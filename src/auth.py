"""
Auth token management for YuppBridge.

Handles token loading, validation, round-robin selection, and error tracking.
"""

import os
import time
from typing import Any, Dict, List, Optional

from . import config, constants, state


async def load_yupp_accounts(tokens_str: Optional[str] = None) -> None:
    """
    Load Yupp accounts from token string or config.
    
    Tokens can be comma-separated in the string or loaded from config.
    """
    if tokens_str is None:
        cfg = config.get_config()
        tokens_str = os.getenv("YUPP_API_KEY") or os.getenv("YUPP_TOKENS")
        
        # Also check config
        if not tokens_str:
            tokens = config.get_auth_tokens(cfg)
            if tokens:
                tokens_str = ",".join(tokens)
    
    if not tokens_str:
        return
    
    tokens = [token.strip() for token in tokens_str.split(",") if token.strip()]
    accounts = [state.Account(token) for token in tokens]
    state.set_accounts(accounts)


async def get_best_yupp_account() -> Optional[Dict[str, Any]]:
    """
    Get the best available account using round-robin with error tracking.
    
    Returns account with lowest error count that hasn't been used recently,
    or None if no valid accounts available.
    """
    accounts = state.get_accounts()
    if not accounts:
        return None
    
    max_error_count = int(os.getenv("MAX_ERROR_COUNT", str(constants.MAX_ERROR_COUNT)))
    error_cooldown = int(os.getenv("ERROR_COOLDOWN", str(constants.ERROR_COOLDOWN)))
    
    async with state.account_rotation_lock:
        now = time.time()
        
        # Filter valid accounts
        valid_accounts = [
            acc for acc in accounts
            if acc.is_valid and (
                acc.error_count < max_error_count or
                now - acc.last_used > error_cooldown
            )
        ]
        
        if not valid_accounts:
            return None
        
        # Reset error count for accounts past cooldown
        for acc in valid_accounts:
            if acc.error_count >= max_error_count and now - acc.last_used > error_cooldown:
                acc.error_count = 0
        
        # Sort by last_used and error_count
        valid_accounts.sort(key=lambda x: (x.last_used, x.error_count))
        
        account = valid_accounts[0]
        account.last_used = now
        
        return {
            "token": account.token,
            "is_valid": account.is_valid,
            "error_count": account.error_count,
            "last_used": account.last_used,
        }


async def mark_account_error(account: Dict[str, Any]) -> None:
    """Mark an account as having an error."""
    accounts = state.get_accounts()
    token = account.get("token")
    
    async with state.account_rotation_lock:
        for acc in accounts:
            if acc.token == token:
                acc.error_count += 1
                if acc.error_count >= int(os.getenv("MAX_ERROR_COUNT", str(constants.MAX_ERROR_COUNT))):
                    acc.is_valid = False
                break


async def mark_account_success(account: Dict[str, Any]) -> None:
    """Mark an account as successful (reset error count)."""
    accounts = state.get_accounts()
    token = account.get("token")
    
    async with state.account_rotation_lock:
        for acc in accounts:
            if acc.token == token:
                acc.error_count = 0
                acc.is_valid = True
                break


def validate_token(token: str) -> bool:
    """Validate a token format."""
    if not token:
        return False
    # Basic validation - token should be a reasonable length
    return len(token) >= 20
