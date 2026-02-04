"""
/inventory command - View user's puzzle inventory.
"""

import discord
from discord import app_commands
from typing import Optional
import logging

from inventory.queries import get_or_create_user, get_user_inventory
from inventory.rules import normalize_scene_name

logger = logging.getLogger(__name__)


def register_inventory_command(tree: app_commands.CommandTree):
    """Register /inventory command."""
    
    @tree.command(name="inventory", description="View your puzzle inventory")
    @app_commands.describe(scene="Optional: Filter by scene name")
    async def inventory_command(interaction: discord.Interaction, scene: Optional[str] = None):
        """View inventory, optionally filtered by scene."""
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Get user
            user_id = await get_or_create_user(
                str(interaction.user.id),
                interaction.user.name
            )
            
            # Get inventory
            inventory = await get_user_inventory(user_id, scene)
            
            if not inventory:
                if scene:
                    await interaction.followup.send(
                        f"📦 You don't have any pieces from **{scene}** yet. Use `/scan` to add them!",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        "📦 Your inventory is empty. Use `/scan` to upload screenshots!",
                        ephemeral=True
                    )
                return
            
            # Group by scene
            scenes = {}
            for piece in inventory:
                scene_name = piece["scene"]
                if scene_name not in scenes:
                    scenes[scene_name] = []
                scenes[scene_name].append(piece)
            
            # Create embed
            embed = discord.Embed(
                title=f"📦 {interaction.user.name}'s Inventory",
                description=f"Total pieces: **{len(inventory)}** across **{len(scenes)}** scenes",
                color=discord.Color.blue()
            )
            
            # Add fields for each scene (limit to prevent embed size issues)
            scene_count = 0
            for scene_name, pieces in sorted(scenes.items()):
                if scene_count >= 10:
                    embed.add_field(
                        name="...",
                        value=f"And {len(scenes) - 10} more scenes. Use `/inventory scene:<name>` to filter.",
                        inline=False
                    )
                    break
                
                # Format pieces
                pieces_text = []
                for piece in sorted(pieces, key=lambda p: p["slot_index"])[:10]:
                    stars = "⭐" * piece["stars"]
                    dupes = piece["duplicates"]
                    dupe_text = f", **{dupes}** dupes" if dupes > 0 else ""
                    pieces_text.append(f"Slot {piece['slot_index']}: {stars}{dupe_text}")
                
                if len(pieces) > 10:
                    pieces_text.append(f"... and {len(pieces) - 10} more")
                
                embed.add_field(
                    name=f"🎬 {scene_name} ({len(pieces)} pieces)",
                    value="\n".join(pieces_text),
                    inline=False
                )
                
                scene_count += 1
            
            embed.set_footer(text="Use /need <scene> to find missing pieces")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"User {interaction.user} viewed inventory (scene={scene})")
            
        except Exception as e:
            logger.error(f"Inventory command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)
