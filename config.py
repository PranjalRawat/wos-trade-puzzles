"""
Configuration management for Discord Puzzle Trading Bot.
Loads settings from environment variables.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import logging

# Load .env file
load_dotenv()


class Config:
    """Application configuration."""
    
    # Discord
    DISCORD_TOKEN: str = os.getenv("DISCORD_TOKEN", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "puzzle_bot.db")
    
    # Tesseract (optional)
    TESSERACT_PATH: str = os.getenv("TESSERACT_PATH", "")
    
    # Google API Key (for Gemini Vision)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Vision settings
    MIN_TILE_AREA: int = int(os.getenv("MIN_TILE_AREA", "1000"))
    MAX_TILE_AREA: int = int(os.getenv("MAX_TILE_AREA", "50000"))
    
    # Bot settings
    COMMAND_PREFIX: str = os.getenv("COMMAND_PREFIX", "/")
    
    @classmethod
    def validate(cls) -> None:
        """Validate required configuration."""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required. Set it in .env file.")
        
        if not cls.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is required for High-Quality AI Scanning. Set it in .env file.")
        
        logging.info(f"GOOGLE_API_KEY found (starts with: {cls.GOOGLE_API_KEY[:4]}...)")
    
    @classmethod
    def setup_logging(cls) -> None:
        """Configure logging."""
        level = getattr(logging, cls.LOG_LEVEL.upper(), logging.INFO)
        
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


# Validate config on import
Config.validate()
Config.setup_logging()
