"""
Tests for state module.
"""

import unittest

from yuppbridge import state


class TestState(unittest.TestCase):
    """Test state module."""
    
    def setUp(self):
        """Set up test."""
        state.reset_state()
    
    def tearDown(self):
        """Clean up."""
        state.reset_state()
    
    def test_default_state(self):
        """Test default state values."""
        self.assertEqual(state.get_accounts(), [])
        self.assertEqual(state.get_current_index(), 0)
        self.assertEqual(state.get_token_extractor(), None)
    
    def test_set_accounts(self):
        """Test setting accounts."""
        accounts = [state.Account("token1"), state.Account("token2")]
        
        state.set_accounts(accounts)
        
        self.assertEqual(len(state.get_accounts()), 2)
        self.assertEqual(state.get_accounts()[0].token, "token1")
    
    def test_increment_index(self):
        """Test incrementing index with wraparound."""
        # Add some accounts
        accounts = [
            state.Account("token1"),
            state.Account("token2"),
            state.Account("token3"),
        ]
        state.set_accounts(accounts)
        
        # Increment a few times
        state.increment_index()
        self.assertEqual(state.get_current_index(), 1)
        
        state.increment_index()
        self.assertEqual(state.get_current_index(), 2)
        
        state.increment_index()
        # Should wrap around
        self.assertEqual(state.get_current_index(), 0)
    
    def test_images_cache(self):
        """Test images cache."""
        # Add to cache
        state.ImagesCache["key1"] = {"data": "value1"}
        state.ImagesCache["key2"] = {"data": "value2"}
        
        self.assertEqual(len(state.ImagesCache), 2)
        self.assertEqual(state.ImagesCache["key1"]["data"], "value1")
    
    def test_evict_cache(self):
        """Test cache eviction."""
        # Fill cache beyond limit
        for i in range(state.MAX_CACHE_SIZE + 100):
            state.ImagesCache[f"key{i}"] = {"data": f"value{i}"}
        
        # Trigger eviction
        state.evict_cache_if_needed()
        
        # Should be reduced
        self.assertLess(len(state.ImagesCache), state.MAX_CACHE_SIZE + 100)
    
    def test_token_extractor_set_get(self):
        """Test token extractor set/get."""
        extractor = object()
        
        state.set_token_extractor(extractor)
        
        self.assertEqual(state.get_token_extractor(), extractor)


class TestAccount(unittest.TestCase):
    """Test Account class."""
    
    def test_account_creation(self):
        """Test creating an account."""
        acc = state.Account("test_token")
        
        self.assertEqual(acc.token, "test_token")
        self.assertEqual(acc.is_valid, True)
        self.assertEqual(acc.error_count, 0)
        self.assertEqual(acc.last_used, 0.0)
    
    def test_account_error_count(self):
        """Test error counting."""
        acc = state.Account("test_token")
        
        acc.error_count = 5
        self.assertEqual(acc.error_count, 5)


if __name__ == "__main__":
    unittest.main()
