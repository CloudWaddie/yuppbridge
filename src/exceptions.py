"""
Custom exceptions for YuppBridge.
"""

from typing import Optional


class YuppBridgeException(Exception):
    """Base exception for YuppBridge."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_type: str = "internal_error",
    ):
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        super().__init__(message)


class NoValidAccountException(YuppBridgeException):
    """Raised when no valid Yupp account is available."""
    
    def __init__(self, message: Optional[str] = None):
        super().__init__(
            message=message or "No valid Yupp accounts available",
            status_code=503,
            error_type="no_account_available",
        )


class TokenExtractionException(YuppBridgeException):
    """Raised when token extraction fails."""
    
    def __init__(self, message: Optional[str] = None):
        super().__init__(
            message=message or "Failed to extract NextAction token",
            status_code=502,
            error_type="token_extraction_failed",
        )


class AuthenticationException(YuppBridgeException):
    """Raised when authentication fails."""
    
    def __init__(self, message: Optional[str] = None):
        super().__init__(
            message=message or "Authentication failed",
            status_code=401,
            error_type="authentication_failed",
        )


class RateLimitException(YuppBridgeException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message: Optional[str] = None):
        super().__init__(
            message=message or "Rate limit exceeded",
            status_code=429,
            error_type="rate_limit_exceeded",
        )


class ValidationException(YuppBridgeException):
    """Raised when request validation fails."""
    
    def __init__(self, message: Optional[str] = None):
        super().__init__(
            message=message or "Request validation failed",
            status_code=400,
            error_type="validation_failed",
        )


class ConfigurationException(YuppBridgeException):
    """Raised when configuration is invalid."""
    
    def __init__(self, message: Optional[str] = None):
        super().__init__(
            message=message or "Invalid configuration",
            status_code=500,
            error_type="invalid_configuration",
        )
