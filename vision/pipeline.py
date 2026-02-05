"""
Main vision pipeline orchestrator.
Coordinates image download, processing, and data extraction.
"""

import cv2
import numpy as np
import aiohttp
from typing import Optional, Dict, Any, List
from io import BytesIO
from PIL import Image
import logging

from vision.grid_detector import GridDetector
from vision.tile_parser import TileParser
from vision.ocr import OCREngine
from utils.image_hash import compute_image_hash

logger = logging.getLogger(__name__)


class VisionPipeline:
    """Main pipeline for processing puzzle screenshots."""
    
    def __init__(self):
        """Initialize vision pipeline components."""
        self.grid_detector = GridDetector()
        self.tile_parser = TileParser()
        self.ocr = OCREngine()
    
    async def process_image_url(self, image_url: str) -> Dict[str, Any]:
        """
        Process an image from a URL (Discord attachment).
        
        Args:
            image_url: URL to image
            
        Returns:
            Dictionary with keys:
                - success: bool
                - image_hash: str
                - scene: str or None
                - pieces: List[Dict] with slot_index, stars, duplicates
                - error: str or None
        """
        result = {
            "success": False,
            "image_hash": None,
            "scene": None,
            "pieces": [],
            "error": None
        }
        
        try:
            # Download image
            image_data = await self._download_image(image_url)
            
            # Compute hash
            image_hash = compute_image_hash(image_data)
            result["image_hash"] = image_hash
            
            # Convert to OpenCV format
            image = self._bytes_to_cv2(image_data)
            
            # Extract scene name from isolated Header Zone
            header_region = self.grid_detector.get_header_region(image)
            scene = self.ocr.extract_scene_title(header_region)
            result["scene"] = scene
            
            # Detect puzzle board (Grid Zone)
            board_bbox = self.grid_detector.detect_puzzle_board(image)
            
            # Detect tiles
            # If board detected, we process the board region for cleaner tile detection
            if board_bbox:
                bx, by, bw, bh = board_bbox
                board_img = image[by:by+bh, bx:bx+bw]
                tiles = self.grid_detector.detect_tiles(board_img)
                # Adjust tile coordinates back to full image space
                tiles = [(tx + bx, ty + by, tw, th) for tx, ty, tw, th in tiles]
            else:
                tiles = self.grid_detector.detect_tiles(image)
            
            if not tiles:
                result["error"] = "No tiles detected in image"
                return result
            
            # Parse each tile
            pieces = []
            for slot_index, tile_bbox in enumerate(tiles, start=1):
                tile_image = self.grid_detector.extract_tile_image(image, tile_bbox)
                tile_data = self.tile_parser.parse_tile(tile_image)
                
                # Only include if we detected valid data
                if tile_data["stars"] > 0 or tile_data["confidence"] > 0.6:
                    pieces.append({
                        "slot_index": slot_index,
                        "stars": tile_data["stars"],
                        "duplicates": tile_data["duplicates"],
                        "confidence": tile_data["confidence"]
                    })
            
            result["pieces"] = pieces
            result["success"] = True
            
            # Optional: Cross-verify with progress bar if OCR found it (e.g., "10/12")
            # For now, we just log the findings
            logger.info(f"Processed image (Sectional): {len(pieces)} pieces found, scene={scene}")
            
        except Exception as e:
            logger.error(f"Vision pipeline failed: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result
    
    async def _download_image(self, url: str) -> bytes:
        """
        Download image from URL.
        
        Args:
            url: Image URL
            
        Returns:
            Image bytes
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download image: HTTP {response.status}")
                
                return await response.read()
    
    def _bytes_to_cv2(self, image_data: bytes) -> np.ndarray:
        """
        Convert image bytes to OpenCV format.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            OpenCV image (BGR format)
        """
        # Load with PIL
        pil_image = Image.open(BytesIO(image_data))
        
        # Convert to RGB (PIL uses RGB, OpenCV uses BGR)
        pil_image = pil_image.convert('RGB')
        
        # Convert to numpy array
        image_array = np.array(pil_image)
        
        # Convert RGB to BGR for OpenCV
        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
        
        return image_bgr
    
    def process_image_bytes(self, image_data: bytes) -> Dict[str, Any]:
        """
        Process image from bytes (synchronous version).
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Same format as process_image_url
        """
        result = {
            "success": False,
            "image_hash": None,
            "scene": None,
            "pieces": [],
            "error": None
        }
        
        try:
            # Compute hash
            image_hash = compute_image_hash(image_data)
            result["image_hash"] = image_hash
            
            # Convert to OpenCV format
            image = self._bytes_to_cv2(image_data)
            
            # Extract scene name from isolated Header Zone
            header_region = self.grid_detector.get_header_region(image)
            scene = self.ocr.extract_scene_title(header_region)
            result["scene"] = scene
            
            # Detect puzzle board (Grid Zone)
            board_bbox = self.grid_detector.detect_puzzle_board(image)
            
            # Detect tiles
            if board_bbox:
                bx, by, bw, bh = board_bbox
                board_img = image[by:by+bh, bx:bx+bw]
                tiles = self.grid_detector.detect_tiles(board_img)
                tiles = [(tx + bx, ty + by, tw, th) for tx, ty, tw, th in tiles]
            else:
                tiles = self.grid_detector.detect_tiles(image)
            
            if not tiles:
                result["error"] = "No tiles detected in image"
                return result
            
            # Parse each tile
            pieces = []
            for slot_index, tile_bbox in enumerate(tiles, start=1):
                tile_image = self.grid_detector.extract_tile_image(image, tile_bbox)
                tile_data = self.tile_parser.parse_tile(tile_image)
                
                if tile_data["stars"] > 0 or tile_data["confidence"] > 0.6:
                    pieces.append({
                        "slot_index": slot_index,
                        "stars": tile_data["stars"],
                        "duplicates": tile_data["duplicates"],
                        "confidence": tile_data["confidence"]
                    })
            
            result["pieces"] = pieces
            result["success"] = True
            
        except Exception as e:
            logger.error(f"Vision pipeline failed: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result


async def process_multiple_images(image_urls: List[str]) -> List[Dict[str, Any]]:
    """
    Process multiple images in parallel.
    
    Args:
        image_urls: List of image URLs
        
    Returns:
        List of results (one per image)
    """
    pipeline = VisionPipeline()
    
    # Process all images
    results = []
    for url in image_urls:
        result = await pipeline.process_image_url(url)
        results.append(result)
    
    return results
