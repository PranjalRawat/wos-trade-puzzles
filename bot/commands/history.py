"""
/history command - View recent scan attempts.
"""

import discord
from discord import app_commands
import logging
from datetime import datetime

from inventory.queries import get_or_create_user, get_user_scan_history

logger = logging.getLogger(__name__)


def register_history_command(tree: app_commands.CommandTree):
    """Register /history command."""
    
    @tree.command(name="history", description="View your recent puzzle scan history")
    async def history_command(interaction: discord.Interaction):
        """Show recent scans for the user."""
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Get user
            user_id = await get_or_create_user(
                str(interaction.user.id),
                interaction.user.name
            )
            
            # Get history
            history = await get_user_scan_history(user_id, limit=5)
            
            if not history:
                await interaction.followup.send(
                    "📜 No scan history found. Use `/scan` to start tracking your puzzles!",
                    ephemeral=True
                )
                return
            
            embed = discord.Embed(
                title=f"📜 {interaction.user.name}'s Scan History",
                description="Your most recent scan attempts:",
                color=discord.Color.blue()
            )
            
            for scan in history:
                # Format time
                # SQLite timestamp is usually YYYY-MM-DD HH:MM:SS
                try:
                    dt = datetime.strptime(scan["at"], "%Y-%m-%d %H:%M:%S")
                    time_str = dt.strftime("%b %d, %H:%M")
                except:
                    time_str = scan["at"]
                
                status_emoji = {
                    "success": "✅",
                    "partial": "⚠️",
                    "failed": "❌",
                    "skipped": "⏭️"
                }.get(scan["status"], "❓")
                
                name = f"{status_emoji} Scan ID: `{scan['id']}` - {time_str}"
                
                details = (
                    f"**Scene**: {scan['scene'] or 'Unknown'}\n"
                    f"**File**: `{scan['filename'] or 'N/A'}`\n"
                    f"**Pieces**: Found {scan['pieces_found']}"
                )
                
                embed.add_field(name=name, value=details, inline=False)
            
            embed.set_footer(text="Use /unscan <id> to undo a scan and clear its image hash.")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"User {interaction.user} viewed scan history")
            
        except Exception as e:
            logger.error(f"History command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
