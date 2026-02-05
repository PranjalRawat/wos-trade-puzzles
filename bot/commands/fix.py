"""
/fix command - Manually correct inventory data.
"""

import discord
from discord import app_commands
from typing import Optional
import logging

from inventory.queries import get_or_create_user, get_piece, add_piece, update_duplicates, get_all_scenes
from typing import List, Optional
from inventory.rules import validate_piece_data, normalize_scene_name, ValidationError
from utils.validation import parse_slot_index

logger = logging.getLogger(__name__)


def register_fix_command(tree: app_commands.CommandTree):
    """Register /fix command."""
    
    @tree.command(name="fix", description="Manually correct your inventory")
    @app_commands.describe(
        scene="Scene name",
        slot="Slot number",
        stars="Star count (1-5)",
        duplicates="Number of duplicates"
    )
    async def fix_command(
        interaction: discord.Interaction,
        scene: str,
        slot: str,
        stars: Optional[int] = None,
        duplicates: Optional[int] = None
    ):
        """Manually fix inventory data."""
        
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
            
            # Get existing piece
            existing = await get_piece(user_id, scene, slot_index)
            
            # Determine what to update
            if not existing:
                # New piece - need both stars and duplicates
                if stars is None or duplicates is None:
                    await interaction.followup.send(
                        "❌ For new pieces, you must provide both `stars` and `duplicates`.",
                        ephemeral=True
                    )
                    return
                
                # Validate
                try:
                    validate_piece_data(scene, slot_index, stars, duplicates)
                except ValidationError as e:
                    await interaction.followup.send(f"❌ Validation error: {e}", ephemeral=True)
                    return
                
                # Add piece
                await add_piece(user_id, scene, slot_index, stars, duplicates)
                
                embed = discord.Embed(
                    title="✅ Piece Added",
                    description=f"Added **{scene}** Slot {slot_index}",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="Stars", value="⭐" * stars, inline=True)
                embed.add_field(name="Duplicates", value=str(duplicates), inline=True)
                
                await interaction.followup.send(embed=embed)
                logger.info(f"User {interaction.user} manually added piece: {scene} slot {slot_index}")
                
            else:
                # Existing piece - update what's provided
                if stars is not None:
                    await interaction.followup.send(
                        "⚠️ **Warning**: Stars are normally immutable. Manual changes should be rare.\n"
                        "Stars cannot be changed after creation. If you need to change stars, delete and re-add the piece.",
                        ephemeral=True
                    )
                    return
                
                if duplicates is not None:
                    # Update duplicates
                    try:
                        validate_piece_data(scene, slot_index, existing["stars"], duplicates)
                    except ValidationError as e:
                        await interaction.followup.send(f"❌ Validation error: {e}", ephemeral=True)
                        return
                    
                    old_dupes = existing["duplicates"]
                    await update_duplicates(user_id, scene, slot_index, duplicates)
                    
                    embed = discord.Embed(
                        title="✅ Duplicates Updated",
                        description=f"Updated **{scene}** Slot {slot_index}",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(name="Stars", value="⭐" * existing["stars"], inline=True)
                    embed.add_field(name="Duplicates", value=f"{old_dupes} → **{duplicates}**", inline=True)
                    
                    await interaction.followup.send(embed=embed)
                    logger.info(f"User {interaction.user} manually updated duplicates: {scene} slot {slot_index} ({old_dupes} → {duplicates})")
                    
                else:
                    await interaction.followup.send(
                        "❌ Please specify what to update (`stars` or `duplicates`).",
                        ephemeral=True
                    )
                    logger.info(f"User {interaction.user} fixed piece: {scene} slot {slot_index}")
            
        except Exception as e:
            logger.error(f"Fix command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @fix_command.autocomplete("scene")
    async def scene_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        scenes = await get_all_scenes()
        return [
            app_commands.Choice(name=s, value=s)
            for s in scenes if current.lower() in s.lower()
        ][:25]
