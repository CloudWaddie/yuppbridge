"""
YuppBridge - OpenAI-compatible API bridge to Yupp AI.

Exposes POST /api/v1/chat/completions and proxies requests through Yupp AI's internal API.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from . import auth, config, constants, state, transport
from .token_extractor import get_token_extractor, reset_token_extractor


# Config file location
CONFIG_FILE = "config.json"

# Global state
api_key_usage: Dict[str, List[Dict[str, Any]]] = {}
chat_sessions: Dict[str, List[Dict[str, Any]]] = {}
current_token_index = 0


def get_config(cfg_file: Optional[str] = None) -> Dict[str, Any]:
    """Get config with proper file path."""
    return config.get_config(cfg_file or CONFIG_FILE)


def save_config(cfg: Dict[str, Any], cfg_file: Optional[str] = None) -> bool:
    """Save config."""
    return config.save_config(cfg, cfg_file or CONFIG_FILE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifespan."""
    # Startup
    print("[YuppBridge] Starting up...")
    
    # Load accounts from config
    cfg = get_config()
    tokens = config.get_auth_tokens(cfg)
    if tokens:
        auth.load_yupp_accounts(",".join(tokens))
        print(f"[YuppBridge] Loaded {len(tokens)} accounts")
    
    yield
    
    # Shutdown
    print("[YuppBridge] Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="YuppBridge",
    description="OpenAI-compatible API bridge to Yupp AI",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_api_key(request: Request) -> str:
    """Extract and validate API key from request."""
    auth_header = request.headers.get("Authorization", "")
    
    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:]
    else:
        # Check query param
        api_key = request.query_params.get("api_key", "")
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")
    
    # Validate against config
    cfg = get_config()
    api_keys = cfg.get("api_keys", [])
    
    valid_keys = [k.get("key") for k in api_keys if k.get("key")]
    if valid_keys and api_key not in valid_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    return api_key


@app.get("/v1/models")
async def list_models(request: Request):
    """List available models."""
    require_api_key(request)
    
    # Return available models
    # In a real implementation, this would fetch from Yupp AI
    models = [
        {"id": "gpt-4o", "object": "model", "created": 1700000000, "owned_by": "openai"},
        {"id": "claude-3-5-sonnet", "object": "model", "created": 1700000000, "owned_by": "anthropic"},
        {"id": "gemini-1.5-pro", "object": "model", "created": 1700000000, "owned_by": "google"},
    ]
    
    return {"object": "list", "data": models}


@app.post("/api/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint."""
    api_key = require_api_key(request)
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    # Extract parameters
    messages = body.get("messages", [])
    model = body.get("model", "gpt-4o")
    stream = body.get("stream", False)
    temperature = body.get("temperature", 1.0)
    max_tokens = body.get("max_tokens")
    
    if not messages:
        raise HTTPException(status_code=400, detail="messages is required")
    
    # Get account
    account = await auth.get_best_yupp_account()
    if not account:
        raise HTTPException(status_code=503, detail="No valid Yupp accounts available")
    
    # Get or create conversation ID
    conversation_id = None
    if api_key in chat_sessions:
        # Use existing conversation
        convos = chat_sessions[api_key]
        if convos:
            conversation_id = convos[-1].get("conversation_id")
    
    try:
        if stream:
            return StreamingResponse(
                _stream_chat(
                    model=model,
                    messages=messages,
                    account=account,
                    conversation_id=conversation_id,
                    api_key=api_key,
                ),
                media_type="text/event-stream",
            )
        else:
            # Non-streaming response
            result = await _non_stream_chat(
                model=model,
                messages=messages,
                account=account,
                conversation_id=conversation_id,
            )
            return JSONResponse(content=result)
    except Exception as e:
        await auth.mark_account_error(account)
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_chat(
    model: str,
    messages: List[Dict[str, Any]],
    account: Dict[str, Any],
    conversation_id: Optional[str],
    api_key: str,
):
    """Stream chat completions."""
    
    # Get config for proxy
    cfg = get_config()
    proxy = cfg.get("proxy")
    
    # Stream from transport
    async for chunk in transport.stream_yupp_chat(
        model=model,
        messages=messages,
        account=account,
        conversation_id=conversation_id,
        proxy=proxy,
    ):
        yield chunk
    
    # Mark success
    await auth.mark_account_success(account)
    
    # Track usage
    if api_key not in api_key_usage:
        api_key_usage[api_key] = []
    api_key_usage[api_key].append({
        "model": model,
        "tokens": 0,  # Would calculate actual tokens
    })


async def _non_stream_chat(
    model: str,
    messages: List[Dict[str, Any]],
    account: Dict[str, Any],
    conversation_id: Optional[str],
) -> Dict[str, Any]:
    """Non-streaming chat completions."""
    
    # Collect all chunks
    content_parts = []
    
    cfg = get_config()
    proxy = cfg.get("proxy")
    
    async for chunk in transport.stream_yupp_chat(
        model=model,
        messages=messages,
        account=account,
        conversation_id=conversation_id,
        proxy=proxy,
    ):
        if chunk.startswith("data: "):
            data = chunk[6:]
            if data == "[DONE]":
                break
            try:
                parsed = json.loads(data)
                if "content" in parsed:
                    content_parts.append(parsed["content"])
            except json.JSONDecodeError:
                continue
    
    # Mark success
    await auth.mark_account_success(account)
    
    return {
        "id": f"chatcmpl-{os.urandom(12).hex()}",
        "object": "chat.completion",
        "created": int(asyncio.get_event_loop().time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "".join(content_parts),
                },
                "finish_reason": "stop",
            }
        ],
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    cfg = get_config()
    tokens = config.get_auth_tokens(cfg)
    
    return {
        "status": "healthy",
        "accounts_loaded": len(tokens),
    }


@app.get("/dashboard")
async def dashboard(request: Request):
    """Simple dashboard for managing the bridge."""
    # Check password
    cfg = get_config()
    password = cfg.get("password", "")
    
    if password:
        # Would check session/auth here
        pass
    
    # Return basic stats
    return {
        "status": "ok",
        "accounts": len(state.get_accounts()),
        "api_keys": len(cfg.get("api_keys", [])),
    }


@app.post("/api/v1/config/reload")
async def reload_config(request: Request):
    """Reload configuration."""
    require_api_key(request)
    
    cfg = get_config()
    tokens = config.get_auth_tokens(cfg)
    
    if tokens:
        auth.load_yupp_accounts(",".join(tokens))
    
    return {"status": "reloaded", "accounts": len(tokens)}


# Re-export for backward compatibility
from . import auth as _auth
from . import config as _config
from . import state as _state
from . import transport as _transport
from . import token_extractor as _token_extractor

get_config = get_config
save_config = save_config
chat_sessions = chat_sessions
api_key_usage = api_key_usage
CONFIG_FILE = CONFIG_FILE
