"""
Database initialization script.
Run this to create the database and tables.

Usage (from project root):
    python scripts/init_db.py
    python scripts/init_db.py --db-path /path/to/database.db
"""
import argparse
import logging
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
        "--db-path",
        type=str,
        help="Custom path for the database file (default: ./data_collector.db or DATABASE_PATH env var)"
    )
    args = parser.parse_args()

    if args.db_path:
        logger.info(f"Creating database tables at: {args.db_path}")
        init_db(db_path=args.db_path)
    else:
        logger.info("Creating database tables at default location...")
        init_db()

    logger.info("Database tables created successfully!")


if __name__ == "__main__":
    main()
