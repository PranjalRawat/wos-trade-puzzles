"""
Database connection manager for Discord Puzzle Trading Bot.
Handles SQLite initialization with easy migration path to Postgres.
"""

import aiosqlite
import sqlite3
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database manager."""
    
    def __init__(self, db_path: str = "puzzle_bot.db"):
        """
        Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file (or Postgres connection string)
        """
        self.db_path = db_path
        self.connection: Optional[aiosqlite.Connection] = None
        
    async def connect(self):
        """Establish database connection and initialize schema."""
        logger.info(f"Connecting to database: {self.db_path}")
        
        # Create database file if it doesn't exist
        db_file = Path(self.db_path)
        is_new_db = not db_file.exists()
        
        # Connect to database
        self.connection = await aiosqlite.connect(self.db_path)
        
        # Enable foreign key constraints (SQLite specific)
        await self.connection.execute("PRAGMA foreign_keys = ON")
        
        # Initialize schema if new database
        if is_new_db:
            logger.info("New database detected, initializing schema...")
            await self._initialize_schema()
        
        logger.info("Database connection established")
        
    async def _initialize_schema(self):
        """Load and execute schema.sql to create tables."""
        schema_path = Path(__file__).parent / "schema.sql"
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        schema_sql = schema_path.read_text()
        
        # Execute schema (split by semicolons for multiple statements)
        await self.connection.executescript(schema_sql)
        await self.connection.commit()
        
        logger.info("Database schema initialized successfully")
        
    async def close(self):
        """Close database connection."""
        if self.connection:
            await self.connection.close()
            logger.info("Database connection closed")
            
    async def execute(self, query: str, params: tuple = ()):
        """
        Execute a single query.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Cursor object
        """
        cursor = await self.connection.execute(query, params)
        await self.connection.commit()
        return cursor
        
    async def executemany(self, query: str, params_list: list):
        """
        Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
        """
        await self.connection.executemany(query, params_list)
        await self.connection.commit()
        
    async def fetchone(self, query: str, params: tuple = ()):
        """
        Execute query and fetch one result.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            Single row or None
        """
        cursor = await self.connection.execute(query, params)
        return await cursor.fetchone()
        
    async def fetchall(self, query: str, params: tuple = ()):
        """
        Execute query and fetch all results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of rows
        """
        cursor = await self.connection.execute(query, params)
        return await cursor.fetchall()


# Global database instance
_db_instance: Optional[Database] = None


async def get_database() -> Database:
    """
    Get or create global database instance.
    
    Returns:
        Database instance
    """
    global _db_instance
    
    if _db_instance is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    
    return _db_instance


async def init_database(db_path: str = "puzzle_bot.db"):
    """
    Initialize global database instance.
    
    Args:
        db_path: Path to database file
    """
    global _db_instance
    
    _db_instance = Database(db_path)
    await _db_instance.connect()
    
    return _db_instance


async def close_database():
    """Close global database instance."""
    global _db_instance
    
    if _db_instance:
        await _db_instance.close()
        _db_instance = None
