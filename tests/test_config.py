"""
Tests for config module.
"""

import json
import os
import tempfile
import unittest

from yuppbridge import config


class TestConfig(unittest.TestCase):
    """Test config module."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "config.json")
    
    def tearDown(self):
        """Clean up."""
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_default_config(self):
        """Test default config generation."""
        cfg = config._default_config()
        
        self.assertIn("auth_tokens", cfg)
        self.assertIn("api_keys", cfg)
        self.assertIn("password", cfg)
        self.assertEqual(cfg["max_error_count"], 3)
        self.assertEqual(cfg["error_cooldown"], 300)
    
    def test_apply_defaults(self):
        """Test applying defaults to partial config."""
        partial = {"auth_tokens": ["token1"]}
        cfg = config._apply_config_defaults(partial)
        
        self.assertEqual(cfg["auth_tokens"], ["token1"])
        self.assertIn("api_keys", cfg)
        self.assertIn("password", cfg)
    
    def test_save_and_load_config(self):
        """Test saving and loading config."""
        test_config = {
            "auth_tokens": ["token1", "token2"],
            "api_keys": [{"name": "test", "key": "sk-123"}],
            "password": "secret",
        }
        
        # Save
        result = config.save_config(test_config, self.config_file)
        self.assertTrue(result)
        
        # Load
        loaded = config.get_config(self.config_file)
        self.assertEqual(loaded["auth_tokens"], ["token1", "token2"])
        self.assertEqual(loaded["api_keys"], [{"name": "test", "key": "sk-123"}])
    
    def test_load_nonexistent_file(self):
        """Test loading nonexistent file returns defaults."""
        cfg = config.get_config("/nonexistent/path/config.json")
        
        self.assertIn("auth_tokens", cfg)
        self.assertIn("api_keys", cfg)
    
    def test_get_auth_tokens(self):
        """Test getting auth tokens."""
        test_config = {
            "auth_tokens": ["token1", "token2"],
        }
        
        tokens = config.get_auth_tokens(test_config)
        self.assertEqual(tokens, ["token1", "token2"])
    
    def test_get_auth_tokens_legacy(self):
        """Test getting auth tokens with legacy single token."""
        test_config = {
            "auth_token": "legacy_token",
            "auth_tokens": ["token1"],
        }
        
        tokens = config.get_auth_tokens(test_config)
        # Legacy should be prepended
        self.assertIn("legacy_token", tokens)
    
    def test_save_auth_tokens(self):
        """Test saving auth tokens."""
        tokens = ["token1", "token2", "token3"]
        
        result = config.save_auth_tokens(tokens, self.config_file)
        self.assertTrue(result)
        
        # Verify
        cfg = config.get_config(self.config_file)
        self.assertEqual(cfg["auth_tokens"], tokens)
        # Legacy should be removed
        self.assertNotIn("auth_token", cfg)


if __name__ == "__main__":
    unittest.main()
