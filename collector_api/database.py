import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from dotenv import load_dotenv

from collector_api.models import Base

# Load environment variables first
load_dotenv()

# Get database URL from environment variable
# Priority: DATABASE_URL (PostgreSQL/Neon) > DATABASE_PATH (SQLite)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Fallback to SQLite if DATABASE_URL is not set
    DATABASE_PATH = os.getenv("DATABASE_PATH", "./data_collector.db")
    DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
    connect_args = {"check_same_thread": False}  # Needed for SQLite
else:
    # PostgreSQL/Neon - no special connect_args needed
    connect_args = {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(db_url: str = None):
    """
    Initialize the database by creating all tables.

    Args:
        db_url: Optional custom database URL (PostgreSQL or SQLite).
                If not provided, uses DATABASE_URL or DATABASE_PATH from environment.
    """
    if db_url:
        # Create a new engine with custom URL
        if db_url.startswith("sqlite"):
            custom_engine = create_engine(
                db_url,
                connect_args={"check_same_thread": False}
            )
        else:
            custom_engine = create_engine(db_url)
        Base.metadata.create_all(bind=custom_engine)
    else:
        Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get a database session.
    Use this in FastAPI endpoints with Depends(get_db).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
