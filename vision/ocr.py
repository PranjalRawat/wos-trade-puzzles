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
    
    def extract_scene_title(self, image: np.ndarray, top_region_ratio: float = 0.15) -> Optional[str]:
        """
        Extract scene title from top region of image.
        
        Args:
            image: Input image (BGR format)
            top_region_ratio: Ratio of image height to use for title region (default: 15%)
            
        Returns:
            Scene title or None if not detected
        """
        try:
            # Extract top region
            height = image.shape[0]
            top_height = int(height * top_region_ratio)
            top_region = image[0:top_height, :]
            
            # Preprocess for better OCR
            preprocessed = self._preprocess_for_ocr(top_region)
            
            # Run OCR
            text = pytesseract.image_to_string(
                preprocessed,
                config='--psm 7'  # Single line mode
            )
            
            # Clean up result
            text = text.strip()
            
            if text:
                logger.info(f"Detected scene title: {text}")
                return text
            else:
                logger.warning("No text detected in top region")
                return None
                
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return None
    
    def _preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR accuracy.
        
        Args:
            image: Input image
            
        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Increase contrast
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(enhanced)
        
        # Threshold
        _, thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
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
