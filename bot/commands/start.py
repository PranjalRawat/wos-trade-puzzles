"""
/start command - Onboarding and help.
"""

import discord
from discord import app_commands
import logging

logger = logging.getLogger(__name__)


def register_start_command(tree: app_commands.CommandTree):
    """Register /start command."""
    
    @tree.command(name="start", description="Learn how to use the Puzzle Trading Bot")
    async def start_command(interaction: discord.Interaction):
        """Show onboarding message."""
        
        embed = discord.Embed(
            title="🧩 Welcome to Puzzle Trading Bot!",
            description="I help you coordinate puzzle piece trades with your community.",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📸 How It Works",
            value=(
                "1. Take screenshots of your puzzle inventory in-game\n"
                "2. Upload them using `/scan`\n"
                "3. I'll detect your pieces and track your inventory\n"
                "4. Use `/need` and `/whohas` to coordinate trades\n"
                "5. Report completed trades with `/used`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Important Rules",
            value=(
                "• **I don't execute trades** - trades happen in-game\n"
                "• **I track availability** - not authority\n"
                "• **Images are evidence** - not truth\n"
                "• **You control your data** - use `/fix` to correct mistakes"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎮 Available Commands",
            value=(
                "`/scan` - Upload puzzle screenshots\n"
                "`/inventory` - View your pieces\n"
                "`/need <scene>` - Find pieces you're missing\n"
                "`/whohas <scene> <slot>` - Find who has a piece\n"
                "`/used <scene> <slot>` - Report a completed trade\n"
                "`/fix` - Manually correct your inventory"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Upload clear, well-lit screenshots\n"
                "• You can upload multiple images at once\n"
                "• I'll ask for confirmation if something looks wrong\n"
                "• Use `/used` after every trade to keep inventory accurate"
            ),
            inline=False
        )
        
        embed.set_footer(text="Ready to start? Use /scan to upload your first screenshot!")
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"User {interaction.user} viewed /start")
