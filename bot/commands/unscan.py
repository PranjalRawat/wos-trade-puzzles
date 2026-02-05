import discord
from discord import app_commands
import logging
from typing import List, Optional

from inventory.queries import get_or_create_user, delete_scan_and_rollback, get_latest_scan_for_scene, get_all_scenes

logger = logging.getLogger(__name__)


def register_unscan_command(tree: app_commands.CommandTree):
    """Register /unscan command."""
    
    @tree.command(name="unscan", description="Undo the latest scan for a specific puzzle scene")
    @app_commands.describe(
        scene="The scene name to undo the latest scan for",
        scan_id="Optional: Specific Scan ID to undo (if you know it)"
    )
    async def unscan_command(
        interaction: discord.Interaction, 
        scene: str,
        scan_id: Optional[int] = None
    ):
        """Rollback a specific scan."""
        
        await interaction.response.defer(thinking=True)
        
        try:
            # Get user
            user_id = await get_or_create_user(
                str(interaction.user.id),
                interaction.user.name
            )
            
            # Resolve scan_id if scene provided
            if scene:
                target_id = await get_latest_scan_for_scene(user_id, scene)
                if not target_id:
                    await interaction.followup.send(
                        f"❌ No recent scans found for scene: **{scene}**",
                        ephemeral=True
                    )
                    return
                scan_id = target_id
            
            if not scan_id:
                await interaction.followup.send(
                    "❌ Please provide either a **Scan ID** or a **Scene Name**.",
                    ephemeral=True
                )
                return
            
            # Perform rollback
            result = await delete_scan_and_rollback(user_id, scan_id)
            
            if not result["success"]:
                await interaction.followup.send(
                    f"❌ Failed to undo scan `{scan_id}`: {result['error']}",
                    ephemeral=True
                )
                return
            
            # Success response
            embed = discord.Embed(
                title="⏪ Scan Undone",
                description=f"Successfully rolled back **Scan ID: {scan_id}**",
                color=discord.Color.green()
            )
            
            if scene:
                embed.add_field(name="Target Scene", value=f"**{scene}**", inline=False)
            
            embed.add_field(
                name="Inventory Changes",
                value=f"Adjusted **{result['rolled_back_pieces']}** pieces back to their original state.",
                inline=False
            )
            
            embed.add_field(
                name="Deduplication",
                value="Image hash cleared. You can now re-scan that screenshot if you wish.",
                inline=False
            )
            
            embed.set_footer(text="Trade coordiantion is now more reliable!")
            
            await interaction.followup.send(embed=embed)
            logger.info(f"User {interaction.user} unscanned scene='{scene}' (scan_id={scan_id})")
            
        except Exception as e:
            logger.error(f"Unscan command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)

    @unscan_command.autocomplete("scene")
    async def scene_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> List[app_commands.Choice[str]]:
        scenes = await get_all_scenes()
        return [
            app_commands.Choice(name=s, value=s)
            for s in scenes if current.lower() in s.lower()
        ][:25]
