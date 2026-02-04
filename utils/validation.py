"""
Input validation utilities.
Provides helper functions for validating user inputs.
"""

import re
from typing import Optional


def is_valid_discord_id(discord_id: str) -> bool:
    """
    Validate Discord user ID format.
    
    Args:
        discord_id: Discord ID string
        
    Returns:
        True if valid
    """
    # Discord IDs are numeric strings, typically 17-19 digits
    return bool(re.match(r'^\d{17,19}$', discord_id))


def sanitize_input(text: str, max_length: int = 100) -> str:
    """
    Sanitize user input text.
    
    Args:
        text: Raw input text
        max_length: Maximum allowed length
        
    Returns:
        Sanitized text
    """
    # Strip whitespace
    text = text.strip()
    
    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]
    
    return text


def parse_slot_index(slot_str: str) -> Optional[int]:
    """
    Parse slot index from user input.
    
    Args:
        slot_str: Slot string (e.g., "5", "slot 5", "#5")
        
    Returns:
        Slot index as integer, or None if invalid
    """
    # Remove common prefixes
    slot_str = slot_str.lower().strip()
    slot_str = slot_str.replace("slot", "").replace("#", "").strip()
    
    try:
        slot_index = int(slot_str)
        return slot_index if slot_index > 0 else None
    except ValueError:
        return None
