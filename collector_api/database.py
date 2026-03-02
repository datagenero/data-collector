import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from dotenv import load_dotenv

from collector_api.models import Base

# Load environment variables first
load_dotenv()

# Get database path from environment variable or use default
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data_collector.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Needed for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(db_path: str = None):
    """
    Initialize the database by creating all tables.

    Args:
        db_path: Optional custom path for the database file.
                 If not provided, uses DATABASE_PATH from environment or default.
    """
    if db_path:
        # Create a new engine with custom path
        custom_engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False}
        )
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
