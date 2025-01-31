import sqlite3
import os

def modify_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Create videos table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,                    -- Directory/video name
            video_path TEXT NOT NULL,              -- Full path to video file
            telegram_message_id INTEGER,
            k2s_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(name)
        )
        """)
        
        # Create clips table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            name TEXT NOT NULL,                    -- Clip name without extension
            clip_path TEXT NOT NULL,               -- Full path to clip file
            start_time INTEGER NOT NULL,           -- Start time in seconds
            end_time INTEGER NOT NULL,             -- End time in seconds
            telegram_message_id INTEGER,
            k2s_url TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id),
            UNIQUE(video_id, name)
        )
        """)
        
        # Create indices for faster querying
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_name ON videos(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_video_status ON videos(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clips_video_id ON clips(video_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clips_status ON clips(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_clips_created ON clips(created_at)")
        
        conn.commit()
        print("Database tables and indices created successfully")
        
    except sqlite3.Error as e:
        print(f"Error: {e}")
    finally:
        conn.close()

def get_video_by_name(db_path, name):
    """Get video record by name"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE name = ?", (name,))
            return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def add_or_update_video(db_path, name, video_path):
    """Add or update video record"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO videos (name, video_path)
                VALUES (?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    video_path = excluded.video_path,
                    status = 'pending'
            """, (name, video_path))
            conn.commit()
            return cursor.lastrowid or cursor.execute("SELECT id FROM videos WHERE name = ?", (name,)).fetchone()[0]
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def add_clip(db_path, video_id, name, clip_path, start_time, end_time):
    """Add new clip record"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO clips (video_id, name, clip_path, start_time, end_time)
                VALUES (?, ?, ?, ?, ?)
            """, (video_id, name, clip_path, start_time, end_time))
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return None

def rename_video(db_path, old_name, new_name, new_path):
    """Rename video record"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE videos 
                SET name = ?, video_path = ?
                WHERE name = ?
            """, (new_name, new_path, old_name))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return False

def get_clips_for_video(db_path, video_id):
    """Get all clips for a video"""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, clip_path, start_time, end_time, status
                FROM clips
                WHERE video_id = ?
                ORDER BY created_at DESC
            """, (video_id,))
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []

if __name__ == "__main__":
    DB_PATH = os.path.join('data', 'db.sqlite')
    modify_database(DB_PATH)  # This will create/update the tables 