"""
Inventory merge logic - CRITICAL COMPONENT
Implements exact merge rules for scan results.

RULES (NON-NEGOTIABLE):
1. Stars are immutable once set
2. Duplicates can only increase automatically
3. If scanned duplicates < stored duplicates → conflict (ask user)
4. User commands override everything
"""

from typing import List, Dict, Any, Tuple
from inventory.queries import get_piece, add_piece, update_duplicates
from inventory.rules import validate_piece_data, normalize_scene_name
import logging

logger = logging.getLogger(__name__)


class MergeResult:
    """Result of merging scan data with existing inventory."""
    
    def __init__(self):
        self.added: List[Dict[str, Any]] = []
        self.updated: List[Dict[str, Any]] = []
        self.conflicts: List[Dict[str, Any]] = []
        self.unchanged: List[Dict[str, Any]] = []
        
    def summary(self) -> str:
        """Generate human-readable summary."""
        parts = []
        
        if self.added:
            parts.append(f"**{len(self.added)} new pieces** added")
        
        if self.updated:
            parts.append(f"**{len(self.updated)} pieces** updated")
        
        if self.unchanged:
            parts.append(f"{len(self.unchanged)} pieces unchanged")
        
        if self.conflicts:
            parts.append(f"⚠️ **{len(self.conflicts)} conflicts** need your review")
        
        return ", ".join(parts) if parts else "No changes detected"
    
    def has_conflicts(self) -> bool:
        """Check if there are any conflicts."""
        return len(self.conflicts) > 0
    
    def total_changes(self) -> int:
        """Total number of changes (added + updated)."""
        return len(self.added) + len(self.updated)


async def merge_scan_results(
    user_id: int,
    scan_data: List[Dict[str, Any]],
    auto_apply: bool = False
) -> MergeResult:
    """
    Merge scanned pieces with existing inventory.
    
    MERGE LOGIC:
    - For each (scene, slot_index) in scan_data:
        - If piece doesn't exist → ADD
        - If piece exists:
            - stars → IGNORE (immutable)
            - duplicates:
                - scanned > stored → UPDATE
                - scanned == stored → IGNORE
                - scanned < stored → CONFLICT (ask user)
    
    Args:
        user_id: Internal user ID
        scan_data: List of pieces from vision pipeline
                   Each item: {scene, slot_index, stars, duplicates}
        auto_apply: If True, apply non-conflicting changes immediately
                    If False, return results without applying
    
    Returns:
        MergeResult with categorized changes
    """
    # Deduplicate scan_data
    # If the same piece is detected multiple times (e.g. across multiple images),
    # the latest detection in the batch takes precedence.
    deduped_scan = {}
    for piece in scan_data:
        scene = normalize_scene_name(piece["scene"])
        slot = piece["slot_index"]
        key = (scene, slot)
        # Latest detection in the batch overrides earlier ones
        deduped_scan[key] = piece

    result = MergeResult()
    
    for (scene, slot_index), piece_data in deduped_scan.items():
        scanned_stars = piece_data["stars"]
        scanned_duplicates = piece_data["duplicates"]
        
        # Validate data
        try:
            validate_piece_data(scene, slot_index, scanned_stars, scanned_duplicates)
        except Exception as e:
            logger.warning(f"Invalid piece data: {e}")
            continue
        
        # Check if piece exists
        existing = await get_piece(user_id, scene, slot_index)
        
        if not existing:
            # NEW PIECE - add it
            if auto_apply:
                await add_piece(user_id, scene, slot_index, scanned_stars, scanned_duplicates)
            
            result.added.append({
                "scene": scene,
                "slot_index": slot_index,
                "stars": scanned_stars,
                "duplicates": scanned_duplicates
            })
            
            logger.info(f"New piece: {scene} slot {slot_index} ({scanned_stars}⭐, {scanned_duplicates} dupes)")
            
        else:
            # EXISTING PIECE - check duplicates
            stored_duplicates = existing["duplicates"]
            stored_stars = existing["stars"]
            
            # Stars are immutable - log warning if different
            if scanned_stars != stored_stars:
                logger.warning(
                    f"Star mismatch for {scene} slot {slot_index}: "
                    f"stored={stored_stars}, scanned={scanned_stars}. "
                    f"Keeping stored value (stars are immutable)."
                )
            
            # Compare duplicates
            if scanned_duplicates > stored_duplicates:
                # INCREASE - safe to apply
                if auto_apply:
                    await update_duplicates(user_id, scene, slot_index, scanned_duplicates)
                
                result.updated.append({
                    "scene": scene,
                    "slot_index": slot_index,
                    "stars": stored_stars,  # Keep stored stars
                    "old_duplicates": stored_duplicates,
                    "new_duplicates": scanned_duplicates
                })
                
                logger.info(
                    f"Updated duplicates: {scene} slot {slot_index} "
                    f"({stored_duplicates} → {scanned_duplicates})"
                )
                
            elif scanned_duplicates < stored_duplicates:
                # DECREASE - conflict! Ask user
                result.conflicts.append({
                    "scene": scene,
                    "slot_index": slot_index,
                    "stars": stored_stars,
                    "stored_duplicates": stored_duplicates,
                    "scanned_duplicates": scanned_duplicates,
                    "message": (
                        f"**{scene} - Slot {slot_index}** ({stored_stars}⭐)\n"
                        f"Stored: {stored_duplicates} duplicates\n"
                        f"Scanned: {scanned_duplicates} duplicates\n"
                        f"The scan shows fewer duplicates than stored. This could mean:\n"
                        f"• You traded some pieces in-game (use `/used` to record trades)\n"
                        f"• The image is old or incomplete\n"
                        f"• Vision detection error"
                    )
                })
                
                logger.warning(
                    f"Conflict: {scene} slot {slot_index} "
                    f"(stored={stored_duplicates}, scanned={scanned_duplicates})"
                )
                
            else:
                # SAME - no change
                result.unchanged.append({
                    "scene": scene,
                    "slot_index": slot_index,
                    "stars": stored_stars,
                    "duplicates": stored_duplicates
                })
    
    return result


async def apply_merge_result(user_id: int, result: MergeResult) -> None:
    """
    Apply a merge result to the database.
    Used when user confirms changes after reviewing conflicts.
    
    Args:
        user_id: Internal user ID
        result: MergeResult to apply
    """
    # Apply additions
    for piece in result.added:
        await add_piece(
            user_id,
            piece["scene"],
            piece["slot_index"],
            piece["stars"],
            piece["duplicates"]
        )
    
    # Apply updates
    for piece in result.updated:
        await update_duplicates(
            user_id,
            piece["scene"],
            piece["slot_index"],
            piece["new_duplicates"]
        )
    
    logger.info(f"Applied merge: {len(result.added)} added, {len(result.updated)} updated")


async def resolve_conflict(
    user_id: int,
    scene: str,
    slot_index: int,
    use_scanned_value: bool
) -> None:
    """
    Resolve a merge conflict by choosing which value to keep.
    
    Args:
        user_id: Internal user ID
        scene: Scene name
        slot_index: Slot position
        use_scanned_value: If True, use scanned duplicates; if False, keep stored
    """
    scene = normalize_scene_name(scene)
    
    if use_scanned_value:
        # User confirmed the scanned value is correct
        # Note: The scanned value should be passed separately in a real implementation
        # For now, this is a placeholder
        logger.info(f"Conflict resolved: using scanned value for {scene} slot {slot_index}")
    else:
        # User wants to keep stored value - do nothing
        logger.info(f"Conflict resolved: keeping stored value for {scene} slot {slot_index}")
