"""
Tests for token_extractor module.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from yuppbridge import constants, state, token_extractor


class TestTokenExtractor(unittest.IsolatedAsyncioTestCase):
    """Test TokenExtractor class."""
    
    def setUp(self):
        """Set up test."""
        state.reset_state()
        token_extractor.reset_token_extractor()
    
    def tearDown(self):
        """Clean up."""
        state.reset_state()
        token_extractor.reset_token_extractor()
    
    async def test_get_token_fallback(self):
        """Test getting fallback token."""
        ext = token_extractor.TokenExtractor()
        
        # Should return fallback token
        result = await ext.get_token("new_conversation")
        
        self.assertEqual(result, constants.NEXT_ACTION_TOKENS["new_conversation"])
    
    async def test_get_token_fallback_existing(self):
        """Test getting fallback for existing conversation."""
        ext = token_extractor.TokenExtractor()
        
        result = await ext.get_token("existing_conversation")
        
        self.assertEqual(result, constants.NEXT_ACTION_TOKENS["existing_conversation"])
    
    async def test_get_token_cached(self):
        """Test getting cached token."""
        from datetime import datetime
        from yuppbridge.token_extractor import TokenCache
        
        cache = TokenCache()
        cache.tokens = {
            "new_conversation": "cached_token_12345",
            "existing_conversation": "cached_token_67890",
        }
        cache.last_updated = datetime.now()
        
        ext = token_extractor.TokenExtractor()
        ext._cache = cache
        
        result = await ext.get_token("new_conversation")
        
        self.assertEqual(result, "cached_token_12345")
    
    async def test_mark_token_failed_triggers_extraction(self):
        """Test that marking token failed triggers extraction."""
        ext = token_extractor.TokenExtractor()
        
        # Mark a fallback token as failed
        await ext.mark_token_failed(
            "new_conversation",
            constants.NEXT_ACTION_TOKENS["new_conversation"]
        )
        
        # Should have incremented failed attempts
        self.assertEqual(ext._cache.failed_attempts, 1)
    
    async def test_mark_token_failed_cached(self):
        """Test marking cached token as failed."""
        from datetime import datetime
        from yuppbridge.token_extractor import TokenCache
        
        cache = TokenCache()
        cache.tokens = {
            "new_conversation": "test_token",
            "existing_conversation": "test_token2",
        }
        cache.last_updated = datetime.now()
        
        ext = token_extractor.TokenExtractor()
        ext._cache = cache
        
        # Mark the cached token as failed
        await ext.mark_token_failed("new_conversation", "test_token")
        
        self.assertEqual(ext._cache.failed_attempts, 1)


class TestTokenCache(unittest.TestCase):
    """Test TokenCache class."""
    
    def test_is_expired(self):
        """Test cache expiration."""
        from datetime import datetime, timedelta
        from yuppbridge.token_extractor import TokenCache
        
        # Empty cache is expired
        cache = TokenCache()
        self.assertTrue(cache.is_expired())
        
        # Fresh cache is not expired
        cache.last_updated = datetime.now()
        self.assertFalse(cache.is_expired())
        
        # Old cache is expired
        cache.last_updated = datetime.now() - timedelta(seconds=constants.TOKEN_CACHE_TTL + 1)
        self.assertTrue(cache.is_expired())
    
    def test_is_valid(self):
        """Test cache validity."""
        from datetime import datetime
        from yuppbridge.token_extractor import TokenCache
        
        # Empty cache is invalid
        cache = TokenCache()
        self.assertFalse(cache.is_valid())
        
        # Valid cache
        cache.tokens = {
            "new_conversation": "token1",
            "existing_conversation": "token2",
        }
        cache.last_updated = datetime.now()
        self.assertTrue(cache.is_valid())
        
        # Invalid - missing tokens
        cache.tokens = {"new_conversation": "token1"}
        self.assertFalse(cache.is_valid())
        
        # Invalid - expired
        cache.tokens = {
            "new_conversation": "token1",
            "existing_conversation": "token2",
        }
        cache.last_updated = None
        self.assertFalse(cache.is_valid())


class TestGetTokenExtractor(unittest.IsolatedAsyncioTestCase):
    """Test get_token_extractor function."""
    
    def setUp(self):
        """Set up test."""
        token_extractor.reset_token_extractor()
    
    def tearDown(self):
        """Clean up."""
        token_extractor.reset_token_extractor()
    
    def test_creates_new_extractor(self):
        """Test creating new extractor."""
        ext = token_extractor.get_token_extractor()
        
        self.assertIsNotNone(ext)
        self.assertIsInstance(ext, token_extractor.TokenExtractor)
    
    def test_returns_same_instance(self):
        """Test singleton behavior."""
        ext1 = token_extractor.get_token_extractor()
        ext2 = token_extractor.get_token_extractor()
        
        self.assertIs(ext1, ext2)
    
    def test_reset_creates_new_instance(self):
        """Test reset creates new instance."""
        ext1 = token_extractor.get_token_extractor()
        
        token_extractor.reset_token_extractor()
        
        ext2 = token_extractor.get_token_extractor()
        
        self.assertIsNot(ext1, ext2)


class TestExtractTokensFromHtml(unittest.IsolatedAsyncioTestCase):
    """Test token extraction from HTML."""
    
    async def test_extract_tokens_from_html(self):
        """Test extracting tokens from HTML."""
        ext = token_extractor.TokenExtractor()
        
        html = '''
        <script>
            next-action: "7f7de0a21bc8dc3cee8ba8b6de632ff16f769649dd"
            nextAction: "7f9ec99a63cbb61f69ef18c0927689629bda07f1bf"
        </script>
        '''
        
        tokens = ext._extract_tokens_from_html(html)
        
        # Should find at least one token
        self.assertGreater(len(tokens), 0)
    
    async def test_filter_invalid_tokens(self):
        """Test filtering invalid tokens."""
        ext = token_extractor.TokenExtractor()
        
        html = '''
        <script>
            next-action: "invalid_short"
            next-action: "7f7de0a21bc8dc3cee8ba8b6de632ff16f769649dd"
        </script>
        '''
        
        tokens = ext._extract_tokens_from_html(html)
        
        # Should only have valid tokens
        for token in tokens:
            self.assertGreaterEqual(len(token), 40)
            self.assertLessEqual(len(token), 42)


if __name__ == "__main__":
    unittest.main()
