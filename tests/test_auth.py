"""
Tests for auth module.
"""

import unittest
from unittest.mock import AsyncMock, patch

from yuppbridge import auth, state


class TestAuth(unittest.IsolatedAsyncioTestCase):
    """Test auth module."""
    
    def setUp(self):
        """Set up test."""
        state.reset_state()
    
    def tearDown(self):
        """Clean up."""
        state.reset_state()
    
    async def test_load_yupp_accounts_from_string(self):
        """Test loading accounts from token string."""
        tokens_str = "token1,token2,token3"
        
        await auth.load_yupp_accounts(tokens_str)
        
        accounts = state.get_accounts()
        self.assertEqual(len(accounts), 3)
        self.assertEqual(accounts[0].token, "token1")
        self.assertEqual(accounts[1].token, "token2")
        self.assertEqual(accounts[2].token, "token3")
    
    async def test_load_yupp_accounts_empty(self):
        """Test loading with empty string."""
        await auth.load_yupp_accounts("")
        
        accounts = state.get_accounts()
        self.assertEqual(len(accounts), 0)
    
    async def test_load_yupp_accounts_with_whitespace(self):
        """Test loading accounts with whitespace."""
        tokens_str = "  token1  ,  token2 ,token3  "
        
        await auth.load_yupp_accounts(tokens_str)
        
        accounts = state.get_accounts()
        self.assertEqual(len(accounts), 3)
        self.assertEqual(accounts[0].token, "token1")
    
    async def test_get_best_yupp_account(self):
        """Test getting best account."""
        # Load accounts
        await auth.load_yupp_accounts("token1,token2")
        
        account = await auth.get_best_yupp_account()
        
        self.assertIsNotNone(account)
        self.assertIn("token", account)
        self.assertEqual(account["is_valid"], True)
    
    async def test_get_best_yupp_account_no_accounts(self):
        """Test getting best account with no accounts."""
        # No accounts loaded
        
        account = await auth.get_best_yupp_account()
        
        self.assertIsNone(account)
    
    async def test_mark_account_error(self):
        """Test marking account error."""
        await auth.load_yupp_accounts("token1")
        
        account = await auth.get_best_yupp_account()
        await auth.mark_account_error(account)
        
        # Check error count increased
        accounts = state.get_accounts()
        self.assertEqual(accounts[0].error_count, 1)
    
    async def test_mark_account_success(self):
        """Test marking account success."""
        await auth.load_yupp_accounts("token1")
        
        # First mark an error
        account = await auth.get_best_yupp_account()
        await auth.mark_account_error(account)
        
        # Then mark success
        await auth.mark_account_success(account)
        
        # Check error count reset
        accounts = state.get_accounts()
        self.assertEqual(accounts[0].error_count, 0)
    
    async def test_account_rotation(self):
        """Test account rotation."""
        await auth.load_yupp_accounts("token1,token2,token3")
        
        # Get multiple accounts
        accounts_used = []
        for _ in range(5):
            account = await auth.get_best_yupp_account()
            if account:
                accounts_used.append(account["token"])
        
        # Should rotate through accounts
        self.assertGreater(len(set(accounts_used)), 1)
    
    def test_validate_token(self):
        """Test token validation."""
        # Valid tokens
        self.assertTrue(auth.validate_token("abc123def456" * 3))
        self.assertTrue(auth.validate_token("x" * 50))
        
        # Invalid tokens
        self.assertFalse(auth.validate_token(""))
        self.assertFalse(auth.validate_token(None))  # type: ignore
        self.assertFalse(auth.validate_token("short"))


if __name__ == "__main__":
    unittest.main()
