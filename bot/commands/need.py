"""
/need command - Find pieces you're missing in a scene.
"""

import discord
from discord import app_commands
import logging

from inventory.queries import get_or_create_user, get_missing_pieces
from inventory.rules import normalize_scene_name

logger = logging.getLogger(__name__)


def register_need_command(tree: app_commands.CommandTree):
    """Register /need command."""
    
    @tree.command(name="need", description="Find pieces you're missing in a scene")
    @app_commands.describe(scene="Scene name to check")
    async def need_command(interaction: discord.Interaction, scene: str):
        """Show pieces user needs in a scene."""
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Get user
            user_id = await get_or_create_user(
                str(interaction.user.id),
                interaction.user.name
            )
            
            # Normalize scene name
            scene = normalize_scene_name(scene)
            
            # Get missing pieces
            missing = await get_missing_pieces(user_id, scene)
            
            if not missing:
                await interaction.followup.send(
                    f"🎉 You have all known pieces from **{scene}**!",
                    ephemeral=True
                )
                return
            
            # Create embed
            embed = discord.Embed(
                title=f"🔍 Missing Pieces: {scene}",
                description=f"You need **{len(missing)}** pieces from this scene:",
                color=discord.Color.orange()
            )
            
            # Format missing pieces
            pieces_text = []
            for piece in missing[:20]:  # Limit to 20
                stars = "⭐" * piece["stars"]
                pieces_text.append(f"• Slot {piece['slot_index']}: {stars}")
            
            if len(missing) > 20:
                pieces_text.append(f"\n... and {len(missing) - 20} more")
            
            embed.add_field(
                name="Missing Pieces",
                value="\n".join(pieces_text),
                inline=False
            )
            
            embed.set_footer(text="Use /whohas <scene> <slot> to find who has a piece")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"User {interaction.user} checked needs for {scene}")
            
        except Exception as e:
            logger.error(f"Need command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
