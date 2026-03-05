"""
Database initialization script.
Run this to create the database and tables.

Usage (from project root):
    python scripts/init_db.py
    python scripts/init_db.py --db-url postgresql://user:pass@host/dbname
"""
import argparse
import logging
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path so we can import collector_api
sys.path.insert(0, str(Path(__file__).parent.parent))

from collector_api.database import init_db
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Initialize the database")
    parser.add_argument(
        "--db-url",
        type=str,
        help="Custom database URL (PostgreSQL or SQLite). If not provided, uses DATABASE_URL or DATABASE_PATH from .env"
    )
    args = parser.parse_args()

    if args.db_url:
        logger.info(f"Creating database tables at: {args.db_url}")
        init_db(db_url=args.db_url)
    else:
        # Check which database is being used
        db_url = os.getenv("DATABASE_URL")
        if db_url:
            logger.info(f"Creating database tables in PostgreSQL/Neon...")
            logger.info(f"Database: {db_url.split('@')[1] if '@' in db_url else 'configured database'}")
        else:
            db_path = os.getenv("DATABASE_PATH", "./data_collector.db")
            logger.info(f"Creating database tables in SQLite at: {db_path}")
        init_db()

    logger.info("Database tables created successfully!")


if __name__ == "__main__":
    main()
