#!/usr/bin/env python3
"""
Daemon script to run the Telegram bot in a persistent mode.
This script is meant to be run by a workflow.
"""
import asyncio
import logging
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
from bot import main

if __name__ == "__main__":
    try:
        logging.info("Starting bot daemon...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot daemon stopped by user.")
    except Exception as e:
        logging.error(f"Bot daemon stopped due to error: {e}")
        sys.exit(1)