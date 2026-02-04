"""
Image hashing utilities for deduplication.
Uses perceptual hashing to detect duplicate images.
"""

import imagehash
from PIL import Image
from io import BytesIO
import logging

logger = logging.getLogger(__name__)


def compute_image_hash(image_data: bytes) -> str:
    """
    Compute perceptual hash of an image.
    
    Uses pHash (perceptual hash) which is robust to:
    - Minor edits
    - Compression
    - Scaling
    - Slight color changes
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        Hash string (hex format)
    """
    try:
        # Load image from bytes
        image = Image.open(BytesIO(image_data))
        
        # Compute perceptual hash
        phash = imagehash.phash(image)
        
        # Convert to string
        hash_str = str(phash)
        
        logger.debug(f"Computed image hash: {hash_str}")
        return hash_str
        
    except Exception as e:
        logger.error(f"Failed to compute image hash: {e}")
        raise


def images_are_similar(hash1: str, hash2: str, threshold: int = 5) -> bool:
    """
    Check if two image hashes are similar.
    
    Args:
        hash1: First image hash
        hash2: Second image hash
        threshold: Maximum hamming distance to consider similar (default: 5)
        
    Returns:
        True if images are similar
    """
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        
        # Compute hamming distance
        distance = h1 - h2
        
        return distance <= threshold
        
    except Exception as e:
        logger.error(f"Failed to compare hashes: {e}")
        return False
