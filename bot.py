"""
Main entry point for Discord Puzzle Trading Bot.
"""

import asyncio
import logging
import signal
import sys

from config import Config
from db.database import init_database, close_database
from bot.client import create_bot
from bot.events import register_events
from bot.commands.start import register_start_command
from bot.commands.scan import register_scan_command
from bot.commands.inventory import register_inventory_command
from bot.commands.need import register_need_command
from bot.commands.whohas import register_whohas_command
from bot.commands.used import register_used_command
from bot.commands.fix import register_fix_command
from bot.commands.history import register_history_command
from bot.commands.unscan import register_unscan_command

logger = logging.getLogger(__name__)


async def main():
    """Main application entry point."""
    
    logger.info("Starting Discord Puzzle Trading Bot...")
    
    # Initialize database
    try:
        await init_database(Config.DATABASE_URL)
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        sys.exit(1)
    
    # Create bot
    bot = create_bot()
    
    # Register events
    register_events(bot)
    
    # Register commands
    register_start_command(bot.tree)
    register_scan_command(bot.tree)
    register_inventory_command(bot.tree)
    register_need_command(bot.tree)
    register_whohas_command(bot.tree)
    register_used_command(bot.tree)
    register_fix_command(bot.tree)
    register_history_command(bot.tree)
    register_unscan_command(bot.tree)
    
    logger.info("Commands registered")
    
    # Setup graceful shutdown
    async def shutdown(sig):
        """Graceful shutdown handler."""
        logger.info(f"Received signal {sig.name}, shutting down...")
        await bot.close()
        await close_database()
        logger.info("Shutdown complete")
    
    # Register signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s)))
    
    # Start bot
    try:
        await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
    finally:
        await close_database()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
