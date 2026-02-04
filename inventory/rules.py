"""
Validation rules for inventory data.
Ensures data integrity before database operations.
"""

from typing import Optional


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


def validate_stars(stars: int) -> None:
    """
    Validate star count.
    
    Args:
        stars: Number of stars (1-5)
        
    Raises:
        ValidationError: If stars is not between 1 and 5
    """
    if not isinstance(stars, int):
        raise ValidationError(f"Stars must be an integer, got {type(stars).__name__}")
    
    if stars < 1 or stars > 5:
        raise ValidationError(f"Stars must be between 1 and 5, got {stars}")


def validate_duplicates(duplicates: int) -> None:
    """
    Validate duplicate count.
    
    Args:
        duplicates: Number of duplicates (>= 0)
        
    Raises:
        ValidationError: If duplicates is negative
    """
    if not isinstance(duplicates, int):
        raise ValidationError(f"Duplicates must be an integer, got {type(duplicates).__name__}")
    
    if duplicates < 0:
        raise ValidationError(f"Duplicates must be >= 0, got {duplicates}")


def validate_scene(scene: str) -> None:
    """
    Validate scene name.
    
    Args:
        scene: Scene name
        
    Raises:
        ValidationError: If scene is empty or invalid
    """
    if not isinstance(scene, str):
        raise ValidationError(f"Scene must be a string, got {type(scene).__name__}")
    
    scene = scene.strip()
    
    if not scene:
        raise ValidationError("Scene name cannot be empty")
    
    if len(scene) > 100:
        raise ValidationError(f"Scene name too long (max 100 chars), got {len(scene)}")


def validate_slot_index(slot_index: int) -> None:
    """
    Validate slot index.
    
    Args:
        slot_index: Slot position (must be positive)
        
    Raises:
        ValidationError: If slot_index is not positive
    """
    if not isinstance(slot_index, int):
        raise ValidationError(f"Slot index must be an integer, got {type(slot_index).__name__}")
    
    if slot_index < 1:
        raise ValidationError(f"Slot index must be >= 1, got {slot_index}")


def validate_piece_data(scene: str, slot_index: int, stars: int, duplicates: int) -> None:
    """
    Validate all piece data at once.
    
    Args:
        scene: Scene name
        slot_index: Slot position
        stars: Star count (1-5)
        duplicates: Duplicate count (>= 0)
        
    Raises:
        ValidationError: If any validation fails
    """
    validate_scene(scene)
    validate_slot_index(slot_index)
    validate_stars(stars)
    validate_duplicates(duplicates)


def normalize_scene_name(scene: str) -> str:
    """
    Normalize scene name for consistent storage.
    
    Args:
        scene: Raw scene name
        
    Returns:
        Normalized scene name (trimmed, title case)
    """
    return scene.strip().title()
