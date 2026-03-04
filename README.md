# YuppBridge

OpenAI-compatible API bridge to Yupp AI (yupp.ai).

### Thank you to the [AI Leaks server](https://discord.gg/fqmaHkQpJZ) for being a partner!

![AI-Leaks-Logo](https://github.com/user-attachments/assets/5fd3d456-152c-44e2-acee-f4c2a1ca2caa)

## Sister Projects

- **[LM Arena Bridge](https://github.com/cloudwaddie/lmarenabridge)** - OpenAI-compatible API bridge to LM Arena

## Description

YuppBridge provides an OpenAI-compatible API endpoint that interacts with models on Yupp AI. It uses cloudscraper for stealthy requests and supports streaming responses.

## Getting Started

### Quick Setup (Recommended)

Run the interactive setup wizard:

```bash
python setup.py
```

The wizard will guide you through:
1. Getting your Yupp AI session token
2. Generating an API key
3. Setting a dashboard password

### Manual Setup

### Prerequisites

- Python 3.12+
- cloudscraper

- Python 3.10+
- cloudscraper

### Installation

```bash
pip install -r requirements.txt
pip install -e .
```

### 1. Get your Authentication Token

To use YuppBridge, you need to get your session token from the Yupp AI website.

1. Open your web browser and go to [yupp.ai](https://yupp.ai).
2. Log in to your account (or use the website without login for limited access).
3. Send a message in the chat (this generates the session token).
4. Open the developer tools in your browser (F12).
5. Go to the "Application" or "Storage" tab.
6. In the "Cookies" section, find the cookies for the yupp.ai domain.
7. Look for a cookie named `__Secure-yupp.session-token` and copy its value.

### 2. Configure the Application

Create a `config.json` file:

```json
{
    "auth_tokens": ["your_yupp_session_token_here"],
    "api_keys": [
        {"name": "default", "key": "sk-your-api-key", "rpm": 60}
    ],
    "password": "admin",
    "proxy": null,
    "max_error_count": 3,
    "error_cooldown": 300
}
```

Or set environment variable:
```bash
export YUPP_API_KEY="your_yupp_session_token"
```

### 3. Run the Application

```bash
# Option 1: Using the run script (recommended)
python run.py

# Option 2: Using uvicorn directly
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```


The application will start a server on `localhost:8000`.

## Usage

### Chat Completions

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

### Streaming

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Authorization: Bearer sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": true
  }'
```

## API Endpoints

- `POST /api/v1/chat/completions` — OpenAI-compatible chat completions
- `GET /api/v1/models` — List available models
- `GET /health` — Health check
- `GET /dashboard` — Admin dashboard
- `POST /api/v1/config/reload` — Reload configuration
- `GET /api/v1/credits` — Get current credit balance
- `GET /metrics` — Prometheus metrics endpoint

## Environment Variables
- `YUPP_API_KEY` — Comma-separated auth tokens
- `YUPP_TOKENS` — Alternative to YUPP_API_KEY
- `MAX_ERROR_COUNT` — Max errors before account disabled (default: 3)
- `ERROR_COOLDOWN` — Seconds before retry (default: 300)
- `DEBUG_MODE` — Enable debug logging and auto-reload (set to `true`)
## Debug Mode
To run the server in debug mode with auto-reload and verbose logging:
**Windows (Git Bash/PowerShell):**
```bash
set DEBUG_MODE=true
python run.py
```
**Linux/Mac:**
```bash
export DEBUG_MODE=true
python run.py
```
**Or inline:**
```bash
DEBUG_MODE=true python run.py
```
Debug mode features:
- Auto-reload on code changes
- Verbose debug logging
- Detailed error messages
**Graceful Shutdown:**
Press `Ctrl-C` to stop the server gracefully.

- `YUPP_API_KEY` — Comma-separated auth tokens
- `YUPP_TOKENS` — Alternative to YUPP_API_KEY
- `MAX_ERROR_COUNT` — Max errors before account disabled (default: 3)
- `ERROR_COOLDOWN` — Seconds before retry (default: 300)
- `DEBUG_MODE` — Enable debug logging
## Credits and Rewards

YuppBridge automatically claims rewards by submitting randomized model feedback after each chat completion. This earns credits on your Yupp AI account.

### How It Works

1. After each chat completion, the system automatically submits feedback comparing the models
2. Feedback is randomized using Option 3 pattern:
   - 60% of time: One model rated GOOD, other rated BAD
   - 30% of time: Both models rated GOOD with different reasons
   - 10% of time: One model rated GOOD, other minimal/empty
3. Reasons are randomly selected from common user feedback:
   - GOOD reasons: "Helpful", "Interesting", "Accurate", "Clear", "Well explained"
   - BAD reasons: "Not helpful", "Inaccurate", "Unclear" (or empty)
4. After feedback submission, rewards are automatically claimed
5. Credit balance is tracked per account

### Check Your Credit Balance

```bash
curl -X GET http://localhost:8000/api/v1/credits \
  -H "Authorization: Bearer sk-your-api-key"
```

Response:
```json
{
  "balance": 5369,
  "account": "eyJhbGci..."
}
```

### Anti-Detection Features

- Randomized feedback patterns mimic natural user behavior
- Varied rating distributions (not always the same model wins)
- Random 1-3 second delay between feedback and reward claim
- Rotation through common feedback reasons
- No comments (most users don't write them)

This approach makes the automated feedback indistinguishable from real user interactions.

## Testing

```bash
python -m pytest tests/
```

## Architecture

See [CLAUDE.md](CLAUDE.md) for detailed architecture documentation.
