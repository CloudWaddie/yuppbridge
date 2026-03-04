"""
Reward claiming and feedback submission for Yupp AI
"""
import json
import random
import asyncio
import logging
from typing import Dict, List, Optional, Any

from src import constants

logger = logging.getLogger(__name__)


def generate_feedback_pattern() -> str:
    """
    Generate feedback pattern based on Option 3 distribution:
    - 60%: One GOOD, one BAD
    - 30%: Both GOOD
    - 10%: One GOOD, minimal/empty
    """
    rand = random.random()
    
    if rand < constants.FEEDBACK_PATTERN_ONE_GOOD_ONE_BAD:
        return "one_good_one_bad"
    elif rand < (constants.FEEDBACK_PATTERN_ONE_GOOD_ONE_BAD + constants.FEEDBACK_PATTERN_BOTH_GOOD):
        return "both_good"
    else:
        return "one_good_minimal"


def generate_message_evals(message_ids: List[str], pattern: str) -> List[Dict[str, Any]]:
    """
    Generate message evaluations based on pattern.
    
    Args:
        message_ids: List of message IDs (typically 2 for model A and B)
        pattern: Feedback pattern to use
        
    Returns:
        List of message evaluation dicts
    """
    if len(message_ids) < 2:
        # If only one message, just rate it GOOD
        return [{
            "messageId": message_ids[0],
            "rating": "GOOD",
            "reasons": [random.choice(constants.FEEDBACK_GOOD_REASONS)]
        }]
    
    # Randomly decide which model gets better rating
    shuffle_order = random.random() < 0.5
    msg_a, msg_b = (message_ids[0], message_ids[1]) if not shuffle_order else (message_ids[1], message_ids[0])
    
    if pattern == "one_good_one_bad":
        # 60%: One GOOD, one BAD
        good_reasons = random.sample(constants.FEEDBACK_GOOD_REASONS, k=random.randint(1, 2))
        bad_reasons = random.sample(constants.FEEDBACK_BAD_REASONS, k=random.randint(0, 1))
        
        return [
            {
                "messageId": msg_a,
                "rating": "GOOD",
                "reasons": good_reasons
            },
            {
                "messageId": msg_b,
                "rating": "BAD",
                "reasons": bad_reasons
            }
        ]
    
    elif pattern == "both_good":
        # 30%: Both GOOD with different reasons
        all_reasons = constants.FEEDBACK_GOOD_REASONS.copy()
        random.shuffle(all_reasons)
        
        reasons_a = [all_reasons[0]] if len(all_reasons) > 0 else ["Helpful"]
        reasons_b = [all_reasons[1]] if len(all_reasons) > 1 else ["Interesting"]
        
        return [
            {
                "messageId": msg_a,
                "rating": "GOOD",
                "reasons": reasons_a
            },
            {
                "messageId": msg_b,
                "rating": "GOOD",
                "reasons": reasons_b
            }
        ]
    
    else:  # one_good_minimal
        # 10%: One GOOD, other minimal/empty
        good_reasons = [random.choice(constants.FEEDBACK_GOOD_REASONS)]
        
        return [
            {
                "messageId": msg_a,
                "rating": "GOOD",
                "reasons": good_reasons
            },
            {
                "messageId": msg_b,
                "rating": "BAD",
                "reasons": []
            }
        ]


async def submit_feedback(
    session,
    turn_id: str,
    message_ids: List[str],
    session_token: str
) -> Optional[str]:
    """
    Submit model feedback to Yupp AI.
    
    Args:
        session: cloudscraper session
        turn_id: Turn ID from chat response
        message_ids: List of message IDs to evaluate
        session_token: User's session token
        
    Returns:
        evalId if successful, None otherwise
    """
    try:
        pattern = generate_feedback_pattern()
        message_evals = generate_message_evals(message_ids, pattern)
        
        payload = {
            "0": {
                "json": {
                    "turnId": turn_id,
                    "isOnboarding": False,
                    "evalType": "SELECTION",
                    "messageEvals": message_evals,
                    "comment": "",
                    "requireReveal": False
                }
            }
        }
        
        url = f"{constants.YUPP_API_TRPC}/evals.recordModelFeedback?batch=1"
        headers = {
            "Content-Type": "application/json",
            "Cookie": f"{constants.SESSION_TOKEN_COOKIE}={session_token}",
            "User-Agent": constants.DEFAULT_USER_AGENT,
            "Referer": constants.YUPP_BASE_URL,
            "Origin": constants.YUPP_BASE_URL,
        }
        
        logger.info(f"Submitting feedback for turn {turn_id} with pattern: {pattern}")
        logger.debug(f"Feedback payload: {json.dumps(payload, indent=2)}")
        
        response = session.post(url, json=payload, headers=headers, timeout=constants.DEFAULT_TIMEOUT)
        
        # Log response for debugging
        logger.debug(f"Feedback response status: {response.status_code}")
        logger.debug(f"Feedback response body: {response.text}")
        
        response.raise_for_status()
        
        response = session.post(url, json=payload, headers=headers, timeout=constants.DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for TRPC errors
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            
            # Check if it's an error response
            if isinstance(first_item, dict) and "error" in first_item:
                error_data = first_item.get("error", {})
                error_json = error_data.get("json", {})
                error_msg = error_json.get("message", "Unknown error")
                error_code = error_json.get("code", "N/A")
                logger.error(f"Yupp AI TRPC Error (feedback): Code={error_code}, Message={error_msg}")
                return None
            
            # Extract evalId from successful response
            result = first_item.get("result", {})
            eval_data = result.get("data", {}).get("json", {})
            eval_id = eval_data.get("evalId")
        
        # Extract evalId from response
        if isinstance(data, list) and len(data) > 0:
            result = data[0].get("result", {})
            eval_data = result.get("data", {}).get("json", {})
            eval_id = eval_data.get("evalId")
            
            if eval_id:
                logger.info(f"Feedback submitted successfully. evalId: {eval_id}")
                return eval_id
            else:
                logger.warning(f"No evalId in feedback response: {data}")
        else:
            logger.warning(f"Unexpected feedback response format: {data}")
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}")
        return None


async def claim_reward(
    session,
    eval_id: str,
    session_token: str
) -> Optional[int]:
    """
    Claim reward after submitting feedback.
    
    Args:
        session: cloudscraper session
        eval_id: Evaluation ID from feedback submission
        session_token: User's session token
        
    Returns:
        Current credit balance if successful, None otherwise
    """
    try:
        # Random delay before claiming (1-3 seconds)
        delay = random.uniform(constants.REWARD_CLAIM_MIN_DELAY, constants.REWARD_CLAIM_MAX_DELAY)
        await asyncio.sleep(delay)
        
        payload = {
            "0": {
                "json": {
                    "evalId": eval_id
                }
            }
        }
        
        url = f"{constants.YUPP_API_TRPC}/reward.claim?batch=1"
        headers = {
            "Content-Type": "application/json",
            "Cookie": f"{constants.SESSION_TOKEN_COOKIE}={session_token}",
            "User-Agent": constants.DEFAULT_USER_AGENT,
            "Referer": constants.YUPP_BASE_URL,
            "Origin": constants.YUPP_BASE_URL,
        }
        
        logger.info(f"Claiming reward for evalId: {eval_id}")
        
        response = session.post(url, json=payload, headers=headers, timeout=constants.DEFAULT_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        
        # Check for TRPC errors
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            
            # Check if it's an error response
            if isinstance(first_item, dict) and "error" in first_item:
                error_data = first_item.get("error", {})
                error_json = error_data.get("json", {})
                error_msg = error_json.get("message", "Unknown error")
                error_code = error_json.get("code", "N/A")
                logger.error(f"Yupp AI TRPC Error (claim reward): Code={error_code}, Message={error_msg}")
                return None
            
            # Extract credit balance from successful response
            result = first_item.get("result", {})
            credit_data = result.get("data", {}).get("json", {})
            balance = credit_data.get("currentCreditBalance")
        
        # Extract credit balance from response
        if isinstance(data, list) and len(data) > 0:
            result = data[0].get("result", {})
            credit_data = result.get("data", {}).get("json", {})
            balance = credit_data.get("currentCreditBalance")
            
            if balance is not None:
                logger.info(f"Reward claimed successfully. New balance: {balance}")
                return balance
            else:
                logger.warning(f"No balance in claim response: {data}")
        else:
            logger.warning(f"Unexpected claim response format: {data}")
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to claim reward: {e}")
        return None


async def get_credit_balance(
    session,
    session_token: str
) -> Optional[int]:
    """
    Get current credit balance.
    
    Args:
        session: cloudscraper session
        session_token: User's session token
        
    Returns:
        Current credit balance if successful, None otherwise
    """
    import asyncio
    from . import transport
    
    try:
        url = f"{constants.YUPP_API_TRPC}/credits.getCredits?batch=1&input=%7B%220%22%3A%7B%22json%22%3Anull%2C%22meta%22%3A%7B%22values%22%3A%5B%22undefined%22%5D%2C%22v%22%3A1%7D%7D%7D"
        headers = {
            "Cookie": f"{constants.SESSION_TOKEN_COOKIE}={session_token}",
            "User-Agent": constants.DEFAULT_USER_AGENT,
            "Referer": constants.YUPP_BASE_URL,
        }
        
        loop = asyncio.get_event_loop()
        
        # Run synchronous cloudscraper call in executor
        response = await loop.run_in_executor(
            transport._executor,
            lambda: session.get(url, headers=headers, timeout=constants.DEFAULT_TIMEOUT)
        )
        response.raise_for_status()
        
        # Parse JSON in executor
        data = await loop.run_in_executor(transport._executor, lambda: response.json())
        logger.debug(f"Credit balance raw response: {data}")
        
        # Check for TRPC errors
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            logger.debug(f"First item type: {type(first_item)}, value: {first_item}")
            
            # Check if it's an error response
            if isinstance(first_item, dict) and "error" in first_item:
                error_data = first_item.get("error", {})
                error_json = error_data.get("json", {})
                error_msg = error_json.get("message", "Unknown error")
                error_code = error_json.get("code", "N/A")
                logger.error(f"Yupp AI TRPC Error (credits): Code={error_code}, Message={error_msg}")
                return None
            
            if isinstance(first_item, dict):
                result = first_item.get("result", {})
                credit_data = result.get("data", {}).get("json")
                
                # The balance can be directly an integer or in an object
                if isinstance(credit_data, int):
                    # Direct integer balance
                    return credit_data
                elif isinstance(credit_data, dict):
                    # Balance in object
                    balance = credit_data.get("currentCreditBalance")
                    if balance is not None:
                        return balance
            else:
                logger.error(f"First item is not a dict, it's a {type(first_item)}: {first_item}")
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            logger.debug(f"First item type: {type(first_item)}, value: {first_item}")
            
            # Check if it's an error response
            if isinstance(first_item, dict) and "error" in first_item:
                error_data = first_item.get("error", {})
                error_json = error_data.get("json", {})
                error_msg = error_json.get("message", "Unknown error")
                error_code = error_json.get("code", "N/A")
                logger.error(f"Yupp AI TRPC Error (credits): Code={error_code}, Message={error_msg}")
                return None
            
            if isinstance(first_item, dict):
                result = first_item.get("result", {})
                credit_data = result.get("data", {}).get("json", {})
                balance = credit_data.get("currentCreditBalance")
                
                if balance is not None:
                    return balance
            else:
                logger.error(f"First item is not a dict, it's a {type(first_item)}: {first_item}")
        data = await loop.run_in_executor(transport._executor, lambda: response.json())
        logger.debug(f"Credit balance raw response: {data}")
        
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            logger.debug(f"First item type: {type(first_item)}, value: {first_item}")
            if isinstance(first_item, dict):
                result = first_item.get("result", {})
                credit_data = result.get("data", {}).get("json", {})
                balance = credit_data.get("currentCreditBalance")
                
                if balance is not None:
                    return balance
            else:
                logger.error(f"First item is not a dict, it's a {type(first_item)}: {first_item}")
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to get credit balance: {e}")
        return None


async def process_reward_flow(
    session,
    turn_id: str,
    message_ids: List[str],
    session_token: str
) -> Optional[int]:
    """
    Complete reward flow: submit feedback -> claim reward.
    
    Args:
        session: cloudscraper session
        turn_id: Turn ID from chat response
        message_ids: List of message IDs to evaluate
        session_token: User's session token
        
    Returns:
        New credit balance if successful, None otherwise
    """
    try:
        # Step 1: Submit feedback
        eval_id = await submit_feedback(session, turn_id, message_ids, session_token)
        
        if not eval_id:
            logger.warning("Failed to get evalId from feedback submission")
            return None
        
        # Step 2: Claim reward
        balance = await claim_reward(session, eval_id, session_token)
        
        return balance
        
    except Exception as e:
        logger.error(f"Error in reward flow: {e}")
        return None
