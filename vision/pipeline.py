import aiohttp
from typing import Optional, Dict, Any, List
from io import BytesIO
from PIL import Image
import logging

from utils.image_hash import compute_image_hash
from config import Config

logger = logging.getLogger(__name__)


class VisionPipeline:
    """Main pipeline for processing puzzle screenshots (Strict AI-Only)."""
    
    def __init__(self):
        """Initialize vision pipeline (AI Only)."""
        pass
    
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
            
            # Compute hash (for deduplication)
            image_hash = compute_image_hash(image_data)
            result["image_hash"] = image_hash
            
            # STRICT AI-ONLY SCANNING (Gemini 3 Flash)
            if not Config.GOOGLE_API_KEY:
                result["error"] = "STRICT AI VISION REQUIRED: Please set GOOGLE_API_KEY in .env to use Gemini 3 Flash scanning."
                logger.error("Scan failed: GOOGLE_API_KEY missing in strict AI mode.")
                return result

            logger.info("Executing strict AI vision scan with Gemini 3 Flash...")
            ai_data = await self._process_with_gemini(image_data)
            
            if ai_data:
                result["scene"] = ai_data.get("scene")
                result["pieces"] = ai_data.get("pieces", [])
                result["success"] = True
                logger.info(f"AI Scan Successful: {len(result['pieces'])} pieces found in '{result['scene']}'")
            else:
                result["error"] = "AI Vision failed to extract data. Please ensure the image is a clear Whiteout Survival screenshot."
                logger.error("Gemini AI extraction failed.")
                
        except Exception as e:
            logger.error(f"Vision pipeline failed: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result

    async def _process_with_gemini(self, image_data: bytes) -> Optional[Dict[str, Any]]:
        """
        Use Google Gemini 3 Flash to extract the scene name and piece data.
        Uses the new google-genai SDK (Async).
        """
        try:
            import json
            import google.genai as genai
            from google.genai import types
            
            # Using the async client
            client = genai.Client(api_key=Config.GOOGLE_API_KEY)
            
            prompt = (
                "This is a screenshot from a puzzle game called 'Whiteout Survival'. "
                "The image shows a 3x4 grid of puzzle tiles. "
                "Please analyze the image and return a JSON object with the following structure: "
                "{\n"
                "  \"scene\": \"The name of the scene from the top header\",\n"
                "  \"pieces\": [\n"
                "    { \"slot_index\": 1, \"stars\": 1, \"duplicates\": 0 },\n"
                "    ...\n"
                "  ]\n"
                "}\n"
                "Rules:\n"
                "1. 'scene' is the title text at the top (e.g., 'Honor and Glory').\n"
                "2. There are exactly 12 slots (indexed 1 to 12). Only include slots that are visible and owned.\n"
                "3. 'stars' is the count of yellow stars (1-5). Use 1 if only the slot is visible but no stars are clear.\n"
                "4. 'duplicates' is the number in the green badge (if any). Default to 0.\n"
                "Respond ONLY with the JSON block. No markdown markers."
            )
            
            # Use client.aio for true async support
            response = await client.aio.models.generate_content(
                model='gemini-3-flash-preview',
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_data, mime_type='image/png')
                ]
            )
            
            text = response.text.strip()
            logger.debug(f"Gemini raw response: {text}")
            
            # Remove markdown markers if present
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "").strip()
            elif text.startswith("```"):
                text = text.replace("```", "").strip()
                
            data = json.loads(text)
            
            # Ensure basic structure
            if "scene" not in data or "pieces" not in data:
                logger.warning("Gemini JSON missing required fields")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"Gemini API (google-genai async) failed: {e}")
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
