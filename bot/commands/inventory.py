"""
/inventory command - View user's puzzle inventory.
"""

import discord
from discord import app_commands
from typing import Optional, List
import logging

from inventory.queries import get_or_create_user, get_user_inventory, get_all_scenes
from inventory.rules import normalize_scene_name

logger = logging.getLogger(__name__)


def register_inventory_command(tree: app_commands.CommandTree):
    """Register /inventory command."""
    
    @tree.command(name="inventory", description="View your puzzle inventory")
    @app_commands.describe(
        scene="Optional: Filter by scene name",
        numbered="Optional: Show slot numbers (reference only)"
    )
    async def inventory_command(
        interaction: discord.Interaction, 
        scene: Optional[str] = None,
        numbered: bool = False
    ):
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
            scenes_data = {}
            for piece in inventory:
                scene_name = piece["scene"]
                if scene_name not in scenes_data:
                    scenes_data[scene_name] = {}
                scenes_data[scene_name][piece["slot_index"]] = piece
            
            # Create embed
            embed = discord.Embed(
                title=f"📦 {interaction.user.name}'s Inventory",
                description=f"Total pieces: **{len(inventory)}** across **{len(scenes_data)}** scenes",
                color=discord.Color.blue()
            )
            
            # Add fields for each scene (limit to prevent embed size issues)
            scene_count = 0
            for scene_name, pieces_map in sorted(scenes_data.items()):
                if scene_count >= 5: # Lower limit for grid display to keep it readable
                    embed.add_field(
                        name="...",
                        value=f"And {len(scenes_data) - 5} more scenes. Use `/inventory scene:<name>` to filter.",
                        inline=False
                    )
                    break
                
                # Determine grid size (default 9, or more if needed)
                max_slot = max(pieces_map.keys()) if pieces_map else 0
                total_pieces = max(9, ((max_slot + 2) // 3) * 3)
                
                # Build grid
                grid_rows = []
                for row_idx in range(total_pieces // 3):
                    row_cells = []
                    for col_idx in range(3):
                        slot_index = row_idx * 3 + col_idx + 1
                        piece = pieces_map.get(slot_index)
                        
                        symbol = ""
                        if not piece:
                            symbol = "❌"
                        elif piece["duplicates"] == 0:
                            symbol = "⬜"
                        else:
                            symbol = f"+{piece['duplicates']}"
                            
                        if numbered:
                            row_cells.append(f"`{slot_index:02}` {symbol}")
                        else:
                            row_cells.append(symbol)
                    
                    grid_rows.append(" | ".join(row_cells))
                
                grid_text = "```\n" + "\n".join(grid_rows) + "\n```"
                
                stars_hint = ""
                # Get stars for the first available piece in this scene to show as hint
                if pieces_map:
                    first_piece = list(pieces_map.values())[0]
                    stars_hint = f"({'⭐' * first_piece['stars']})"
                
                embed.add_field(
                    name=f"🎬 {scene_name} {stars_hint}",
                    value=grid_text,
                    inline=False
                )
                
                scene_count += 1
            
            embed.set_footer(text="❌: Missing | ⬜: Owned | +N: Duplicates")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"User {interaction.user} viewed inventory (scene={scene}, numbered={numbered})")
            
        except Exception as e:
            logger.error(f"Inventory command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @inventory_command.autocomplete("scene")
    async def scene_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        scenes = await get_all_scenes()
        return [
            app_commands.Choice(name=s, value=s)
            for s in scenes if current.lower() in s.lower()
        ][:25]
