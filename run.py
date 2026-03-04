#!/usr/bin/env python3
"""
YuppBridge Server Runner
Start the YuppBridge server.
"""
import os
import sys
import signal
import uvicorn
def signal_handler(sig, frame):
    """Handle Ctrl-C gracefully."""
    print("\n\n[Server] Shutting down gracefully...")
    sys.exit(0)
if __name__ == "__main__":
    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Check for debug mode
    debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"
    log_level = "debug" if debug_mode else "info"
    
    print("="*70)
    print("  YuppBridge Server")
    print("="*70)
    print(f"  Host: 0.0.0.0")
    print(f"  Port: 8000")
    print(f"  Debug: {debug_mode}")
    print(f"  Log Level: {log_level}")
    print("="*70)
    print()
    print("Press Ctrl-C to stop the server")
    print()
    
    # Run the server
    try:
        uvicorn.run(
            "src.main:app",
            host="0.0.0.0",
            port=8000,
            reload=debug_mode,  # Auto-reload in debug mode
            log_level=log_level
        )
    except KeyboardInterrupt:
        print("\n[Server] Stopped by user")
        sys.exit(0)
"""
YuppBridge Server Runner

Start the YuppBridge server.
"""

import sys
import uvicorn

if __name__ == "__main__":
    # Run the server
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
