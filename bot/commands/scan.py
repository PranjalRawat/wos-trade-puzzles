"""
/scan command - Upload and process puzzle screenshots.
Most complex command with image processing and merge logic.
"""

import discord
from discord import app_commands
from typing import List, Dict, Any
import logging
import asyncio

from inventory.queries import get_or_create_user, record_scan, check_image_hash, record_image_hash
from inventory.merge import merge_scan_results, apply_merge_result
from vision.pipeline import VisionPipeline
from inventory.rules import normalize_scene_name

logger = logging.getLogger(__name__)


def register_scan_command(tree: app_commands.CommandTree):
    """Register /scan command."""
    
    @tree.command(name="scan", description="Upload puzzle screenshots to update your inventory")
    async def scan_command(interaction: discord.Interaction):
        """
        Scan puzzle screenshots.
        User should attach images to the command.
        """
        
        # Defer response since processing may take time
        await interaction.response.defer(thinking=True)
        
        try:
            # Get user ID
            user_id = await get_or_create_user(
                str(interaction.user.id),
                interaction.user.name
            )
            
            # Check for attachments
            # Note: Discord slash commands don't support file uploads directly
            # Users need to upload images in a follow-up message
            # For now, we'll provide instructions
            
            embed = discord.Embed(
                title="📸 Upload Your Screenshots",
                description="Please upload your puzzle screenshots in your next message.",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📋 Instructions",
                value=(
                    "1. Take clear screenshots of your puzzle inventory\n"
                    "2. Upload them in your next message (you can upload multiple)\n"
                    "3. I'll process them and show you a summary\n"
                    "4. Confirm the changes to update your inventory"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💡 Tips",
                value=(
                    "• Make sure screenshots are clear and well-lit\n"
                    "• You can upload up to 10 images at once\n"
                    "• I'll skip duplicate images automatically"
                ),
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
            # Wait for user to upload images
            def check(m):
                return m.author.id == interaction.user.id and m.channel.id == interaction.channel.id and len(m.attachments) > 0
            
            try:
                message = await interaction.client.wait_for('message', check=check, timeout=300.0)
            except asyncio.TimeoutError:
                await interaction.followup.send("⏱️ Scan timed out. Use `/scan` again when you're ready.", ephemeral=True)
                return
            
            # Process attachments
            attachments = message.attachments
            
            if not attachments:
                await interaction.followup.send("❌ No images found. Please attach images.", ephemeral=True)
                return
            
            # Filter for image attachments
            image_attachments = [a for a in attachments if a.content_type and a.content_type.startswith('image/')]
            
            if not image_attachments:
                await interaction.followup.send("❌ No valid images found. Please upload image files.", ephemeral=True)
                return
            
            # Process images
            processing_msg = await interaction.followup.send(f"🔄 Processing {len(image_attachments)} images...")
            
            pipeline = VisionPipeline()
            all_pieces = []
            skipped_count = 0
            failed_count = 0
            scenes_found = set()
            
            for attachment in image_attachments:
                # Check if already scanned
                # First, we need to download to compute hash
                image_data = await attachment.read()
                from utils.image_hash import compute_image_hash
                image_hash = compute_image_hash(image_data)
                
                existing_hash = await check_image_hash(image_hash)
                if existing_hash:
                    logger.info(f"Skipping duplicate image (hash: {image_hash})")
                    skipped_count += 1
                    await record_scan(
                        user_id, image_hash, None, 0, 0, 0, 0, 'skipped',
                        f"Duplicate image (first seen by {existing_hash['first_seen_by']})"
                    )
                    continue
                
                # Process image
                result = await pipeline.process_image_url(attachment.url)
                
                if not result["success"]:
                    logger.error(f"Failed to process image: {result['error']}")
                    failed_count += 1
                    await record_scan(
                        user_id, image_hash, None, 0, 0, 0, 0, 'failed',
                        result['error']
                    )
                    continue
                
                # Record hash
                await record_image_hash(user_id, image_hash)
                
                # Add pieces to batch
                scene = result["scene"] or "Unknown Scene"
                scenes_found.add(scene)
                
                for piece in result["pieces"]:
                    piece["scene"] = scene
                    all_pieces.append(piece)
            
            # Check if we got any pieces
            if not all_pieces:
                await processing_msg.edit(content=f"❌ No pieces detected. Skipped: {skipped_count}, Failed: {failed_count}")
                return
            
            # Merge with existing inventory
            merge_result = await merge_scan_results(user_id, all_pieces, auto_apply=False)
            
            # Show summary
            summary_embed = discord.Embed(
                title="📊 Scan Results",
                description=merge_result.summary(),
                color=discord.Color.green() if not merge_result.has_conflicts() else discord.Color.orange()
            )
            
            if scenes_found:
                summary_embed.add_field(
                    name="🎬 Scenes Detected",
                    value=", ".join(f"**{s}**" for s in scenes_found),
                    inline=False
                )
            
            if merge_result.added:
                summary_embed.add_field(
                    name=f"➕ New Pieces ({len(merge_result.added)})",
                    value=_format_pieces_list(merge_result.added[:5]) + (f"\n... and {len(merge_result.added) - 5} more" if len(merge_result.added) > 5 else ""),
                    inline=False
                )
            
            if merge_result.updated:
                summary_embed.add_field(
                    name=f"🔄 Updated ({len(merge_result.updated)})",
                    value=_format_updates_list(merge_result.updated[:5]) + (f"\n... and {len(merge_result.updated) - 5} more" if len(merge_result.updated) > 5 else ""),
                    inline=False
                )
            
            if merge_result.has_conflicts():
                summary_embed.add_field(
                    name=f"⚠️ Conflicts ({len(merge_result.conflicts)})",
                    value="Some scanned values are lower than stored. Review below.",
                    inline=False
                )
            
            if skipped_count > 0:
                summary_embed.add_field(
                    name="⏭️ Skipped",
                    value=f"{skipped_count} duplicate images",
                    inline=True
                )
            
            if failed_count > 0:
                summary_embed.add_field(
                    name="❌ Failed",
                    value=f"{failed_count} images couldn't be processed",
                    inline=True
                )
            
            await processing_msg.edit(content=None, embed=summary_embed)
            
            # Handle conflicts
            if merge_result.has_conflicts():
                conflicts_embed = discord.Embed(
                    title="⚠️ Conflicts Need Review",
                    description="The scan shows fewer duplicates than stored for these pieces:",
                    color=discord.Color.orange()
                )
                
                for conflict in merge_result.conflicts[:5]:
                    conflicts_embed.add_field(
                        name=f"{conflict['scene']} - Slot {conflict['slot_index']} ({'⭐' * conflict['stars']})",
                        value=f"Stored: **{conflict['stored_duplicates']}** → Scanned: **{conflict['scanned_duplicates']}**",
                        inline=False
                    )
                
                conflicts_embed.set_footer(text="React with ✅ to apply non-conflicting changes only, or ❌ to cancel.")
                
                conflict_msg = await interaction.followup.send(embed=conflicts_embed)
                await conflict_msg.add_reaction("✅")
                await conflict_msg.add_reaction("❌")
                
                # Wait for reaction
                def reaction_check(reaction, user):
                    return user.id == interaction.user.id and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == conflict_msg.id
                
                try:
                    reaction, user = await interaction.client.wait_for('reaction_add', check=reaction_check, timeout=60.0)
                    
                    if str(reaction.emoji) == "✅":
                        # Apply non-conflicting changes only
                        merge_result.conflicts = []  # Clear conflicts
                        await apply_merge_result(user_id, merge_result)
                        
                        # Record successful scan
                        for scene in scenes_found:
                            await record_scan(
                                user_id, image_hash, scene,
                                len(all_pieces), len(merge_result.added),
                                len(merge_result.updated), 0, 'partial'
                            )
                        
                        await interaction.followup.send("✅ Applied non-conflicting changes. Use `/fix` to correct conflicts manually.")
                    else:
                        await interaction.followup.send("❌ Scan cancelled. No changes made.")
                        
                except asyncio.TimeoutError:
                    await interaction.followup.send("⏱️ Confirmation timed out. No changes made.")
                    
            else:
                # No conflicts - ask for confirmation
                confirm_embed = discord.Embed(
                    title="✅ Ready to Apply",
                    description=f"Apply {merge_result.total_changes()} changes to your inventory?",
                    color=discord.Color.green()
                )
                
                confirm_msg = await interaction.followup.send(embed=confirm_embed)
                await confirm_msg.add_reaction("✅")
                await confirm_msg.add_reaction("❌")
                
                def reaction_check(reaction, user):
                    return user.id == interaction.user.id and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
                
                try:
                    reaction, user = await interaction.client.wait_for('reaction_add', check=reaction_check, timeout=60.0)
                    
                    if str(reaction.emoji) == "✅":
                        await apply_merge_result(user_id, merge_result)
                        
                        # Record successful scan
                        for scene in scenes_found:
                            await record_scan(
                                user_id, image_hash, scene,
                                len(all_pieces), len(merge_result.added),
                                len(merge_result.updated), 0, 'success'
                            )
                        
                        await interaction.followup.send("✅ Inventory updated successfully!")
                    else:
                        await interaction.followup.send("❌ Scan cancelled.")
                        
                except asyncio.TimeoutError:
                    await interaction.followup.send("⏱️ Confirmation timed out. No changes made.")
        
        except Exception as e:
            logger.error(f"Scan command failed: {e}", exc_info=True)
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)


def _format_pieces_list(pieces: List[Dict[str, Any]]) -> str:
    """Format pieces for display."""
    lines = []
    for piece in pieces:
        stars = "⭐" * piece["stars"]
        dupes = piece.get("duplicates", 0)
        lines.append(f"• **{piece['scene']}** Slot {piece['slot_index']} ({stars}, {dupes} dupes)")
    return "\n".join(lines) if lines else "None"


def _format_updates_list(updates: List[Dict[str, Any]]) -> str:
    """Format updates for display."""
    lines = []
    for update in updates:
        stars = "⭐" * update["stars"]
        old = update["old_duplicates"]
        new = update["new_duplicates"]
        lines.append(f"• **{update['scene']}** Slot {update['slot_index']} ({stars}): {old} → {new} dupes")
    return "\n".join(lines) if lines else "None"
