# Quick Start Guide

## Setup (First Time)

1. **Run the setup wizard:**
   ```bash
   python setup.py
   ```

   The wizard will guide you through:
   - Getting your Yupp AI session token
   - Generating an API key
   - Setting a dashboard password

2. **Start the server:**
   ```bash
   python run.py
   ```

   The server will start on `http://localhost:8000`

## Usage

### Test the API

```bash
# Health check
curl http://localhost:8000/health

# Chat completion (with automatic reward claiming)
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello!"}]}'

# Check your credit balance
curl -H "Authorization: Bearer YOUR_API_KEY" \
  http://localhost:8000/api/v1/credits
```

### Response Format

**Credits endpoint returns:**
```json
{
  "balance": 5369
}
```

## How Rewards Work

After each chat completion, YuppBridge automatically:
1. Submits randomized feedback (Option 3 pattern)
2. Waits 1-3 seconds (random delay)
3. Claims the reward
4. Updates your credit balance

**No action required!** Rewards are claimed automatically in the background.

## Troubleshooting

### "No config file found"
- Run `python setup.py` to create the config

### "No valid Yupp account available"
- Make sure you added your session token in the wizard
- Or set environment variable: `set YUPP_API_KEY=your_token`
- Token might be expired - get a fresh one from yupp.ai

### "Import error"
- Don't run `python src/main.py` directly
- Use `python run.py` instead

### Check if dependencies are installed
```bash
pip list | findstr "fastapi httpx uvicorn"
```

If missing, run:
```bash
pip install -r requirements.txt
```

## Configuration File

Located at: `config.json`

```json
{
    "auth_tokens": ["your_yupp_session_token"],
    "api_keys": [
        {"name": "default", "key": "sk-...", "rpm": 60}
    ],
    "password": "admin",
    "proxy": null,
    "max_error_count": 3,
    "error_cooldown": 300
}
```

## Environment Variables

Alternative to config file:
```bash
set YUPP_API_KEY=your_yupp_session_token
set DEBUG_MODE=true
```

## Next Steps

- See `README.md` for full documentation
- See `IMPLEMENTATION.md` for technical details
- Check logs for reward claiming activity
