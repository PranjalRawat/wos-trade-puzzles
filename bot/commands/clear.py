"""
/clear command - Reset user inventory and history.
Includes confirmation UI to prevent accidental deletion.
"""

import discord
from discord import app_commands
import logging
from typing import Optional

from inventory.queries import get_or_create_user, clear_user_inventory, get_all_scenes

logger = logging.getLogger(__name__)


class ClearConfirmation(discord.ui.View):
    """Confirmation view with Yes/No buttons."""
    
    def __init__(self, user_id: int, scene: Optional[str] = None):
        super().__init__(timeout=60.0)
        self.user_id = user_id
        self.scene = scene
        self.confirmed = False

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the command user can confirm.", ephemeral=True)
            return
            
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.send_message("Deletion cancelled.", ephemeral=True)


def register_clear_command(tree: app_commands.CommandTree):
    """Register /clear command."""
    
    @tree.command(name="clear", description="Reset your inventory data (optional: specific scene)")
    @app_commands.describe(scene="The specific puzzle scene to clear (leave empty for full reset)")
    async def clear_command(interaction: discord.Interaction, scene: Optional[str] = None):
        """Reset user inventory."""
        
        # Get user ID
        internal_user_id = await get_or_create_user(
            str(interaction.user.id),
            interaction.user.name
        )
        
        target_text = f"**{scene}**" if scene else "your **ENTIRE inventory and scan history**"
        
        embed = discord.Embed(
            title="⚠️ Confirm Inventory Deletion",
            description=(
                f"Are you sure you want to clear {target_text}?\n\n"
                "**This action cannot be undone.**"
            ),
            color=discord.Color.red()
        )
        
        view = ClearConfirmation(interaction.user.id, scene)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        # Wait for confirmation
        await view.wait()
        
        if view.confirmed:
            try:
                result = await clear_user_inventory(internal_user_id, scene)
                
                success_embed = discord.Embed(
                    title="✅ Inventory Cleared",
                    description=f"Successfully cleared {target_text}.",
                    color=discord.Color.green()
                )
                
                success_embed.add_field(
                    name="📊 Summary",
                    value=(
                        f"• Items deleted: {result['inventory_deleted']}\n"
                        f"• History records cleared: {result['scans_deleted']}"
                    )
                )
                
                await interaction.edit_original_response(embed=success_embed, view=None)
                logger.info(f"User {interaction.user.name} cleared {scene if scene else 'ALL'} inventory.")
                
            except Exception as e:
                logger.error(f"Failed to clear inventory for {interaction.user.name}: {e}")
                await interaction.edit_original_response(content=f"❌ An error occurred: {e}", embed=None, view=None)
