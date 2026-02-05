"""
Tile parser for extracting piece information from individual tiles.
Detects stars and duplicates using template matching and color detection.
"""

import cv2
import numpy as np
from typing import Optional, Dict, Any, List
from vision.ocr import OCREngine
import logging

logger = logging.getLogger(__name__)


class TileParser:
    """Parses individual puzzle tiles to extract stars and duplicates."""
    
    def __init__(self, star_templates: Optional[List[np.ndarray]] = None):
        """
        Initialize tile parser.
        
        Args:
            star_templates: Optional list of star template images for matching
        """
        self.star_templates = star_templates or []
        self.ocr = OCREngine()
    
    def parse_tile(self, tile_image: np.ndarray) -> Dict[str, Any]:
        """
        Parse a single tile to extract piece information.
        
        Args:
            tile_image: Cropped tile image
            
        Returns:
            Dictionary with keys: stars, duplicates, confidence
        """
        result = {
            "stars": 0,
            "duplicates": 0,
            "confidence": 0.0
        }
        
        try:
            # Detect stars
            stars, star_confidence = self._detect_stars(tile_image)
            result["stars"] = stars
            
            # Detect duplicates
            duplicates, dup_confidence = self._detect_duplicates(tile_image)
            result["duplicates"] = duplicates
            
            # Overall confidence
            result["confidence"] = (star_confidence + dup_confidence) / 2
            
        except Exception as e:
            logger.error(f"Failed to parse tile: {e}")
        
        return result
    
    def _detect_stars(self, tile_image: np.ndarray) -> tuple[int, float]:
        """
        Detect number of stars in a tile.
        
        Strategy:
        1. Look for star-shaped contours
        2. Count distinct star regions
        3. Fallback to template matching if available
        
        Args:
            tile_image: Tile image
            
        Returns:
            (star_count, confidence)
        """
        # Convert to HSV for better color detection
        hsv = cv2.cvtColor(tile_image, cv2.COLOR_BGR2HSV)
        
        # Define yellow/gold color range for stars
        # Use lower saturation/value to catch highlights and smaller stars
        lower_yellow = np.array([15, 40, 40])
        upper_yellow = np.array([50, 255, 255])
        
        # Create mask for star color
        mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Count star-like contours
        star_count = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 15:  # Lowered further for smaller stars in high-res
                star_count += 1
        
        # Pieces can have 0 stars if they are grayed out/missing
        star_count = min(star_count, 5)
        
        # Confidence based on detection clarity
        confidence = 0.8 if star_count > 0 else 0.5
        
        logger.debug(f"Detected {star_count} stars (confidence: {confidence})")
        return star_count, confidence
    
    def _detect_duplicates(self, tile_image: np.ndarray) -> tuple[int, float]:
        """
        Detect number of duplicates from badge.
        
        Strategy:
        1. Look for badge region (bottom-right corner)
        2. Use color detection to find badge
        3. OCR to extract number
        
        Args:
            tile_image: Tile image
            
        Returns:
            (duplicate_count, confidence)
        """
        # Look for badge in bottom-right corner (based on provided screenshots)
        height, width = tile_image.shape[:2]
        # Badge is typically in the bottom 35% and right 50%
        badge_region = tile_image[int(height*0.65):height, int(width*0.5):width]
        
        # Convert to HSV
        hsv = cv2.cvtColor(badge_region, cv2.COLOR_BGR2HSV)
        
        # Define color range for duplicate badge (usually green)
        # Lenient thresholds for varied lighting
        lower_green = np.array([30, 30, 30])
        upper_green = np.array([90, 255, 255])
        
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Check if badge exists
        if cv2.countNonZero(mask) < 20: # Lowered threshold
            # No badge detected = 0 duplicates
            return 0, 0.9
        
        # Try OCR on badge region
        duplicate_count = self.ocr.extract_number_from_badge(badge_region)
        
        if duplicate_count is not None:
            return duplicate_count, 0.9
        else:
            # Fallback: assume 1 duplicate if badge exists (+1)
            # Screenshots show +1, +4 etc. The '+' might confuse OCR sometimes.
            return 1, 0.5
    
    def _template_match_stars(self, tile_image: np.ndarray) -> Optional[int]:
        """
        Use template matching to detect stars (if templates are available).
        
        Args:
            tile_image: Tile image
            
        Returns:
            Star count or None if matching fails
        """
        if not self.star_templates:
            return None
        
        gray = cv2.cvtColor(tile_image, cv2.COLOR_BGR2GRAY)
        
        best_match = 0
        best_score = 0
        
        for i, template in enumerate(self.star_templates):
            # Template should be grayscale
            if len(template.shape) == 3:
                template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
            
            # Match template
            result = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            if max_val > best_score:
                best_score = max_val
                best_match = i + 1  # Template index = star count
        
        if best_score > 0.6:  # Confidence threshold
            return best_match
        
        return None


def create_star_templates() -> List[np.ndarray]:
    """
    Create synthetic star templates for matching.
    In production, these should be extracted from actual game screenshots.
    
    Returns:
        List of star template images (1-5 stars)
    """
    # This is a placeholder - in real implementation, you would:
    # 1. Extract star regions from sample screenshots
    # 2. Save them as template images
    # 3. Load them here
    
    templates = []
    
    # For now, return empty list
    # Templates should be added after analyzing actual game UI
    
    return templates
