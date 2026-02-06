import aiohttp
from typing import Optional, Dict, Any, List
from io import BytesIO
from PIL import Image
import logging
import asyncio

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
            
            PROMPT = (
                "You are analyzing multiple screenshots from the mobile game 'Whiteout Survival'. "
                "All screenshots were uploaded by the SAME user.\n\n"
            
                "Your task is to build a SINGLE, FINAL inventory for each scene visible in the screenshots.\n\n"
            
                "SCENE GROUPING RULES:\n"
                "1. Each screenshot contains a scene title shown at the top of the screen "
                "(e.g., 'Honor and Glory', 'Mining the Fire').\n"
                "2. Screenshots with DIFFERENT scene titles must ALWAYS be handled separately.\n"
                "3. Screenshots with the SAME scene title belong to the SAME scene inventory for the SAME user.\n"
                "4. Screenshots are evidence only; they do not represent inventory by themselves.\n\n"
            
                "SCROLLING AND OVERLAP RULES:\n"
                "5. A scene may contain more than 12 pieces.\n"
                "6. Screenshots may show only PARTIAL views of a scene due to scrolling.\n"
                "7. Screenshots from the same scene may overlap and show some of the SAME pieces.\n"
                "8. Overlap is expected and must NOT cause duplication.\n\n"
            
                "PIECE IDENTITY RULES:\n"
                "9. Within a single scene, each puzzle piece has a UNIQUE visual design.\n"
                "10. If two pieces from DIFFERENT screenshots have the SAME scene title "
                "and the SAME visual design, they represent the SAME puzzle piece.\n"
                "11. Pieces must NEVER be matched across different scenes, even if they look similar.\n\n"
            
                "INVENTORY RULES:\n"
                "12. The puzzle grid is always 3 columns by N rows.\n"
                "13. Slot indexing is GLOBAL PER SCENE and must be assigned left-to-right, "
                "top-to-bottom starting at slot_index = 1.\n"
                "14. Owned = the tile is colored.\n"
                "15. Missing = the tile is gray or shadowed.\n"
                "16. Duplicates = the number shown in a green '+N' badge (default 0).\n"
                "17. Locked = true ONLY if the piece has exactly 5 stars.\n"
                "18. Never decrease duplicates.\n"
                "19. Never infer trades.\n"
                "20. Never invent pieces that are not visible in at least one screenshot.\n\n"
            
                "CONFLICT RESOLUTION RULES:\n"
                "21. If the SAME piece appears in multiple screenshots with different values:\n"
                "- Prefer owned = true over false.\n"
                "- Prefer the HIGHER duplicate count.\n"
                "- Prefer locked = true over false.\n\n"
            
                "OUTPUT FORMAT:\n"
                "For EACH scene detected, output ONE JSON object with this structure:\n"
                "{\n"
                "  \"scene\": \"<scene name>\",\n"
                "  \"total_slots\": <integer>,\n"
                "  \"pieces\": [\n"
                "    {\n"
                "      \"slot_index\": <integer>,\n"
                "      \"owned\": <true|false>,\n"
                "      \"duplicates\": <integer>,\n"
                "      \"locked\": <true|false>\n"
                "    }\n"
                "  ]\n"
                "}\n\n"
            
                "If a progress bar like '10 / 18' is visible, use the second number as total_slots.\n"
                "If no progress bar is visible, infer total_slots from the highest slot_index observed.\n\n"
            
                "Respond ONLY with valid JSON. "
                "Do NOT include explanations, markdown, or extra text."
            )

            # Use client.aio for true async support with retries
            max_retries = 3
            base_delay = 1  # seconds
            
            response = None
            for attempt in range(max_retries):
                try:
                    response = await client.aio.models.generate_content(
                        model='gemini-3-flash-preview',
                        contents=[
                            prompt,
                            types.Part.from_bytes(data=image_data, mime_type='image/png')
                        ]
                    )
                    break  # Success
                except Exception as e:
                    if "503" in str(e) or "429" in str(e) or "overloaded" in str(e).lower():
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            logger.warning(f"Gemini API overloaded/rate-limited (Attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                            await asyncio.sleep(delay)
                            continue
                    raise e  # Re-raise if not a transient error or out of retries
            
            if not response:
                return None
                
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
            
            # Convert the new 'owned' and 'locked' structure to our DB-ready structure
            # Logic: We only care about OWNED pieces. 
            # locked=True -> stars=5, locked=False -> stars=1 (arbitrary but enough to identify un-maxed)
            filtered_pieces = []
            for p in data["pieces"]:
                if p.get("owned", False):
                    filtered_pieces.append({
                        "slot_index": p["slot_index"],
                        "stars": 5 if p.get("locked", False) else 1,
                        "duplicates": p.get("duplicates", 0)
                    })
            
            return {
                "scene": data["scene"],
                "pieces": filtered_pieces
            }
            
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
