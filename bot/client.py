"""
Discord bot client setup.
Initializes the bot and registers commands.
"""

import discord
from discord import app_commands
from typing import Optional
import logging

from config import Config

logger = logging.getLogger(__name__)


class PuzzleBotClient(discord.Client):
    """Main Discord bot client."""
    
    def __init__(self):
        """Initialize bot with required intents."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.members = True
        
        super().__init__(intents=intents)
        
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        """Called when bot is starting up."""
        logger.info("Setting up bot...")
        
        # Sync commands with Discord
        await self.tree.sync()
        
        logger.info("Bot setup complete")


def create_bot() -> PuzzleBotClient:
    """
    Create and configure bot instance.
    
    Returns:
        Configured bot client
    """
    bot = PuzzleBotClient()
    return bot
