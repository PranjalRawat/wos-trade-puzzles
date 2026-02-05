"""
OCR utilities for extracting text from images.
Uses Tesseract for scene title detection.
"""

import cv2
import numpy as np
import pytesseract
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class OCREngine:
    """OCR engine for extracting text from puzzle screenshots."""
    
    def __init__(self, tesseract_path: Optional[str] = None):
        """
        Initialize OCR engine.
        
        Args:
            tesseract_path: Optional path to Tesseract executable
        """
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
    
    def extract_scene_title(self, image: np.ndarray, top_region_ratio: float = 0.25) -> Optional[str]:
        """
        Extract scene title from image using multiple OCR passes if needed.
        """
        try:
            # Check if image is already a small header region or full screenshot
            height, width = image.shape[:2]
            
            # If height/width ratio is small (e.g., < 0.4), it's likely already a header crop
            if height / width < 0.4:
                header = image
            else:
                top_height = int(height * top_region_ratio)
                header = image[0:top_height, 0:int(width * 0.9)]
            
            # Preprocess
            preprocessed = self._preprocess_for_ocr(header)
            
            # Multi-Pass OCR: Try different PSM modes
            # Mode 3: Automatic (default)
            # Mode 11: Sparse text
            # Mode 6: Single block
            psm_modes = [3, 11, 6]
            
            best_titles = []
            
            for psm in psm_modes:
                text = pytesseract.image_to_string(
                    preprocessed,
                    config=f'--psm {psm}'
                )
                
                # Clean up result
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                # Filter lines
                ignore_keywords = ["complete", "obtain", "reward", "this", "to", "tap", "click", "collect"]
                filtered_lines = []
                for line in lines:
                    lower_line = line.lower()
                    if any(kw in lower_line for kw in ignore_keywords) and len(lower_line) > 8:
                        continue
                    if "/" in line and any(c.isdigit() for c in line): # Skip "10/12"
                        continue
                    if len(line.strip()) < 3:
                        continue
                    filtered_lines.append(line.strip())
                
                if filtered_lines:
                    # Pick the best candidate from this pass
                    # We prefer titles that aren't too long or too short
                    candidates = [l for l in filtered_lines if 3 <= len(l) <= 30]
                    if candidates:
                        # Usually the first candidate in high-res images is the title
                        best_titles.append(candidates[0])
            
            if best_titles:
                # Pick the most common or first successful result
                # For now, just return the first one found
                result = best_titles[0]
                logger.info(f"Detected scene title (Multi-Pass): {result}")
                return result
            
            logger.warning("No scene title text detected after all passes")
            return None
                
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return None
                
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return None
    
    def _preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        Handles both dark-on-light and light-on-dark text.
        
        Args:
            image: Input image
            
        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Resize to improve OCR (upscale 2x)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            11, 2
        )
        
        # Ensure black text on white background (OCR preference)
        white_pixels = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        # If image is mostly black, it's likely white text on black background.
        # We invert it to get black text on white background.
        if white_pixels < total_pixels * 0.3: # Threshold 0.3 for sparse text
            thresh = cv2.bitwise_not(thresh)
            
        return thresh
    
    def extract_number_from_badge(self, badge_image: np.ndarray) -> Optional[int]:
        """
        Extract number from duplicate badge.
        
        Args:
            badge_image: Cropped badge region
            
        Returns:
            Number or None if not detected
        """
        try:
            # Preprocess
            preprocessed = self._preprocess_for_ocr(badge_image)
            
            # Run OCR with digits-only mode
            text = pytesseract.image_to_string(
                preprocessed,
                config='--psm 10 -c tessedit_char_whitelist=0123456789'
            )
            
            # Parse number
            text = text.strip()
            if text.isdigit():
                number = int(text)
                logger.debug(f"Detected badge number: {number}")
                return number
            else:
                logger.warning(f"Invalid badge text: {text}")
                return None
                
        except Exception as e:
            logger.error(f"Badge OCR failed: {e}")
            return None


def extract_text_simple(image: np.ndarray) -> str:
    """
    Simple text extraction without preprocessing.
    
    Args:
        image: Input image
        
    Returns:
        Extracted text
    """
    try:
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        logger.error(f"Simple OCR failed: {e}")
        return ""
