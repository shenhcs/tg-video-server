import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Database URL - using SQLite
DATABASE_URL = "sqlite:///./tg_video.db"

# Create engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Create session factory
Session = sessionmaker(bind=engine)

# Create base class for models
Base = declarative_base()

def get_db():
    """Get database session"""
    db = Session()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize database by creating all tables"""
    Base.metadata.create_all(engine) 