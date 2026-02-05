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
    
    def __init__(self, min_tile_area: int = 500, max_tile_area: int = 500000):
        """
        Initialize grid detector.
        
        Args:
            min_tile_area: Minimum area for a valid tile (pixels) - Default low to catch tiny pieces
            max_tile_area: Maximum area for a valid tile (pixels) - Default high for high-res screens
        """
        self.min_tile_area = min_tile_area
        self.max_tile_area = max_tile_area
        self.board_bbox = None
    
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
        height, width = image.shape[:2]
        total_area = height * width
        
        # Dynamic area thresholds based on image size
        # A tile should be at least ~0.5% and at most ~15% of the total area
        img_min_area = total_area * 0.005 
        img_max_area = total_area * 0.15
        
        # Use the most restrictive of fixed vs dynamic thresholds
        actual_min_area = max(self.min_tile_area, img_min_area)
        actual_max_area = min(self.max_tile_area, img_max_area)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            
            if actual_min_area <= area <= actual_max_area:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by aspect ratio (tiles should be nearly square)
                aspect_ratio = w / h if h > 0 else 0
                if 0.7 <= aspect_ratio <= 1.4:  # Loosened aspect ratio
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

    def detect_puzzle_board(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Identify the main puzzle board/parchment area.
        This allows us to isolate tiles from title cards, buttons, etc.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (11, 11), 0)
        
        # Use Canny to get strong edges
        edges = cv2.Canny(blurred, 30, 150)
        
        # Dilate edges to close gaps
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        height, width = image.shape[:2]
        img_area = height * width
        
        # We look for a large rectangular contour in the middle-ish of the screen
        best_board = None
        max_board_area = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            # A board should be at least 30% of the image area
            if area > img_area * 0.3:
                x, y, w, h = cv2.boundingRect(contour)
                # Aspect ratio for a 3x3 or 3x4 grid is usually between 0.6 and 1.5
                aspect = w / h if h > 0 else 0
                if 0.5 <= aspect <= 1.8:
                    if area > max_board_area:
                        max_board_area = area
                        best_board = (x, y, w, h)
        
        if best_board:
            logger.info(f"Detected puzzle board at {best_board} (area: {max_board_area/img_area:.1%})")
        return best_board

    def get_header_region(self, image: np.ndarray) -> np.ndarray:
        """
        Isolate the top header card containing the scene name.
        """
        height, width = image.shape[:2]
        # Usually occupies the top 25%
        header_height = int(height * 0.25)
        # Often slightly inset from edges
        x_start = int(width * 0.05)
        x_end = int(width * 0.95)
        
        return image[0:header_height, x_start:x_end]
    
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
