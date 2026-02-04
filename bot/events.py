"""
Discord bot event handlers.
"""

import discord
import logging

logger = logging.getLogger(__name__)


def register_events(client: discord.Client):
    """
    Register event handlers for the bot.
    
    Args:
        client: Discord client instance
    """
    
    @client.event
    async def on_ready():
        """Called when bot is ready."""
        logger.info(f"Bot logged in as {client.user}")
        logger.info(f"Connected to {len(client.guilds)} guilds")
    
    @client.event
    async def on_error(event: str, *args, **kwargs):
        """Called when an error occurs."""
        logger.error(f"Error in event {event}", exc_info=True)
    
    @client.event
    async def on_command_error(interaction: discord.Interaction, error: Exception):
        """Called when a command error occurs."""
        logger.error(f"Command error: {error}", exc_info=True)
        
        # Send user-friendly error message
        if interaction.response.is_done():
            await interaction.followup.send(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ An error occurred: {str(error)}",
                ephemeral=True
            )
