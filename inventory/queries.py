"""
Database query functions for inventory operations.
All queries use the database connection from db/database.py.
"""

from typing import Optional, List, Dict, Any
from db.database import get_database
from inventory.rules import validate_piece_data, validate_duplicates, normalize_scene_name
import logging

logger = logging.getLogger(__name__)


async def get_or_create_user(discord_id: str, discord_username: str) -> int:
    """
    Get user ID from Discord ID, creating user if they don't exist.
    
    Args:
        discord_id: Discord user ID
        discord_username: Discord username
        
    Returns:
        Internal user ID
    """
    db = await get_database()
    
    # Try to get existing user
    row = await db.fetchone(
        "SELECT id FROM users WHERE discord_id = ?",
        (discord_id,)
    )
    
    if row:
        # Update username in case it changed
        await db.execute(
            "UPDATE users SET discord_username = ?, updated_at = CURRENT_TIMESTAMP WHERE discord_id = ?",
            (discord_username, discord_id)
        )
        return row[0]
    
    # Create new user
    cursor = await db.execute(
        "INSERT INTO users (discord_id, discord_username) VALUES (?, ?)",
        (discord_id, discord_username)
    )
    
    logger.info(f"Created new user: {discord_username} ({discord_id})")
    return cursor.lastrowid


async def get_user_inventory(user_id: int, scene: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get user's inventory, optionally filtered by scene.
    
    Args:
        user_id: Internal user ID
        scene: Optional scene filter
        
    Returns:
        List of inventory items with keys: scene, slot_index, stars, duplicates
    """
    db = await get_database()
    
    if scene:
        scene = normalize_scene_name(scene)
        rows = await db.fetchall(
            """
            SELECT scene, slot_index, stars, duplicates, updated_at
            FROM inventory
            WHERE user_id = ? AND scene = ?
            ORDER BY scene, slot_index
            """,
            (user_id, scene)
        )
    else:
        rows = await db.fetchall(
            """
            SELECT scene, slot_index, stars, duplicates, updated_at
            FROM inventory
            WHERE user_id = ?
            ORDER BY scene, slot_index
            """,
            (user_id,)
        )
    
    return [
        {
            "scene": row[0],
            "slot_index": row[1],
            "stars": row[2],
            "duplicates": row[3],
            "updated_at": row[4]
        }
        for row in rows
    ]


async def get_piece(user_id: int, scene: str, slot_index: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific piece from user's inventory.
    
    Args:
        user_id: Internal user ID
        scene: Scene name
        slot_index: Slot position
        
    Returns:
        Piece data or None if not found
    """
    db = await get_database()
    scene = normalize_scene_name(scene)
    
    row = await db.fetchone(
        """
        SELECT stars, duplicates, updated_at
        FROM inventory
        WHERE user_id = ? AND scene = ? AND slot_index = ?
        """,
        (user_id, scene, slot_index)
    )
    
    if not row:
        return None
    
    return {
        "scene": scene,
        "slot_index": slot_index,
        "stars": row[0],
        "duplicates": row[1],
        "updated_at": row[2]
    }


async def add_piece(user_id: int, scene: str, slot_index: int, stars: int, duplicates: int) -> None:
    """
    Add a new piece to user's inventory.
    
    Args:
        user_id: Internal user ID
        scene: Scene name
        slot_index: Slot position
        stars: Star count (1-5)
        duplicates: Duplicate count (>= 0)
    """
    validate_piece_data(scene, slot_index, stars, duplicates)
    scene = normalize_scene_name(scene)
    
    db = await get_database()
    
    # Use UPSERT (INSERT ... ON CONFLICT) to prevent crashes
    # Note: Stars are immutable once set, so we only update duplicates
    await db.execute(
        """
        INSERT INTO inventory (user_id, scene, slot_index, stars, duplicates)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, scene, slot_index) DO UPDATE SET
            duplicates = MAX(inventory.duplicates, excluded.duplicates),
            updated_at = CURRENT_TIMESTAMP
        """,
        (user_id, scene, slot_index, stars, duplicates)
    )
    
    logger.info(f"Add/Update piece: user={user_id}, scene={scene}, slot={slot_index}, stars={stars}, duplicates={duplicates}")


async def update_duplicates(user_id: int, scene: str, slot_index: int, new_count: int) -> None:
    """
    Update duplicate count for a piece.
    CRITICAL: This is the ONLY way to modify duplicates after initial creation.
    
    Args:
        user_id: Internal user ID
        scene: Scene name
        slot_index: Slot position
        new_count: New duplicate count (>= 0)
    """
    validate_duplicates(new_count)
    scene = normalize_scene_name(scene)
    
    db = await get_database()
    
    await db.execute(
        """
        UPDATE inventory
        SET duplicates = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND scene = ? AND slot_index = ?
        """,
        (new_count, user_id, scene, slot_index)
    )
    
    logger.info(f"Updated duplicates: user={user_id}, scene={scene}, slot={slot_index}, new_count={new_count}")


async def who_has_piece(scene: str, slot_index: int) -> List[Dict[str, Any]]:
    """
    Find all users who own a specific piece with duplicates > 0.
    
    Args:
        scene: Scene name
        slot_index: Slot position
        
    Returns:
        List of users with keys: discord_id, discord_username, duplicates
    """
    db = await get_database()
    scene = normalize_scene_name(scene)
    
    rows = await db.fetchall(
        """
        SELECT u.discord_id, u.discord_username, i.duplicates, i.stars
        FROM inventory i
        JOIN users u ON i.user_id = u.id
        WHERE i.scene = ? AND i.slot_index = ? AND i.duplicates > 0 AND i.stars < 5
        ORDER BY i.duplicates DESC
        """,
        (scene, slot_index)
    )
    
    return [
        {
            "discord_id": row[0],
            "discord_username": row[1],
            "duplicates": row[2],
            "stars": row[3]
        }
        for row in rows
    ]


async def who_needs_scene(scene: str) -> List[Dict[str, Any]]:
    """
    Find all pieces in a scene that a user doesn't own.
    
    Args:
        scene: Scene name
        
    Returns:
        List of available pieces with keys: slot_index, stars, owners
    """
    db = await get_database()
    scene = normalize_scene_name(scene)
    
    # Get all unique pieces in this scene
    rows = await db.fetchall(
        """
        SELECT DISTINCT slot_index, stars
        FROM inventory
        WHERE scene = ?
        ORDER BY slot_index
        """,
        (scene,)
    )
    
    return [
        {
            "slot_index": row[0],
            "stars": row[1]
        }
        for row in rows
    ]


async def get_missing_pieces(user_id: int, scene: str) -> List[Dict[str, Any]]:
    """
    Get pieces in a scene that a user doesn't own.
    
    Args:
        user_id: Internal user ID
        scene: Scene name
        
    Returns:
        List of missing pieces with keys: slot_index, stars
    """
    db = await get_database()
    scene = normalize_scene_name(scene)
    
    # Get all pieces in scene that user doesn't have
    rows = await db.fetchall(
        """
        SELECT DISTINCT i.slot_index, i.stars
        FROM inventory i
        WHERE i.scene = ?
        AND NOT EXISTS (
            SELECT 1 FROM inventory i2
            WHERE i2.user_id = ? AND i2.scene = i.scene AND i2.slot_index = i.slot_index
        )
        ORDER BY i.slot_index
        """,
        (scene, user_id)
    )
    
    return [
        {
            "slot_index": row[0],
            "stars": row[1]
        }
        for row in rows
    ]


async def record_scan(
    user_id: int,
    image_hash: str,
    image_filename: Optional[str],
    scene: Optional[str],
    pieces_found: int,
    pieces_added: int,
    pieces_updated: int,
    conflicts_found: int,
    scan_status: str,
    error_message: Optional[str] = None
) -> None:
    """
    Record a scan attempt in scan_history.
    
    Args:
        user_id: Internal user ID
        image_hash: Hash of the scanned image
        image_filename: Filename of the scanned image
        scene: Scene name (if detected)
        pieces_found: Total pieces detected
        pieces_added: New pieces added
        pieces_updated: Existing pieces updated
        conflicts_found: Conflicts requiring user confirmation
        scan_status: 'success', 'partial', 'failed', 'skipped'
        error_message: Optional error message
    """
    db = await get_database()
    
    await db.execute(
        """
        INSERT INTO scan_history (
            user_id, image_hash, image_filename, scene, pieces_found, pieces_added,
            pieces_updated, conflicts_found, scan_status, error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, image_hash, image_filename, scene, pieces_found, pieces_added,
         pieces_updated, conflicts_found, scan_status, error_message)
    )


async def check_image_hash(image_hash: str) -> Optional[Dict[str, Any]]:
    """
    Check if an image hash has been seen before.
    
    Args:
        image_hash: Hash of the image
        
    Returns:
        Hash record or None if not seen
    """
    db = await get_database()
    
    row = await db.fetchone(
        """
        SELECT h.hash, h.first_seen_at, h.times_attempted, u.discord_username
        FROM image_hashes h
        JOIN users u ON h.first_seen_by = u.id
        WHERE h.hash = ?
        """,
        (image_hash,)
    )
    
    if not row:
        return None
    
    return {
        "hash": row[0],
        "first_seen_at": row[1],
        "times_attempted": row[2],
        "first_seen_by": row[3]
    }


async def record_image_hash(user_id: int, image_hash: str) -> None:
    """
    Record a new image hash or increment attempt counter.
    
    Args:
        user_id: Internal user ID
        image_hash: Hash of the image
    """
    db = await get_database()
    
    # Try to insert, or increment if exists
    existing = await check_image_hash(image_hash)
    
    if existing:
        await db.execute(
            "UPDATE image_hashes SET times_attempted = times_attempted + 1 WHERE hash = ?",
            (image_hash,)
        )
    else:
        await db.execute(
            "INSERT INTO image_hashes (hash, first_seen_by) VALUES (?, ?)",
            (image_hash, user_id)
        )
