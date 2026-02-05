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
    
    def extract_scene_title(self, image: np.ndarray, top_region_ratio: float = 0.2) -> Optional[str]:
        """
        Extract scene title from top region of image.
        Focuses on the left side of the header where the title usually is.
        
        Args:
            image: Input image (BGR format)
            top_region_ratio: Ratio of image height to use for title region (default: 20%)
            
        Returns:
            Scene title or None if not detected
        """
        try:
            # Extract top region
            height, width = image.shape[:2]
            top_height = int(height * top_region_ratio)
            # Focus on the left 60% of the header to avoid "Complete this Scene..." text
            header = image[0:top_height, 0:int(width * 0.6)]
            
            # Preprocess
            preprocessed = self._preprocess_for_ocr(header)
            
            # Run OCR with page segmentation mode 6 (Assume a single uniform block of text)
            # or 11 (Sparse text)
            text = pytesseract.image_to_string(
                preprocessed,
                config='--psm 6'
            )
            
            # Clean up result - remove common OCR artifacts/instructions
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Filter lines: skip "Complete this...", skip very short ones
            ignore_keywords = ["complete", "scene", "obtain", "reward", "this", "to"]
            filtered_lines = []
            for line in lines:
                lower_line = line.lower()
                if any(kw in lower_line for kw in ignore_keywords) and len(lower_line) > 15:
                    continue
                if len(line) > 3:
                    filtered_lines.append(line)
            
            if filtered_lines:
                # Usually the scene title is the longest or most prominent text in the header box
                scene_title = max(filtered_lines, key=len)
                logger.info(f"Detected scene title: {scene_title}")
                return scene_title
            
            logger.warning("No scene title text detected")
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
        
        # Apply adaptive thresholding to handle uneven lighting
        thresh = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 
            11, 2
        )
        
        # Check if we should invert (OCR generally likes black text on white background)
        # Count white vs black pixels
        white_pixels = cv2.countNonZero(thresh)
        total_pixels = thresh.shape[0] * thresh.shape[1]
        if white_pixels > total_pixels * 0.5:
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
