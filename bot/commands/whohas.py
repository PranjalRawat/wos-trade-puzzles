"""
/whohas command - Find who has a specific piece.
"""

import discord
from discord import app_commands
import logging
from typing import List

from inventory.queries import get_or_create_user, who_has_piece, get_all_scenes
from inventory.rules import normalize_scene_name
from utils.validation import parse_slot_index

logger = logging.getLogger(__name__)


def register_whohas_command(tree: app_commands.CommandTree):
    """Register /whohas command."""
    
    @tree.command(name="whohas", description="Find who has a specific puzzle piece")
    @app_commands.describe(
        scene="Scene name",
        slot="Slot number (e.g., 5 or 'slot 5')"
    )
    async def whohas_command(interaction: discord.Interaction, scene: str, slot: str):
        """Find who has a specific piece."""
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Normalize scene
            scene = normalize_scene_name(scene)
            
            # Parse slot
            slot_index = parse_slot_index(slot)
            if slot_index is None:
                await interaction.followup.send(
                    f"❌ Invalid slot number: {slot}. Please use a number like '5'.",
                    ephemeral=True
                )
                return
            
            # Find owners
            owners = await who_has_piece(scene, slot_index)
            
            if not owners:
                await interaction.followup.send(
                    f"❌ No one has **{scene}** Slot {slot_index} with duplicates available.",
                    ephemeral=True
                )
                return
            
            # Create embed
            stars = "⭐" * owners[0]["stars"] if owners else ""
            embed = discord.Embed(
                title=f"👥 Who Has: {scene} - Slot {slot_index}",
                description=f"{stars}\n\n**{len(owners)}** users have this piece with duplicates:",
                color=discord.Color.green()
            )
            
            # List owners
            owners_text = []
            for owner in owners[:15]:  # Limit to 15
                username = owner["discord_username"]
                dupes = owner["duplicates"]
                dupe_text = "duplicate" if dupes == 1 else "duplicates"
                owners_text.append(f"• **{username}**: {dupes} {dupe_text}")
            
            if len(owners) > 15:
                owners_text.append(f"\n... and {len(owners) - 15} more")
            
            embed.add_field(
                name="Available From",
                value="\n".join(owners_text),
                inline=False
            )
            
            embed.set_footer(text="Contact these users in-game to arrange a trade!")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"User {interaction.user} checked who has {scene} slot {slot_index}")
            
        except Exception as e:
            logger.error(f"Whohas command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @whohas_command.autocomplete("scene")
    async def scene_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        scenes = await get_all_scenes()
        return [
            app_commands.Choice(name=s, value=s)
            for s in scenes if current.lower() in s.lower()
        ][:25]
