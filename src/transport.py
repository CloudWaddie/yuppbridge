"""
Transport layer for YuppBridge.

Contains streaming transport implementation using cloudscraper.
"""

import asyncio
import json
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from . import auth, constants, state, token_extractor as tex

_executor = ThreadPoolExecutor(max_workers=32)
_executor_shutdown = False


def cleanup_executor() -> None:
    """Clean up the ThreadPoolExecutor on shutdown."""
    global _executor_shutdown
    if not _executor_shutdown:
        _executor.shutdown(wait=True)
        _executor_shutdown = True
        import logging
        logging.getLogger("yuppbridge").info("ThreadPoolExecutor shut down")


def log_debug(message: str) -> None:
    """Debug logging."""
    if os.getenv("DEBUG_MODE", "false").lower() == "true":
        print(f"[DEBUG] {message}")


def create_scraper():
    """Create a cloudscraper instance with stealthy headers."""
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
                "mobile": False,
            },
            delay=10,
            interpreter="nodejs",
        )
        scraper.headers.update(
            {
                "User-Agent": constants.DEFAULT_USER_AGENT,
                "Accept": "text/x-component, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Ch-Ua": '"Microsoft Edge";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            }
        )
        return scraper
    except ImportError:
        raise ImportError("cloudscraper is required for YuppBridge")


def format_messages_for_yupp(messages: List[Dict[str, Any]]) -> str:
    """Format messages for Yupp AI API."""
    if not messages:
        return ""

    if len(messages) == 1 and isinstance(messages[0].get("content"), str):
        return messages[0].get("content", "").strip()

    formatted = []

    # System/developer messages
    system_messages = [
        msg for msg in messages if msg.get("role") in ["developer", "system"]
    ]
    if system_messages:
        for sys_msg in system_messages:
            content = sys_msg.get("content", "")
            if content:
                formatted.append(content)

    # User/assistant messages
    user_assistant_msgs = [
        msg for msg in messages if msg.get("role") in ["user", "assistant"]
    ]
    for msg in user_assistant_msgs:
        role = "Human" if msg.get("role") == "user" else "Assistant"
        content = msg.get("content", "")
        
        if isinstance(content, list):
            for part in content:
                if part.get("text", "").strip():
                    formatted.append(f"\n\n{role}: {part.get('text', '')}")
        elif content:
            formatted.append(f"\n\n{role}: {content}")

    # Ensure we end with Assistant:
    if not formatted or not formatted[-1].strip().startswith("Assistant:"):
        formatted.append("\n\nAssistant:")

    result = "".join(formatted)
    if result.startswith("\n\n"):
        result = result[2:]

    return result


def prepare_media(media: Any, scraper: Any, account: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare media files for upload."""
    files = []
    if not media:
        return files
    
    # Media preparation logic would go here
    # For now, return empty list
    return files


async def stream_yupp_chat(
    model: str,
    messages: List[Dict[str, Any]],
    account: Dict[str, Any],
    conversation_id: Optional[str] = None,
    proxy: Optional[str] = None,
    media: Optional[Any] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream chat completions from Yupp AI.
    
    Yields SSE-formatted chunks.
    """
    scraper = create_scraper()
    
    if proxy:
        scraper.proxies = {"http": proxy, "https": proxy}
    
    # Set auth cookie
    scraper.cookies.set(constants.SESSION_TOKEN_COOKIE, account["token"])
    
    # Get token extractor
    token_ext = tex.get_token_extractor(jwt_token=account["token"], scraper=scraper)
    
    # Prepare messages
    is_new_conversation = conversation_id is None
    
    if is_new_conversation:
        conversation_id = str(uuid.uuid4())
        prompt = format_messages_for_yupp(messages)
    else:
        # For existing conversations, just get the last user message
        prompt = messages[-1].get("content", "") if messages else ""
    
    log_debug(f"Conversation ID: {conversation_id}, Is new: {is_new_conversation}")
    
    turn_id = str(uuid.uuid4())
    
    # Prepare files if media provided
    files = []
    if media:
        files = prepare_media(media, scraper, account)
    
    # Determine mode
    mode = "image"  # Could check model capabilities
    
    # Build payload
    if is_new_conversation:
        payload = [
            conversation_id,
            turn_id,
            prompt,
            "$undefined",
            "$undefined",
            files,
            "$undefined",
            [{"modelName": model, "promptModifierId": "$undefined"}] if model else "none",
            mode,
            True,
            "$undefined",
        ]
    else:
        payload = [
            conversation_id,
            turn_id,
            prompt,
            False,
            [],
            [{"modelName": model, "promptModifierId": "$undefined"}] if model else "none",
            mode,
        ]
    
    # Get next action token
    next_action = await token_ext.get_token(
        "new_conversation" if is_new_conversation else "existing_conversation"
    )
    
    # Build URL
    url = f"{constants.YUPP_BASE_URL}/chat/{conversation_id}?stream=true"
    
    log_debug(f"Streaming from: {url}")
    
    # Make request
    headers = {
        "Content-Type": "application/json",
        "Next-Action": next_action,
    }
    
    try:
        response = scraper.post(
            url,
            json=payload,
            headers=headers,
            stream=True,
            timeout=constants.STREAM_TIMEOUT,
        )
        response.raise_for_status()
        
        # Process streaming response
        async for chunk in _process_stream_response(
            response, token_ext, account, model
        ):
            yield chunk
            
    except Exception as e:
        log_debug(f"Stream error: {e}")
        # Mark token as failed if it was the issue
        await token_ext.mark_token_failed(
            "new_conversation" if is_new_conversation else "existing_conversation",
            next_action
        )
        raise


async def _process_stream_response(
    response: Any,
    token_ext: "tex.TokenExtractor",
    account: Dict[str, Any],
    model: str,
) -> AsyncGenerator[str, None]:
    """Process the streaming response from Yupp AI with RSC reference resolution."""
    
    # Line pattern for SSE - matches hex chunk IDs (0-9, a-f)
    line_pattern = re.compile(rb'^([0-9a-f]+):(.+)$')
    
    think_blocks: Dict[str, str] = {}
    image_blocks: Dict[str, str] = {}
    
    # RSC chunk storage for reference resolution
    chunk_map: Dict[str, Any] = {}  # Store all chunks by their hex ID
    
    capturing_ref_id: Optional[str] = None
    capturing_lines: List[bytes] = []
    
    target_stream_id = None
    variant_stream_id = None
    quick_response_id = None
    turn_id = None
    left_message_id = None
    right_message_id = None
    
    def resolve_reference(value: Any) -> Any:
        """Resolve RSC reference ($@xx) to actual value from chunk map."""
        if isinstance(value, str) and value.startswith("$@"):
            ref_id = value[2:]  # Remove $@ prefix
            if ref_id in chunk_map:
                resolved = chunk_map[ref_id]
                log_debug(f"Resolved {value} -> {resolved}")
                # If resolved value is also a reference, resolve recursively
                if isinstance(resolved, dict) and "curr" in resolved:
                    return resolved.get("curr")
                return resolved
            else:
                log_debug(f"Reference {value} not found in chunk_map (yet)")
        return value
    """Process the streaming response from Yupp AI."""
    
    # Line pattern for SSE
    line_pattern = re.compile(rb'^(\d+):(.+)$')
    
    think_blocks: Dict[str, str] = {}
    image_blocks: Dict[str, str] = {}
    
    capturing_ref_id: Optional[str] = None
    capturing_lines: List[bytes] = []
    
    target_stream_id = None
    variant_stream_id = None
    quick_response_id = None
    turn_id = None
    left_message_id = None
    right_message_id = None
    
    loop = asyncio.get_event_loop()
    
    def iter_lines():
        for line in response.iter_lines():
            if line:
                yield line
    
    lines_iterator = iter_lines()
    
    while True:
        try:
            line = await loop.run_in_executor(
                _executor, lambda: next(lines_iterator, None)
            )
            if line is None:
                break
        except StopIteration:
            break
        
        if isinstance(line, str):
            line = line.encode()
        
        # Handle thinking blocks
        if b"<think>" in line:
            m = line_pattern.match(line)
            if m:
                capturing_ref_id = m.group(1).decode()
                capturing_lines = [line]
                continue
        
        # Handle yapp blocks
        if capturing_ref_id is not None:
            capturing_lines.append(line)
            if b"</yapp>" in line:
                idx = line.find(b"</yapp>")
                suffix = line[idx + len(b"</yapp>"):]
                
                # Store the captured block
                if capturing_ref_id in think_blocks:
                    # Already have think block, this might be yapp
                    pass
                
                capturing_ref_id = None
                capturing_lines = []
                
                if suffix.strip():
                    line = suffix
                else:
                    continue
        
        # Parse line
        match = line_pattern.match(line)
        if not match:
            continue
        
        chunk_id, chunk_data = match.groups()
        chunk_id = chunk_id.decode()
        
        try:
            data = json.loads(chunk_data) if chunk_data != b"{}" else {}
        except json.JSONDecodeError:
            continue
        
        # Store chunk in map for reference resolution
        chunk_map[chunk_id] = data
        log_debug(f"Stored chunk {chunk_id} in map")
        # Process based on chunk ID
        if chunk_id == "1":
            # Initial response
            if isinstance(data, dict):
                left_stream = data.get("leftStream", {})
                right_stream = data.get("rightStream", {})
                
                # Assign stream IDs for content matching
                if left_stream and left_stream != "$undefined":
                    target_stream_id = _extract_ref_id(left_stream.get("next"))
                    # Strip $@ prefix for chunk ID matching
                    if target_stream_id and target_stream_id.startswith("$@"):
                        target_stream_id = target_stream_id[2:]
                    log_debug(f"Assigned target_stream_id: {target_stream_id}")
                
                if right_stream and right_stream != "$undefined":
                    variant_stream_id = _extract_ref_id(right_stream.get("next"))
                    # Strip $@ prefix for chunk ID matching
                    if variant_stream_id and variant_stream_id.startswith("$@"):
                        variant_stream_id = variant_stream_id[2:]
                    log_debug(f"Assigned variant_stream_id: {variant_stream_id}")
                
                # Extract stream IDs
                if data.get("quickResponse", {}) != "$undefined":
                    quick_response_id = _extract_ref_id(
                        data.get("quickResponse", {}).get("stream", {}).get("next")
                    )
                
                if data.get("turnId", {}) != "$undefined":
                    # turnId is a direct value, not a reference object
                    turn_id_value = data.get("turnId")
                    if isinstance(turn_id_value, str):
                        turn_id = turn_id_value
                    elif isinstance(turn_id_value, dict):
                        turn_id = _extract_ref_id(turn_id_value.get("next"))
                
                if data.get("leftMessageId", {}) != "$undefined":
                    left_message_id = _extract_ref_id(
                        data.get("leftMessageId", {}).get("next")
                    )
                
                if data.get("rightMessageId", {}) != "$undefined":
                    right_message_id = _extract_ref_id(
                        data.get("rightMessageId", {}).get("next")
                    )
        
        # Yield content based on stream IDs
        if target_stream_id and chunk_id == target_stream_id:
            if isinstance(data, dict):
                target_stream_id = _extract_ref_id(data.get("next"))
                content = data.get("curr", "")
                if content:
                    yield f"data: {json.dumps({'content': content})}\n\n"
        
        elif variant_stream_id and chunk_id == variant_stream_id:
            if isinstance(data, dict):
                variant_stream_id = _extract_ref_id(data.get("next"))
                content = data.get("curr", "")
                if content:
                    yield f"data: {json.dumps({'content': f'[Variant] {content}'})}\n\n"
        
        elif quick_response_id and chunk_id == quick_response_id:
            if isinstance(data, dict):
                content = data.get("curr", "")
                if content:
                    yield f"data: {json.dumps({'content': f'[Quick] {content}'})}\n\n"
    
    # End of stream - resolve references and trigger reward flow
    # Wait a moment for any late-arriving chunks
    await asyncio.sleep(0.5)
    
    # Resolve all reference IDs to actual values
    turn_id = resolve_reference(turn_id)
    left_message_id = resolve_reference(left_message_id)
    right_message_id = resolve_reference(right_message_id)
    
    log_debug(f"Final resolved IDs - turn_id: {turn_id}, left: {left_message_id}, right: {right_message_id}")
    log_debug(f"Chunk map keys: {list(chunk_map.keys())}")
    print(f"[REWARD DEBUG] Final resolved IDs - turn_id: {turn_id}, left: {left_message_id}, right: {right_message_id}")
    print(f"[REWARD DEBUG] Chunk map keys: {list(chunk_map.keys())}")
    
    if turn_id and left_message_id and right_message_id:
        try:
            # Import rewards module
            from . import rewards
            
            # Create message IDs list
            message_ids = [left_message_id, right_message_id]
            
            # Submit feedback and claim reward in background
            loop = asyncio.get_event_loop()
            scraper = create_scraper()
            
            async def claim_in_background():
                try:
                    balance = await rewards.process_reward_flow(
                        session=scraper,
                        turn_id=turn_id,
                        message_ids=message_ids,
                        session_token=account.get('token', '')
                    )
                    if balance is not None:
                        state.update_credit_balance(account.get('token', ''), balance)
                        log_debug(f"Reward claimed successfully. New balance: {balance}")
                except Exception as e:
                    log_debug(f"Background reward claim failed: {e}")
            
            # Fire and forget
            asyncio.create_task(claim_in_background())
        except Exception as e:
            log_debug(f"Failed to initiate reward flow: {e}")
    
    yield "data: [DONE]\n\n"


def _extract_ref_id(value: Any) -> Optional[str]:
    """Extract reference ID from value."""
    if isinstance(value, dict):
        return value.get("next")
    return value


async def sync_claim_reward(
    scraper: Any,
    account: Dict[str, Any],
    eval_id: str,
) -> Optional[float]:
    """Claim reward for model feedback."""
    try:
        log_debug(f"Claiming reward {eval_id}...")
        url = f"{constants.YUPP_BASE_URL}{constants.REWARD_CLAIM_ENDPOINT}?batch=1"
        payload = {"0": {"json": {"evalId": eval_id}}}
        scraper.cookies.set(constants.SESSION_TOKEN_COOKIE, account["token"])
        response = scraper.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        balance = data[0]["result"]["data"]["json"]["currentCreditBalance"]
        log_debug(f"Reward claimed. New balance: {balance}")
        return balance
    except Exception as e:
        log_debug(f"Failed to claim reward: {e}")
        return None


async def sync_record_feedback(
    scraper: Any,
    account: Dict[str, Any],
    turn_id: str,
    left_message_id: str,
    right_message_id: str,
) -> Optional[str]:
    """Record model feedback with randomized patterns (Option 3)."""
    try:
        from . import rewards
        
        log_debug(f"Recording feedback for turn {turn_id}...")
        
        # Generate randomized feedback
        pattern = rewards.generate_feedback_pattern()
        message_ids = [left_message_id, right_message_id]
        message_evals = rewards.generate_message_evals(message_ids, pattern)
        
        url = f"{constants.YUPP_BASE_URL}{constants.FEEDBACK_RECORD_ENDPOINT}?batch=1"
        payload = {
            "0": {
                "json": {
                    "turnId": turn_id,
                    "isOnboarding": False,
                    "evalType": "SELECTION",
                    "messageEvals": message_evals,
                    "comment": "",
                    "requireReveal": False,
                }
            }
        }
        scraper.cookies.set(constants.SESSION_TOKEN_COOKIE, account["token"])
        response = scraper.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        for result in data:
            json_data = result.get("result", {}).get("data", {}).get("json", {})
            eval_id = json_data.get("evalId")
            final_reward = json_data.get("finalRewardAmount")
            
            if final_reward:
                log_debug(f"Feedback recorded - evalId: {eval_id}, reward: {final_reward}, pattern: {pattern}")
                return eval_id
        
        return None
    except Exception as e:
        log_debug(f"Failed to record feedback: {e}")
        return None


async def fetch_yupp_models(
    account: Dict[str, Any],
    proxy: Optional[str] = None,
) -> List[Dict[str, Any]]:
    scraper = create_scraper()
    
    if proxy:
        scraper.proxies = {"http": proxy, "https": proxy}
    
    scraper.cookies.set(constants.SESSION_TOKEN_COOKIE, account["token"])
    
    url = f"{constants.YUPP_BASE_URL}/api/trpc/model.getModelInfoList?batch=1&input=%7B%220%22%3A%7B%22json%22%3A%7B%22includeRecents%22%3Atrue%7D%7D%7D"
    
    loop = asyncio.get_event_loop()
    
    try:
        response = await loop.run_in_executor(
            _executor,
            lambda: scraper.get(
                url,
                headers={
                    "Accept": "*/*",
                },
                timeout=constants.DEFAULT_TIMEOUT,
            ),
        )
        response.raise_for_status()
        
        data = await loop.run_in_executor(_executor, lambda: response.json())
        
        # Check for TRPC errors
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "error" in item:
                    error_data = item.get("error", {})
                    error_json = error_data.get("json", {})
                    error_msg = error_json.get("message", "Unknown error")
                    error_code = error_json.get("code", "N/A")
                    log_debug(f"TRPC Error in models response: Code={error_code}, Message={error_msg}")
                    logger.error(f"Yupp AI TRPC Error (models): {error_msg}")
                    return []
        
        models = []
        log_debug(f"Models response received. Count: {len(data) if isinstance(data, list) else 'N/A'}")
        
        # Check for TRPC errors
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "error" in item:
                    error_data = item.get("error", {})
                    error_json = error_data.get("json", {})
                    error_msg = error_json.get("message", "Unknown error")
                    error_code = error_json.get("code", "N/A")
                    log_debug(f"TRPC Error in models response: Code={error_code}, Message={error_msg}")
                    logger.error(f"Yupp AI TRPC Error (models): {error_msg}")
                    return []
        
        models = []
        log_debug(f"Models response received. Count: {len(data) if isinstance(data, list) else 'N/A'}")
        
        models = []
        
        if isinstance(data, list):
            for item in data:
                result = item.get("result", {})
                json_data = result.get("data", {}).get("json", {})
                
                model_list = json_data if isinstance(json_data, list) else json_data.get("models", [])
                
                for model in model_list:
                    # API returns: id (UUID), name (internal name), label (display name)
                    model_name = (model.get("name") or model.get("id", "")).strip()  # Use internal name as ID
                    if model_name:
                        display_name = (model.get("label") or model.get("shortLabel") or model_name).strip()
                        models.append({
                            "id": model_name,  # Use internal name (e.g., gpt-5.3-codex<>low)
                            "name": display_name,  # Display name
                            "object": "model",
                            "created": model.get("timeAddedMillis", constants.DEFAULT_MODEL_CREATED_TIMESTAMP) // 1000,  # Convert ms to seconds
                            "owned_by": (model.get("publisher") or "yupp").strip(),
                            "description": (model.get("family") or "").strip(),
                            "tags": [],  # Tags not in this format
                        })
                    # API returns: id (UUID), name (internal name), label (display name)
                    model_name = model.get("name") or model.get("id", "")  # Use internal name as ID
                    if model_name:
                        models.append({
                            "id": model_name,  # Use internal name (e.g., gpt-5.3-codex<>low)
                            "name": model.get("label") or model.get("shortLabel") or model_name,  # Display name
                            "object": "model",
                            "created": model.get("timeAddedMillis", constants.DEFAULT_MODEL_CREATED_TIMESTAMP) // 1000,  # Convert ms to seconds
                            "owned_by": model.get("publisher", "yupp"),
                            "description": model.get("family", ""),
                            "tags": [],  # Tags not in this format
                        })
                    # API returns: name, label, shortLabel, publisher, family
                    model_id = model.get("name") or model.get("id", "")
                    if model_id:
                        models.append({
                            "id": model_id,
                            "name": model.get("label") or model.get("shortLabel") or model_id,
                            "object": "model",
                            "created": model.get("timeAddedMillis", constants.DEFAULT_MODEL_CREATED_TIMESTAMP) // 1000,  # Convert ms to seconds
                            "owned_by": model.get("publisher", "yupp"),
                            "description": model.get("family", ""),
                            "tags": [],  # Tags not in this format
                        })
        
        log_debug(f"Successfully parsed {len(models)} models from Yupp AI")
        
        return models
        
    except httpx.HTTPError as e:
        log_debug(f"Failed to fetch models due to HTTP error: {e}")
        return []
    except json.JSONDecodeError as e:
        log_debug(f"Failed to parse models response: {e}")
        return []
    except Exception as e:
        log_debug(f"An unexpected error occurred while fetching models: {e}")
        return []
