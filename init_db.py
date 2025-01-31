from database.db import init_db, engine, Base
from database.models import Video, Clip, VideoStatus, K2SStatus, TelegramStatus
import os

if __name__ == "__main__":
    print("=== Database Initialization ===")
    
    # Get the absolute path of the database file
    db_path = os.path.abspath("tg_video.db")
    print(f"Database will be created at: {db_path}")
    
    # Check if database file exists
    exists = os.path.exists(db_path)
    print(f"Database file exists: {exists}")
    if exists:
        print(f"Database file size: {os.path.getsize(db_path)} bytes")
    
    print("\nInitializing database...")
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Verify tables were created
    tables = Base.metadata.tables
    print("\nCreated tables:")
    for table_name in tables:
        print(f"- {table_name}")
    
    print("\nDatabase initialized successfully!") 