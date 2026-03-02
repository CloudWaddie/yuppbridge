"""
Test utilities for YuppBridge.

Base test class and common fixtures.
"""

import asyncio
import json
import os
import tempfile
import unittest
from typing import Any, Dict, Optional
from unittest import IsolatedAsyncioTestCase


class BaseBridgeTest(IsolatedAsyncioTestCase):
    """
    Base test class for YuppBridge tests.
    
    Provides:
    - Temp config file management
    - State cleanup between tests
    - Async test support
    """
    
    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        
        # Create temp config file
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "config.json")
        
        # Write default config
        self.default_config = {
            "auth_tokens": ["test_token_1", "test_token_2"],
            "api_keys": [
                {"name": "test-key", "key": "sk-test123", "rpm": 60}
            ],
            "password": "testpass",
            "proxy": None,
            "max_error_count": 3,
            "error_cooldown": 300,
        }
        
        with open(self.config_file, "w") as f:
            json.dump(self.default_config, f)
        
        # Import and reset state
        from yuppbridge import state, auth, token_extractor
        state.reset_state()
        token_extractor.reset_token_extractor()
    
    def tearDown(self):
        """Clean up after test."""
        super().tearDown()
        
        # Clean up temp files
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        
        # Reset state
        from yuppbridge import state, token_extractor
        state.reset_state()
        token_extractor.reset_token_extractor()
    
    def get_test_config(self) -> Dict[str, Any]:
        """Get the test config dict."""
        return self.default_config.copy()
    
    def write_test_config(self, config: Dict[str, Any]) -> None:
        """Write config to temp file."""
        with open(self.config_file, "w") as f:
            json.dump(config, f)


class FakeStreamResponse:
    """Fake stream response for testing."""
    
    def __init__(
        self,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        lines: Optional[list] = None,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self._lines = lines or []
        self._index = 0
    
    def raise_for_status(self):
        """Raise if status is error."""
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")
    
    def iter_lines(self):
        """Iterate over lines."""
        for line in self._lines:
            yield line
    
    def json(self):
        """Return JSON."""
        return {}


class FakeScraper:
    """Fake cloudscraper for testing."""
    
    def __init__(
        self,
        response_status: int = 200,
        response_text: str = "",
        response_json: Optional[Dict[str, Any]] = None,
    ):
        self.response_status = response_status
        self.response_text = response_text
        self.response_json = response_json or {}
        self.cookies = {}
        self.headers = {}
        self.proxies = None
    
    def get(self, url, **kwargs):
        """Fake GET request."""
        return FakeResponse(
            self.response_status,
            self.response_text,
            self.response_json,
        )
    
    def post(self, url, **kwargs):
        """Fake POST request."""
        return FakeResponse(
            self.response_status,
            self.response_text,
            self.response_json,
        )


class FakeResponse:
    """Fake response object."""
    
    def __init__(
        self,
        status_code: int,
        text: str = "",
        json_data: Optional[Dict[str, Any]] = None,
    ):
        self.status_code = status_code
        self.text = text
        self._json_data = json_data or {}
    
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")
    
    def json(self):
        return self._json_data
