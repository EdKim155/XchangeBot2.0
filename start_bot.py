#!/usr/bin/env python3
"""
Script to run the Telegram bot continuously.
This script is meant to be run by Replit workflow system.
"""
import asyncio
import logging
import os
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log")
    ]
)

# Import the bot's main function
from bot import main, bot

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    logging.info("Signal received to stop the bot. Shutting down...")
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    try:
        logging.info("Starting Telegram bot...")
        # Print bot information
        logging.info(f"Bot username: {os.environ.get('BOT_USERNAME', 'Unknown')}")
        
        # Run the bot
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
    except Exception as e:
        logging.error(f"Bot stopped due to error: {e}")
        sys.exit(1)