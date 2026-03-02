"""
Config file I/O for YuppBridge.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import constants as _constants


def get_config(config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Load config from JSON file.
    
    Returns default config if file doesn't exist.
    """
    cfg_file = config_file or _constants.CONFIG_FILE
    
    if not os.path.exists(cfg_file):
        return _default_config()
    
    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            config = json.load(f)
            return _apply_config_defaults(config)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Config] Failed to load config: {e}")
        return _default_config()


def save_config(config: Dict[str, Any], config_file: Optional[str] = None) -> bool:
    """
    Save config to JSON file.
    """
    cfg_file = config_file or _constants.CONFIG_FILE
    
    try:
        # Create directory if needed
        Path(cfg_file).parent.mkdir(parents=True, exist_ok=True)
        
        with open(cfg_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except IOError as e:
        print(f"[Config] Failed to save config: {e}")
        return False


def _default_config() -> Dict[str, Any]:
    """Return default config."""
    return {
        "auth_tokens": [],
        "api_keys": [],
        "password": "",
        "proxy": None,
        "max_error_count": 3,
        "error_cooldown": 300,
    }


def _apply_config_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply defaults to config, preserving existing values."""
    defaults = _default_config()
    
    for key, value in defaults.items():
        if key not in config:
            config[key] = value
    
    # Ensure required keys exist
    if "auth_tokens" not in config:
        config["auth_tokens"] = []
    if "api_keys" not in config:
        config["api_keys"] = []
    
    return config


def get_models(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Get API keys from config."""
    cfg = config or get_config()
    return cfg.get("api_keys", [])


def save_models(models: List[Dict[str, Any]], config_file: Optional[str] = None) -> bool:
    """Save API keys to config."""
    cfg = get_config(config_file)
    cfg["api_keys"] = models
    return save_config(cfg, config_file)


def get_auth_tokens(config: Optional[Dict[str, Any]] = None) -> List[str]:
    """Get auth tokens from config."""
    cfg = config or get_config()
    tokens = cfg.get("auth_tokens", [])
    
    # Support legacy single token
    legacy_token = cfg.get("auth_token")
    if legacy_token and legacy_token not in tokens:
        tokens.insert(0, legacy_token)
    
    return [t for t in tokens if t]


def save_auth_tokens(tokens: List[str], config_file: Optional[str] = None) -> bool:
    """Save auth tokens to config."""
    cfg = get_config(config_file)
    cfg["auth_tokens"] = tokens
    # Remove legacy if present
    if "auth_token" in cfg:
        del cfg["auth_token"]
    return save_config(cfg, config_file)
