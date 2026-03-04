"""
In-memory shared state for YuppBridge.
"""

import asyncio
import time
from typing import Any, Dict, List, Optional


# Account state
class Account:
    def __init__(self, token: str):
        self.token = token
        self.is_valid = True
        self.error_count = 0
        self.last_used = 0.0


# Global state
accounts: List[Account] = []
account_rotation_lock = asyncio.Lock()
current_account_index = 0

# Chat sessions per API key
chat_sessions: Dict[str, List[Dict[str, Any]]] = {}

# Token extractor state
_token_extractor: Optional[Any] = None

# Images cache
ImagesCache: Dict[str, dict] = {}
MAX_CACHE_SIZE = 1000

# Credit balance tracking per account
credit_balances: Dict[str, int] = {}  # token -> balance


def get_accounts() -> List[Account]:
    """Get all accounts."""
    global accounts
    return accounts


def set_accounts(new_accounts: List[Account]) -> None:
    """Set accounts list."""
    global accounts
    accounts = new_accounts


def get_current_index() -> int:
    """Get current account index."""
    global current_account_index
    return current_account_index


def set_current_index(idx: int) -> None:
    """Set current account index."""
    global current_account_index
    current_account_index = idx


def increment_index() -> None:
    """Increment account index with wraparound."""
    global current_account_index
    if accounts:
        current_account_index = (current_account_index + 1) % len(accounts)


def reset_state() -> None:
    """Reset all state (for testing)."""
    global accounts, current_account_index, chat_sessions, ImagesCache, _token_extractor, credit_balances
    accounts = []
    current_account_index = 0
    chat_sessions = {}
    ImagesCache = {}
    _token_extractor = None
    credit_balances = {}


def evict_cache_if_needed() -> None:
    """Evict old cache entries if over limit."""
    global ImagesCache
    if len(ImagesCache) > MAX_CACHE_SIZE:
        keys_to_remove = list(ImagesCache.keys())[:len(ImagesCache) - MAX_CACHE_SIZE + 100]
        for key in keys_to_remove:
            del ImagesCache[key]


def set_token_extractor(extractor: Any) -> None:
    """Set token extractor instance."""
    global _token_extractor
    _token_extractor = extractor


def get_token_extractor() -> Optional[Any]:
    """Get token extractor instance."""
    global _token_extractor
    return _token_extractor


def get_credit_balance(token: str) -> Optional[int]:
    """Get credit balance for account."""
    global credit_balances
    return credit_balances.get(token)


def set_credit_balance(token: str, balance: int) -> None:
    """Set credit balance for account."""
    global credit_balances
    credit_balances[token] = balance


def update_credit_balance(token: str, balance: int) -> None:
    """Update credit balance for account (alias for set_credit_balance)."""
    set_credit_balance(token, balance)
