# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Commands

```bash
# Run the server
python src/main.py

# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_auth.py -v

# Run a single test by name
python -m pytest tests/test_auth.py::TestAuth::test_load_yupp_accounts_from_string -v

# Syntax check
python -c "import ast; ast.parse(open('src/main.py', encoding='utf-8').read()); print('OK')"
```

Python version: **3.12** (see `.python-version`).

## Architecture

This is an OpenAI-compatible API bridge to Yupp AI (`yupp.ai`). It exposes `POST /api/v1/chat/completions` and proxies requests through Yupp AI's internal API using cloudscraper for stealthy requests.

### Module structure (`src/`)

- **`main.py`** — FastAPI app, route handlers, request/streaming logic, startup lifespan.
- **`constants.py`** — All hardcoded values: URLs, timeouts, token patterns, headers.
- **`config.py`** — Config file I/O (`get_config`, `save_config`, `get_auth_tokens`, `save_auth_tokens`).
- **`state.py`** — In-memory shared state (accounts, chat sessions, image cache, token extractor).
- **`auth.py`** — Auth token management: loading, validation, round-robin selection, error tracking.
- **`token_extractor.py`** — NextAction token extraction with caching and fallback strategies.
- **`transport.py`** — Streaming transport layer using cloudscraper.

### Cross-module pattern (`_m()` late import)

The sibling project lmarenabridge uses a `_m()` late import pattern for testability. YuppBridge uses direct imports but maintains similar testability through `state.reset_state()` and `token_extractor.reset_token_extractor()` in test setup.

### Transport layer

The chat completions endpoint uses cloudscraper for making requests:

1. **Direct cloudscraper** — Standard sync HTTP via cloudscraper with stealthy headers.
2. **Streaming** — Uses SSE (Server-Sent Events) for streaming responses.

### Auth token lifecycle

- Tokens are session cookies from Yupp AI.
- `get_best_yupp_account()` does round-robin over configured tokens, filtering by error count.
- After errors, accounts are marked invalid until cooldown expires.
- Token extractor provides NextAction tokens for API calls.

### Startup flow

On startup, the server:
1. Loads auth tokens from config or environment
2. Initializes account pool
3. Ready to serve requests

### Config file (`config.json`)

Key fields: `auth_tokens` (list), `api_keys` (list of `{name, key, rpm, created}`), `password`, `proxy`, `max_error_count`, `error_cooldown`.

### Testing

Tests use `unittest.IsolatedAsyncioTestCase` via `BaseBridgeTest` in `tests/_test_utils.py`. Each test:
- Uses temp config files
- Clears state between tests via `state.reset_state()`
- Uses fake responses for transport testing

## Environment Variables

- `YUPP_API_KEY` — Comma-separated auth tokens
- `YUPP_TOKENS` — Alternative to YUPP_API_KEY
- `MAX_ERROR_COUNT` — Max errors before account disabled (default: 3)
- `ERROR_COOLDOWN` — Seconds before retry (default: 300)
- `DEBUG_MODE` — Enable debug logging

## API Endpoints

- `POST /api/v1/chat/completions` — Chat completions (OpenAI-compatible)
- `GET /v1/models` — List available models
- `GET /health` — Health check
- `GET /dashboard` — Simple admin dashboard
- `POST /api/v1/config/reload` — Reload configuration
