"""
/used command - Report a completed in-game trade.
"""

import discord
from discord import app_commands
import logging

from inventory.queries import get_or_create_user, get_piece, update_duplicates, get_all_scenes
from typing import List
from inventory.rules import normalize_scene_name
from utils.validation import parse_slot_index

logger = logging.getLogger(__name__)


def register_used_command(tree: app_commands.CommandTree):
    """Register /used command."""
    
    @tree.command(name="used", description="Report that you traded a piece in-game")
    @app_commands.describe(
        scene="Scene name",
        slot="Slot number"
    )
    async def used_command(interaction: discord.Interaction, scene: str, slot: str):
        """Record a completed trade."""
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Get user
            user_id = await get_or_create_user(
                str(interaction.user.id),
                interaction.user.name
            )
            
            # Normalize scene
            scene = normalize_scene_name(scene)
            
            # Parse slot
            slot_index = parse_slot_index(slot)
            if slot_index is None:
                await interaction.followup.send(
                    f"❌ Invalid slot number: {slot}",
                    ephemeral=True
                )
                return
            
            # Get piece
            piece = await get_piece(user_id, scene, slot_index)
            
            if not piece:
                await interaction.followup.send(
                    f"❌ You don't own **{scene}** Slot {slot_index}. Use `/scan` to add it first.",
                    ephemeral=True
                )
                return
            
            # Check duplicates
            current_dupes = piece["duplicates"]
            
            if current_dupes <= 0:
                await interaction.followup.send(
                    f"❌ You have 0 duplicates of **{scene}** Slot {slot_index}. Cannot reduce further.",
                    ephemeral=True
                )
                return
            
            # Reduce duplicates
            new_dupes = current_dupes - 1
            await update_duplicates(user_id, scene, slot_index, new_dupes)
            
            # Confirmation
            stars = "⭐" * piece["stars"]
            embed = discord.Embed(
                title="✅ Trade Recorded",
                description=f"Reduced duplicates for **{scene}** Slot {slot_index}",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Piece",
                value=f"{stars}",
                inline=True
            )
            
            embed.add_field(
                name="Duplicates",
                value=f"{current_dupes} → **{new_dupes}**",
                inline=True
            )
            
            embed.set_footer(text="Great job trading! Keep your inventory updated.")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"User {interaction.user} recorded trade: {scene} slot {slot_index} ({current_dupes} → {new_dupes})")
            
        except Exception as e:
            logger.error(f"Used command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @used_command.autocomplete("scene")
    async def scene_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        scenes = await get_all_scenes()
        return [
            app_commands.Choice(name=s, value=s)
            for s in scenes if current.lower() in s.lower()
        ][:25]
