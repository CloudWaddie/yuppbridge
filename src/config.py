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
def ensure_config_exists(config_file: Optional[str] = None) -> bool:
    """
    Ensure config file exists. If not, create it with interactive wizard.
    Returns True if config was created, False if it already existed.
    """
    cfg_file = config_file or _constants.CONFIG_FILE
    
    if os.path.exists(cfg_file):
        return False
    
    print("="*70)
    print("  YuppBridge Configuration Wizard")
    print("="*70)
    print()
    print("Welcome! Let's set up YuppBridge in a few simple steps.")
    print()
    
    # Step 1: Yupp AI Token
    print("-" * 70)
    print("Step 1 of 3: Yupp AI Session Token")
    print("-" * 70)
    print()
    print("To use YuppBridge, you need a session token from Yupp AI.")
    print()
    print("How to get your token:")
    print("  1. Open https://yupp.ai in your browser")
    print("  2. Log in to your account")
    print("  3. Send a test message in the chat")
    print("  4. Press F12 to open Developer Tools")
    print("  5. Go to: Application -> Cookies -> https://yupp.ai")
    print("  6. Find '__Secure-yupp.session-token' and copy its value")
    print()
    
    yupp_token = input("> Enter your Yupp session token (or press Enter to skip): ").strip()
    
    if yupp_token:
        print("  [OK] Token saved!")
    else:
        print("  [SKIP] You can add it later to config.json or use YUPP_API_KEY env var")
    print()
    
    # Step 2: API Key
    print("-" * 70)
    print("Step 2 of 3: API Key Generation")
    print("-" * 70)
    print()
    print("YuppBridge needs an API key to authenticate your requests.")
    print("We'll generate a secure one for you.")
    print()
    
    import secrets
    api_key = f"sk-{secrets.token_urlsafe(32)}"
    
    print(f"  Generated API Key: {api_key}")
    print()
    print("  [INFO] Save this key! You'll need it to make requests.")
    print()
    
    input("Press Enter to continue...")
    print()
    
    # Step 3: Dashboard Password
    print("-" * 70)
    print("Step 3 of 3: Dashboard Password")
    print("-" * 70)
    print()
    print("Set a password to protect the admin dashboard.")
    print()
    
    dashboard_password = input("> Enter dashboard password (default: 'admin'): ").strip() or "admin"
    print("  [OK] Password set!")
    print()
    
    # Create config
    config = {
        "auth_tokens": [yupp_token] if yupp_token else [],
        "api_keys": [
            {
                "name": "default",
                "key": api_key,
                "rpm": 60
            }
        ],
        "password": dashboard_password,
        "proxy": None,
        "max_error_count": 3,
        "error_cooldown": 300
    }
    
    # Save config
    print("-" * 70)
    print("Saving Configuration...")
    print("-" * 70)
    print()
    
    if save_config(config, cfg_file):
        print(f"  [OK] Configuration saved to: {cfg_file}")
        print()
        print("="*70)
        print("  Setup Complete!")
        print("="*70)
        print()
        print("Quick Start Guide:")
        print()
        print("  1. Start the server:")
        print("     python src/main.py")
        print()
        print("  2. Test the API:")
        print(f"     curl -H 'Authorization: Bearer {api_key}' \\")
        print("          http://localhost:8000/health")
        print()
        print("  3. Make a chat request:")
        print(f"     curl -X POST http://localhost:8000/api/v1/chat/completions \\")
        print(f"          -H 'Authorization: Bearer {api_key}' \\")
        print("          -H 'Content-Type: application/json' \\")
        print("          -d '{\"model\": \"gpt-4o\", \"messages\": [{\"role\": \"user\", \"content\": \"Hello!\"}]}'")
        print()
        print("  4. Check your credits:")
        print(f"     curl -H 'Authorization: Bearer {api_key}' \\")
        print("          http://localhost:8000/api/v1/credits")
        print()
        
        if not yupp_token:
            print("[WARNING] No Yupp token was provided.")
            print("  Add it to config.json or set the YUPP_API_KEY environment variable.")
            print()
        
        print("Documentation: See README.md for more details")
        print()
        print("="*70)
        print()
        return True
    else:
        print("  [ERROR] Failed to save configuration")
        print()
        return False
