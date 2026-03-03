"""
YuppBridge - OpenAI-compatible API bridge to Yupp AI (yupp.ai)
"""

# Import submodules
from . import auth, config, constants, state, token_extractor, transport, exceptions

# Import app lazily to avoid circular imports
def __getattr__(name):
    if name == "app":
        from .main import app
        return app
    if name == "get_config":
        from .main import get_config
        return get_config
    if name == "save_config":
        from .main import save_config
        return save_config
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__version__ = "0.2.0"

__all__ = [
    "auth",
    "config", 
    "constants",
    "state",
    "token_extractor",
    "transport",
    "exceptions",
]
