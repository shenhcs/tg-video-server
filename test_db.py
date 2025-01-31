from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from database.models import Base, Video, Clip

# Create database engine
DATABASE_URL = "sqlite:///./tg_video.db"
engine = create_engine(DATABASE_URL, echo=True)

def main():
    print("=== Testing Database Connection ===")
    
    # Create all tables
    print("\nCreating tables...")
    Base.metadata.create_all(engine)
    
    # Get metadata about created tables
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    print("\nCreated tables:")
    for table_name in metadata.tables:
        print(f"- {table_name}")
        
    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Test querying
    print("\nTesting queries:")
    video_count = session.query(Video).count()
    clip_count = session.query(Clip).count()
    print(f"Number of videos: {video_count}")
    print(f"Number of clips: {clip_count}")
    
    session.close()
    print("\nDatabase test completed successfully!")

if __name__ == "__main__":
    main() 