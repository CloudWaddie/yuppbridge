"""
Constants for Yupp AI bridge
"""

# Yupp AI URLs
YUPP_BASE_URL = "https://yupp.ai"
YUPP_CHAT_URL = "https://yupp.ai/chat"
YUPP_API_TRPC = "https://yupp.ai/api/trpc"

# API Endpoints
CHAT_STREAM_ENDPOINT = "/chat"
MODEL_INFO_ENDPOINT = "/api/trpc/model.getModelInfoList,scribble.getScribbleByLabel"
REWARD_CLAIM_ENDPOINT = "/api/trpc/reward.claim"
FEEDBACK_RECORD_ENDPOINT = "/api/trpc/evals.recordModelFeedback"
DELETE_CHAT_ENDPOINT = "/api/trpc/chat.deleteChat"
PRIVATE_CHAT_ENDPOINT = "/api/trpc/chat.updateSharingSettings"
PRESIGNED_URL_ENDPOINT = "/api/trpc/chat.createPresignedURLForUpload"
ATTACHMENT_ENDPOINT = "/api/trpc/chat.createAttachmentForUploadedFile"
SIGNED_IMAGE_ENDPOINT = "/api/trpc/chat.getSignedImage"
CREDITS_GET_ENDPOINT = "/api/trpc/credits.getCredits"
TURN_ANNOTATIONS_ENDPOINT = "/api/trpc/evals.getTurnAnnotations"

# Default fallback NextAction tokens
NEXT_ACTION_TOKENS = {
    "new_conversation": "7f7de0a21bc8dc3cee8ba8b6de632ff16f769649dd",
    "existing_conversation": "7f9ec99a63cbb61f69ef18c0927689629bda07f1bf",
}

# Token extraction settings
TOKEN_CACHE_TTL = 3600  # 1 hour in seconds
MAX_EXTRACTION_RETRIES = 3
MIN_REQUIRED_TOKENS = 2

# Token extraction regex patterns
TOKEN_PATTERNS = [
    r'next-action["\']?\s*[:=]\s*["\']?([a-f0-9]{40,42})',
    r'"next-action"\s*:\s*"([a-f0-9]{40,42})"',
    r'"actionId"\s*:\s*"([a-f0-9]{40,42})"',
    r'nextAction["\']?\s*:\s*["\']?([a-f0-9]{40,42})',
    r'["\']?action["\']?\s*[:=]\s*["\']?([a-f0-9]{40,42})',
    r'["\']?new_conversation["\']?\s*[:=]\s*["\']?([a-f0-9]{40,42})',
    r'["\']?existing_conversation["\']?\s*[:=]\s*["\']?([a-f0-9]{40,42})',
    r'["\']?new["\']?\s*[:=]\s*["\']?([a-f0-9]{40,42})',
    r'["\']?existing["\']?\s*[:=]\s*["\']?([a-f0-9]{40,42})',
]

# Model settings
DEFAULT_MODEL_CREATED_TIMESTAMP = 1700000000  # Fallback timestamp for models

# Request settings
DEFAULT_TIMEOUT = 120
STREAM_TIMEOUT = 300
MAX_ERROR_COUNT = 3
ERROR_COOLDOWN = 300  # seconds
MAX_CACHE_SIZE = 1000

# HTTP Headers
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0"
)

# Cookie names
SESSION_TOKEN_COOKIE = "__Secure-yupp.session-token"

# Config file
CONFIG_FILE = "config.json"

# Supported model families
SUPPORTED_FAMILIES = {
    "GPT", "Claude", "Gemini", "Qwen", "DeepSeek", "Perplexity", "Kimi"
}

# Model tags
TAG_MAPPING = {
    "isPro": "☀️",
    "isMax": "🔥",
    "isNew": "🆕",
    "isLive": "🎤",
    "isAgent": "🤖",
    "isFast": "🚀",
    "isReasoning": "🧠",
    "isImageGeneration": "🎨",
}

# Reward and feedback settings
FEEDBACK_GOOD_REASONS = ["Helpful", "Interesting", "Accurate", "Clear", "Well explained"]
FEEDBACK_BAD_REASONS = ["Not helpful", "Inaccurate", "Unclear"]
# Feedback distribution (Option 3)
# 60%: One GOOD, one BAD
# 30%: Both GOOD
# 10%: One GOOD, other minimal/empty
FEEDBACK_PATTERN_ONE_GOOD_ONE_BAD = 0.60
FEEDBACK_PATTERN_BOTH_GOOD = 0.30
FEEDBACK_PATTERN_ONE_GOOD_MINIMAL = 0.10
# Timing settings for reward claiming
REWARD_CLAIM_MIN_DELAY = 1.0  # seconds
REWARD_CLAIM_MAX_DELAY = 3.0  # seconds
