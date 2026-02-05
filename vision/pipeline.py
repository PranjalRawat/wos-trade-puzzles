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

import google.generativeai as genai
from config import Config
from vision.constants import KNOWN_SCENES
from rapidfuzz import process, fuzz

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
            
            # Extract scene name using Multi-Pass OCR
            header_region = self.grid_detector.get_header_region(image)
            scene = self.ocr.extract_scene_title(header_region)
            
            # Fallback for scene name: Try full image if header crop failed
            if not scene:
                scene = self.ocr.extract_scene_title(image)
            
            # GOOGLE AI FALLBACK (Premium Vision)
            # If scene is still missing or looks like garbage, try Gemini Vision if API key is present
            if Config.GOOGLE_API_KEY and (not scene or len(scene) < 3 or any(c in scene for c in "——=€{")):
                logger.info("Local OCR failed or returned garbage, attempting Gemini Vision fallback...")
                gemini_scene = await self._process_with_gemini(image_data)
                if gemini_scene:
                    # Apply fuzzy matching to Gemini result as well to ensure normalization
                    match = process.extractOne(gemini_scene, KNOWN_SCENES, scorer=fuzz.WRatio)
                    if match and match[1] > 70:
                        scene = match[0]
                    else:
                        scene = gemini_scene
                    logger.info(f"Gemini Vision recovered scene: {scene}")
                
            result["scene"] = scene
            
            # Multi-Pass Grid Detection
            tiles = self.grid_detector.detect_tiles_multi_pass(image)
            
            if not tiles:
                # Last resort fallback: simple detection
                from vision.grid_detector import detect_grid_alternative
                tiles = detect_grid_alternative(image)
                
            if not tiles:
                result["error"] = "No tiles detected in image"
                return result
            
            # Parse each tile
            pieces = []
            for slot_index, tile_bbox in enumerate(tiles, start=1):
                tile_image = self.grid_detector.extract_tile_image(image, tile_bbox)
                tile_data = self.tile_parser.parse_tile(tile_image)
                
                # Confidence-based inclusion
                # If we see stars, it's definitely a piece. 
                # If no stars but high confidence, we still take it (might be missing/empty)
                if tile_data["stars"] > 0 or tile_data["confidence"] > 0.4:
                    pieces.append({
                        "slot_index": slot_index,
                        "stars": tile_data["stars"],
                        "duplicates": tile_data["duplicates"],
                        "confidence": tile_data["confidence"]
                    })
            
            result["pieces"] = pieces
            result["success"] = True
            
            logger.info(f"Processed image (Multi-Pass + Gemini): {len(pieces)} pieces found, scene={scene}")
            
        except Exception as e:
            logger.error(f"Vision pipeline failed: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result

    async def _process_with_gemini(self, image_data: bytes) -> Optional[str]:
        """
        Use Google Gemini 1.5 Flash to extract the scene name.
        Requires GOOGLE_API_KEY in .env.
        """
        try:
            genai.configure(api_key=Config.GOOGLE_API_KEY)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Convert bytes to PIL Image for Gemini
            pil_img = Image.open(BytesIO(image_data))
            
            prompt = (
                "This is a screenshot from a puzzle game. "
                "Look at the header area and tell me the name of the 'Scene'. "
                "Respond ONLY with the scene name, no extra text. "
                "Example: 'Honor and Glory', 'Rekindled Flames'."
            )
            
            response = model.generate_content([prompt, pil_img])
            text = response.text.strip()
            
            # Basic cleanup
            if ":" in text:
                text = text.split(":")[-1].strip()
            
            return text if len(text) > 2 else None
            
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            return None
    
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
            
            # Extract scene name using Multi-Pass OCR
            header_region = self.grid_detector.get_header_region(image)
            scene = self.ocr.extract_scene_title(header_region)
            
            # Fallback for scene name: Try full image if header crop failed
            if not scene:
                scene = self.ocr.extract_scene_title(image)
                
            # Note: Gemini fallback is not implemented in sync process_image_bytes
            # since the Gemini API is async. Use process_image_url for premium results.
            
            result["scene"] = scene
            
            # Multi-Pass Grid Detection
            tiles = self.grid_detector.detect_tiles_multi_pass(image)
            
            if not tiles:
                # Last resort fallback: simple detection
                from vision.grid_detector import detect_grid_alternative
                tiles = detect_grid_alternative(image)
                
            if not tiles:
                result["error"] = "No tiles detected in image"
                return result
            
            # Parse each tile
            pieces = []
            for slot_index, tile_bbox in enumerate(tiles, start=1):
                tile_image = self.grid_detector.extract_tile_image(image, tile_bbox)
                tile_data = self.tile_parser.parse_tile(tile_image)
                
                if tile_data["stars"] > 0 or tile_data["confidence"] > 0.4:
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
