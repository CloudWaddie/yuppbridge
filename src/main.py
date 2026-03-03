"""
YuppBridge - OpenAI-compatible API bridge to Yupp AI.

Exposes POST /api/v1/chat/completions and proxies requests through Yupp AI's internal API.
"""

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from . import auth, config, constants, state, transport
from .token_extractor import get_token_extractor, reset_token_extractor
from .exceptions import (
    YuppBridgeException,
    NoValidAccountException,
    TokenExtractionException,
    AuthenticationException,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("yuppbridge")

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


# Pydantic models for request/response validation
class Message(BaseModel):
    """Chat message model."""
    role: str = Field(..., description="Role of the message sender")
    content: str | List[Dict[str, Any]] = Field(..., description="Content of the message")


class ChatCompletionRequest(BaseModel):
    """Chat completions request model."""
    model: str = Field(default="gpt-4o", description="Model to use")
    messages: List[Message] = Field(..., description="List of chat messages")
    stream: bool = Field(default=False, description="Enable streaming")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0, description="Temperature")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens")
    top_p: Optional[float] = Field(default=None, description="Top p")


class ChatMessage(BaseModel):
    """Chat message response."""
    role: str
    content: str


class ChatChoice(BaseModel):
    """Chat completion choice."""
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionResponse(BaseModel):
    """Chat completion response."""
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatChoice]
    usage: Optional[Dict[str, int]] = None


class ModelInfo(BaseModel):
    """Model information."""
    id: str
    object: str = "model"
    created: int
    owned_by: str


class ModelList(BaseModel):
    """List of models."""
    object: str = "list"
    data: List[ModelInfo]


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    accounts_loaded: int
    accounts_active: int
    uptime_seconds: float
    error_rate: float


class DashboardResponse(BaseModel):
    """Dashboard response."""
    status: str
    accounts: int
    api_keys: int
    total_requests: int
    uptime_seconds: float


# Config file location
CONFIG_FILE = "config.json"

# Application state stored in app.state
_app_start_time: float = 0.0
_request_count: int = 0
_error_count: int = 0
_app_state: Dict[str, Any] = {
    'api_key_usage': {},
    'chat_sessions': {},
    'request_count': 0,
    'error_count': 0,
}


def get_config(cfg_file: Optional[str] = None) -> Dict[str, Any]:
    """Get config with proper file path."""
    return config.get_config(cfg_file or CONFIG_FILE)


def save_config(cfg: Dict[str, Any], cfg_file: Optional[str] = None) -> bool:
    """Save config."""
    return config.save_config(cfg, cfg_file or CONFIG_FILE)


def _get_app_state() -> Dict[str, Any]:
    """Get or initialize app state."""
    global _app_state
    return _app_state


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifespan."""
    global _app_start_time, _request_count, _error_count
    
    # Startup
    _app_start_time = time.time()
    _request_count = 0
    _error_count = 0
    
    logger.info("YuppBridge starting up...")
    
    # Load accounts from config
    cfg = get_config()
    tokens = config.get_auth_tokens(cfg)
    if tokens:
        auth.load_yupp_accounts(",".join(tokens))
        logger.info(f"Loaded %d accounts", len(tokens))
    
    yield
    
    # Shutdown
    logger.info("YuppBridge shutting down...")
    
    # Cleanup ThreadPoolExecutor
    from .transport import cleanup_executor
    cleanup_executor()


# Create FastAPI app
app = FastAPI(
    title="YuppBridge",
    description="OpenAI-compatible API bridge to Yupp AI",
    version="0.2.0",
    lifespan=lifespan,
)

# Add rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware - configurable via environment
_cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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
        raise AuthenticationException("Missing API key")
    
    # Validate against config
    cfg = get_config()
    api_keys = cfg.get("api_keys", [])
    
    valid_keys = [k.get("key") for k in api_keys if k.get("key")]
    if valid_keys and api_key not in valid_keys:
        raise AuthenticationException("Invalid API key")
    
    # Track request
    app_state = _get_app_state()
    app_state['request_count'] = app_state.get('request_count', 0) + 1
    
    return api_key


@app.exception_handler(YuppBridgeException)
async def yupp_bridge_exception_handler(request: Request, exc: YuppBridgeException):
    """Handle custom YuppBridge exceptions."""
    global _error_count
    _error_count += 1
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "type": exc.error_type},
    )


@app.get("/v1/models", response_model=ModelList)
async def list_models(request: Request):
    """List available models."""
    require_api_key(request)
    
    # Return available models
    # In a real implementation, this would fetch from Yupp AI
    models = [
        ModelInfo(id="gpt-4o", object="model", created=1700000000, owned_by="openai"),
        ModelInfo(id="claude-3-5-sonnet", object="model", created=1700000000, owned_by="anthropic"),
        ModelInfo(id="gemini-1.5-pro", object="model", created=1700000000, owned_by="google"),
    ]
    
    return ModelList(object="list", data=models)


@app.post("/api/v1/chat/completions")
@limiter.limit("60/minute")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completions endpoint."""
    api_key = require_api_key(request)
    
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    
    # Extract parameters with Pydantic validation
    messages = body.get("messages", [])
    model = body.get("model", "gpt-4o")
    stream = body.get("stream", False)
    temperature = body.get("temperature", 1.0)
    max_tokens = body.get("max_tokens")
    
    if not messages:
        raise HTTPException(status_code=400, detail="messages is required")
    
    # Get account
    try:
        account = await auth.get_best_yupp_account()
        if not account:
            raise NoValidAccountException()
    except Exception as e:
        logger.error(f"Failed to get account: {e}")
        raise NoValidAccountException()
    
    # Get or create conversation ID
    app_state = _get_app_state()
    conversation_id = None
    if api_key in app_state.get('chat_sessions', {}):
        # Use existing conversation
        convos = app_state['chat_sessions'][api_key]
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
            result, tokens_used = await _non_stream_chat(
                model=model,
                messages=messages,
                account=account,
                conversation_id=conversation_id,
            )
            # Track token usage
            _track_usage(api_key, model, tokens_used)
            
            return JSONResponse(content=result)
    except Exception as e:
        await auth.mark_account_error(account)
        app_state['error_count'] = app_state.get('error_count', 0) + 1
        logger.error(f"Chat completion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _track_usage(api_key: str, model: str, tokens: int) -> None:
    """Track API key usage."""
    app_state = _get_app_state()
    if 'api_key_usage' not in app_state:
        app_state['api_key_usage'] = {}
    
    if api_key not in app_state['api_key_usage']:
        app_state['api_key_usage'][api_key] = []
    
    app_state['api_key_usage'][api_key].append({
        "model": model,
        "tokens": tokens,
        "timestamp": time.time(),
    })


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
    
    # Track tokens from streaming
    total_tokens = 0
    
    # Stream from transport with retry
    async for chunk in _stream_with_retry(
        model=model,
        messages=messages,
        account=account,
        conversation_id=conversation_id,
        proxy=proxy,
    ):
        # Estimate tokens from chunk (rough approximation)
        if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
            total_tokens += len(chunk) // 4  # Rough token estimate
        
        yield chunk
    
    # Mark success
    await auth.mark_account_success(account)
    
    # Track usage
    _track_usage(api_key, model, total_tokens)


async def _stream_with_retry(
    model: str,
    messages: List[Dict[str, Any]],
    account: Dict[str, Any],
    conversation_id: Optional[str],
    proxy: Optional[str],
    max_retries: int = 3,
) -> AsyncGenerator[str, None]:
    """Stream with exponential backoff retry."""
    last_exception: Optional[Exception] = None
    success = False
    
    for attempt in range(max_retries):
        try:
            async for chunk in transport.stream_yupp_chat(
                model=model,
                messages=messages,
                account=account,
                conversation_id=conversation_id,
                proxy=proxy,
            ):
                yield chunk
            success = True
            break  # Success - exit loop
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # Exponential backoff
                logger.warning(
                    "Retry attempt %d/%d after %.1fs: %s",
                    attempt + 1, max_retries, wait_time, str(e)
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error("All retry attempts failed: %s", e)
    
    if not success and last_exception:
        raise last_exception


async def _non_stream_chat(
    model: str,
    messages: List[Dict[str, Any]],
    account: Dict[str, Any],
    conversation_id: Optional[str],
) -> tuple[Dict[str, Any], int]:
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
    
    content = "".join(content_parts)
    # Estimate tokens (roughly 1 token per 4 characters)
    estimated_tokens = len(content) // 4
    
    return {
        "id": f"chatcmpl-{os.urandom(12).hex()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": sum(len(m.get("content", "")) for m in messages) // 4,
            "completion_tokens": estimated_tokens,
            "total_tokens": (sum(len(m.get("content", "")) for m in messages) // 4) + estimated_tokens,
        },
    }, estimated_tokens


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint with enhanced status."""
    global _error_count, _request_count
    
    cfg = get_config()
    tokens = config.get_auth_tokens(cfg)
    
    accounts = state.get_accounts()
    active_accounts = sum(1 for acc in accounts if acc.is_valid)
    
    uptime = time.time() - _app_start_time if _app_start_time > 0 else 0
    error_rate = _error_count / max(_request_count, 1)
    
    return HealthResponse(
        status="healthy",
        accounts_loaded=len(tokens),
        accounts_active=active_accounts,
        uptime_seconds=uptime,
        error_rate=error_rate,
    )


@app.get("/dashboard", response_model=DashboardResponse)
async def dashboard(request: Request):
    """Simple dashboard for managing the bridge."""
    # Check password - require auth header
    auth_header = request.headers.get("Authorization", "")
    cfg = get_config()
    password = cfg.get("password", "")
    
    if password:
        # Check for password in header
        if not auth_header.startswith("Bearer ") or auth_header[7:] != password:
            raise AuthenticationException("Invalid or missing dashboard password")
    
    app_state = _get_app_state()
    uptime = time.time() - _app_start_time if _app_start_time > 0 else 0
    
    return DashboardResponse(
        status="ok",
        accounts=len(state.get_accounts()),
        api_keys=len(cfg.get("api_keys", [])),
        total_requests=app_state.get('request_count', 0),
        uptime_seconds=uptime,
    )


@app.post("/api/v1/config/reload")
async def reload_config(request: Request):
    """Reload configuration."""
    require_api_key(request)
    
    cfg = get_config()
    tokens = config.get_auth_tokens(cfg)
    
    if tokens:
        auth.load_yupp_accounts(",".join(tokens))
    
    logger.info("Configuration reloaded")
    
    return {"status": "reloaded", "accounts": len(tokens)}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    # Import only what's needed
    # Note: We build metrics manually to avoid heavy prometheus_client dependency
    
    app_state = _get_app_state()
    
    # Build metrics response manually
    metric_lines = [
        "# HELP yuppbridge_requests_total Total number of requests",
        "# TYPE yuppbridge_requests_total counter",
        f"yuppbridge_requests_total {app_state.get('request_count', 0)}",
        "",
        "# HELP yuppbridge_errors_total Total number of errors",
        "# TYPE yuppbridge_errors_total counter",
        f"yuppbridge_errors_total {app_state.get('error_count', 0)}",
        "",
        "# HELP yuppbridge_uptime_seconds Application uptime in seconds",
        "# TYPE yuppbridge_uptime_seconds gauge",
        f"yuppbridge_uptime_seconds {time.time() - _app_start_time if _app_start_time > 0 else 0}",
    ]
    
    # Add per-api-key usage
    usage = app_state.get('api_key_usage', {})
    for api_key, usage_list in usage.items():
        total_tokens = sum(u.get('tokens', 0) for u in usage_list)
        metric_lines.extend([
            "",
            f"# HELP yuppbridge_tokens_total Total tokens used for API key",
            "# TYPE yuppbridge_tokens_total counter",
            f'yuppbridge_tokens_total{{api_key="{api_key}"}} {total_tokens}',
        ])
    
    return StreamingResponse(
        iter(["\n".join(metric_lines)]),
        media_type="text/plain",
    )


# Re-export for backward compatibility
from . import auth as _auth
from . import config as _config
from . import state as _state
from . import transport as _transport
from . import token_extractor as _token_extractor

get_config = get_config
save_config = save_config
chat_sessions = lambda: _get_app_state().get('chat_sessions', {})
api_key_usage = lambda: _get_app_state().get('api_key_usage', {})
CONFIG_FILE = CONFIG_FILE
