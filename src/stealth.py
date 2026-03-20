"""
Stealth transport layer using Scrapling (Patchright) for YuppBridge.
Handles Kasada protection by maintaining a persistent browser context.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from scrapling import StealthCrawler
from . import constants

logger = logging.getLogger("yuppbridge.stealth")

class StealthFetcher:
    """
    Maintains a persistent Patchright browser context to generate Kasada headers.
    """
    def __init__(self):
        self.crawler = None
        self._lock = asyncio.Lock()

    async def start(self):
        """Initialize the browser context."""
        async with self._lock:
            if self.crawler:
                return
            
            logger.info("Initializing StealthFetcher with Patchright...")
            try:
                # Scrapling with Patchright
                self.crawler = StealthCrawler(
                    engine="patchright",
                    headless=True,
                    allow_images=False,
                )
                # Initial page load to trigger Kasada and establish session
                self.crawler.get(
                    constants.YUPP_BASE_URL,
                    headers={"User-Agent": constants.DEFAULT_USER_AGENT}
                )
                logger.info("StealthFetcher initialized successfully with Patchright")
            except Exception as e:
                logger.error(f"Failed to initialize StealthFetcher: {e}")
                self.crawler = None
                raise

    async def close(self):
        """Clean up the browser context."""
        async with self._lock:
            if self.crawler:
                logger.info("Closing StealthFetcher browser...")
                try:
                    if hasattr(self.crawler, 'kill'):
                        self.crawler.kill()
                    elif hasattr(self.crawler, 'close'):
                        self.crawler.close()
                    self.crawler = None
                except Exception as e:
                    logger.error(f"Error closing StealthFetcher: {e}")

    def is_active(self) -> bool:
        """Check if the browser context is active."""
        return self.crawler is not None

    async def post(
        self, 
        url: str, 
        json_data: Any, 
        headers: Dict[str, str], 
        timeout: int = 300
    ) -> Any:
        """
        Perform a POST request using the browser context to ensure Kasada headers are present.
        """
        if not self.crawler:
            await self.start()

        async with self._lock:
            logger.debug(f"Stealth POST to {url}")
            # Ensure headers include our consistent User-Agent
            request_headers = headers.copy()
            if "User-Agent" not in request_headers:
                request_headers["User-Agent"] = constants.DEFAULT_USER_AGENT
                
            try:
                # The crawler naturally handles the Kasada VM execution and header generation
                response = self.crawler.post(
                    url,
                    json=json_data,
                    headers=request_headers,
                )
                
                # Check for Kasada failure (often 403)
                if response.status_code == 403:
                    logger.warning("Kasada challenge failed (403), refreshing context and retrying...")
                    self.crawler.get(
                        constants.YUPP_BASE_URL,
                        headers={"User-Agent": constants.DEFAULT_USER_AGENT}
                    )
                    # Retry once after refresh
                    response = self.crawler.post(
                        url,
                        json=json_data,
                        headers=request_headers
                    )

                return response
            except Exception as e:
                logger.error(f"Stealth POST error: {e}")
                raise

# Global instance
_stealth_fetcher: Optional[StealthFetcher] = None

def get_stealth_fetcher() -> StealthFetcher:
    global _stealth_fetcher
    if _stealth_fetcher is None:
        _stealth_fetcher = StealthFetcher()
    return _stealth_fetcher
