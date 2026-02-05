"""
Grid detection for puzzle piece images.
Uses OpenCV to dynamically detect and sort tiles.
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class GridDetector:
    """Detects grid layout in puzzle screenshots."""
    
    def __init__(self, min_tile_area: int = 1000, max_tile_area: int = 50000):
        """
        Initialize grid detector.
        
        Args:
            min_tile_area: Minimum area for a valid tile (pixels)
            max_tile_area: Maximum area for a valid tile (pixels)
        """
        self.min_tile_area = min_tile_area
        self.max_tile_area = max_tile_area
    
    def detect_tiles(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect puzzle tiles in an image.
        
        Args:
            image: Input image (BGR format from OpenCV)
            
        Returns:
            List of bounding boxes (x, y, width, height) sorted top-to-bottom, left-to-right
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to preserve edges while removing noise
        blurred = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Adaptive thresholding to find tile borders
        thresh = cv2.adaptiveThreshold(
            blurred, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 
            11, 2
        )
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter and extract bounding boxes
        potential_tiles = []
        for contour in contours:
            area = cv2.contourArea(contour)
            
            # Filter by area (puzzle tiles are usually substantial)
            if self.min_tile_area <= area <= self.max_tile_area:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by aspect ratio (tiles should be nearly square)
                aspect_ratio = w / h if h > 0 else 0
                if 0.8 <= aspect_ratio <= 1.2:  # Tightened aspect ratio
                    potential_tiles.append((x, y, w, h))
        
        if not potential_tiles:
            logger.warning("No potential tiles found")
            return []
            
        # Refine: Keep only tiles that are similar in size to the median tile
        # This helps exclude small UI icons or large layout boxes
        areas = [w * h for x, y, w, h in potential_tiles]
        median_area = np.median(areas)
        
        tiles = []
        for tile in potential_tiles:
            tile_area = tile[2] * tile[3]
            if 0.7 * median_area <= tile_area <= 1.3 * median_area:
                tiles.append(tile)
        
        # Sort tiles: top-to-bottom, left-to-right
        tiles = self._sort_tiles(tiles)
        
        logger.info(f"Detected {len(tiles)} tiles after filtering outliers")
        return tiles
    
    def _sort_tiles(self, tiles: List[Tuple[int, int, int, int]]) -> List[Tuple[int, int, int, int]]:
        """
        Sort tiles in reading order (top-to-bottom, left-to-right).
        
        Args:
            tiles: List of (x, y, w, h) tuples
            
        Returns:
            Sorted list of tiles
        """
        if not tiles:
            return []
        
        # Group tiles by rows (tiles with similar y-coordinates)
        # Calculate average tile height
        avg_height = sum(h for _, _, _, h in tiles) / len(tiles)
        row_threshold = avg_height * 0.5  # Tiles within 50% of avg height are in same row
        
        # Sort by y first
        tiles_sorted_by_y = sorted(tiles, key=lambda t: t[1])
        
        # Group into rows
        rows = []
        current_row = [tiles_sorted_by_y[0]]
        current_y = tiles_sorted_by_y[0][1]
        
        for tile in tiles_sorted_by_y[1:]:
            if abs(tile[1] - current_y) <= row_threshold:
                # Same row
                current_row.append(tile)
            else:
                # New row
                rows.append(current_row)
                current_row = [tile]
                current_y = tile[1]
        
        # Add last row
        if current_row:
            rows.append(current_row)
        
        # Sort each row by x-coordinate (left-to-right)
        sorted_tiles = []
        for row in rows:
            row_sorted = sorted(row, key=lambda t: t[0])
            sorted_tiles.extend(row_sorted)
        
        return sorted_tiles
    
    def extract_tile_image(
        self,
        image: np.ndarray,
        bbox: Tuple[int, int, int, int],
        padding: int = 5
    ) -> np.ndarray:
        """
        Extract a tile from the image.
        
        Args:
            image: Source image
            bbox: Bounding box (x, y, w, h)
            padding: Padding to add around tile (pixels)
            
        Returns:
            Cropped tile image
        """
        x, y, w, h = bbox
        
        # Add padding (with bounds checking)
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(image.shape[1], x + w + padding)
        y2 = min(image.shape[0], y + h + padding)
        
        return image[y1:y2, x1:x2]


def detect_grid_alternative(image: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """
    Alternative grid detection using adaptive thresholding.
    Fallback method if contour detection fails.
    
    Args:
        image: Input image (BGR format)
        
    Returns:
        List of bounding boxes
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Adaptive thresholding
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )
    
    # Morphological operations to clean up
    kernel = np.ones((3, 3), np.uint8)
    cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # Find contours
    contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Extract bounding boxes
    tiles = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 1000:  # Minimum area threshold
            x, y, w, h = cv2.boundingRect(contour)
            tiles.append((x, y, w, h))
    
    return tiles
