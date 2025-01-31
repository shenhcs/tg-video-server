from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, FileResponse
from pydantic import BaseModel
import os
import json
import logging
from database.db import Session, init_db
from database.db_manager import DatabaseManager
from database.models import K2SStatus, Video, Clip, TelegramStatus
# Comment out unused imports for now
from services.clip_creator import ClipCreator
from typing import Optional, List
from datetime import datetime
from pathlib import Path
# from services.k2s_uploader import K2SUploader
# from services.telegram_uploader import TelegramUploader
from fastapi.staticfiles import StaticFiles
import subprocess
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="TG Video API")

# Mount storage directory for static file serving
storage_path = Path("storage").resolve()
logger.info(f"Mounting storage directory: {storage_path}")
logger.info(f"Storage directory exists: {storage_path.exists()}")
logger.info(f"Storage directory is directory: {storage_path.is_dir()}")
app.mount("/storage", StaticFiles(directory=str(storage_path)), name="storage")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length", "Content-Type"]
)

# Load config
with open('config.json') as f:
    config = json.load(f)

# Initialize database first
init_db()
logger.info("Database tables initialized")

# Pydantic models
class VideoResponse(BaseModel):
    id: int
    filename: str
    path: str
    k2s_status: str
    k2s_link: Optional[str] = None

    class Config:
        from_attributes = True

class ClipCreate(BaseModel):
    start_time: str
    end_time: str
    output_name: str

class ClipResponse(BaseModel):
    id: int
    filename: str
    path: str
    start_time: int
    end_time: int
    k2s_link: Optional[str] = None

    class Config:
        from_attributes = True

# Storage paths
VIDEOS_DIR = Path(__file__).parent / config['paths']['videos_dir']
CLIPS_DIR = Path(__file__).parent / config['paths']['clips_dir']

logger.info(f"Videos directory: {VIDEOS_DIR}")
logger.info(f"Clips directory: {CLIPS_DIR}")
logger.info(f"Videos directory exists: {VIDEOS_DIR.exists()}")
logger.info(f"Videos directory is directory: {VIDEOS_DIR.is_dir()}")
logger.info(f"Videos directory absolute path: {VIDEOS_DIR.resolve()}")
logger.info(f"Videos directory contents: {list(VIDEOS_DIR.glob('*'))}")

# Initialize services after database is ready
db = Session()
db_manager = DatabaseManager(db)
clip_creator = ClipCreator(db_manager)
# k2s_uploader = K2SUploader()
# telegram_uploader = TelegramUploader()

def scan_videos():
    """Scan storage directory for videos and add them to database if not already present"""
    try:
        print("\n" + "="*50)
        print("Scanning storage for videos...")
        video_files = list(VIDEOS_DIR.glob("*.mp4"))
        print(f"Found {len(video_files)} video files")
        
        for video_file in video_files:
            try:
                video_id = get_video_id(video_file)
                print(f"\nProcessing video: {video_file.name}")
                print(f"Generated ID: {video_id}")
                
                # Check if video exists in database
                video_record = db_manager.get_video_by_id(video_id)
                if not video_record:
                    print(f"Video not in database, adding: {video_file.name}")
                    db_manager.add_video(
                        id=video_id,
                        filename=video_file.name,
                        path=str(video_file)
                    )
                    print(f"Added video to database with ID: {video_id}")
                else:
                    print(f"Video already in database: {video_file.name}")
            except Exception as e:
                print(f"Error processing video {video_file.name}: {str(e)}")
                continue
        
        print("\nVideo scan complete")
        print("="*50)
    except Exception as e:
        print(f"Error scanning videos: {str(e)}")
        print("\nTraceback:")
        import traceback
        print(traceback.format_exc())

# Create directories
try:
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(CLIPS_DIR, exist_ok=True)
    logger.info("Created directories successfully")
    
    # Scan for videos on startup
    scan_videos()
except Exception as e:
    logger.error(f"Error during startup: {str(e)}")
    logger.exception("Startup error traceback:")

# Test hash calculation
test_video = VIDEOS_DIR / "rickroll_test.mp4"
if test_video.exists():
    test_hash = abs(hash(str(test_video)))
    logger.info(f"Test video path: {test_video}")
    logger.info(f"Test video hash: {test_hash}")

def get_video_duration(video_path: Path) -> str:
    try:
        # Check if ffprobe is available
        try:
            subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.warning("ffprobe not found, using default duration")
            return "00:00:00"
            
        # Use ffprobe to get video duration
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'json',
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)
        duration_seconds = float(data['format']['duration'])
        
        # Format duration as HH:MM:SS
        hours = int(duration_seconds // 3600)
        minutes = int((duration_seconds % 3600) // 60)
        seconds = int(duration_seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception as e:
        logger.error(f"Error getting video duration: {str(e)}")
        return "00:00:00"

def get_video_id(video_path: Path) -> int:
    """Generate a stable ID for a video file based on its name and size"""
    try:
        logger.info(f"Generating ID for video: {video_path}")
        logger.info(f"Video path exists: {video_path.exists()}")
        logger.info(f"Video path is file: {video_path.is_file()}")
        
        file_size = os.path.getsize(video_path)
        logger.info(f"Video file size: {file_size} bytes")
        
        # Use a combination of filename and size to generate a stable hash
        hash_input = f"{video_path.name}_{file_size}"
        logger.info(f"Hash input: {hash_input}")
        
        # Use a more stable hash function
        hash_obj = hashlib.md5(hash_input.encode())
        hash_bytes = hash_obj.digest()[:8]
        video_id = int.from_bytes(hash_bytes, byteorder='big')
        
        # Round to nearest thousand to match client expectations
        rounded_id = round(video_id / 1000) * 1000
        logger.info(f"Generated ID: {video_id}")
        logger.info(f"Rounded ID: {rounded_id}")
        
        return rounded_id
    except Exception as e:
        logger.error(f"Error generating video ID: {str(e)}")
        logger.exception("Video ID generation error traceback:")
        return 0

def get_video_info(video_file: Path) -> dict:
    try:
        video_id = get_video_id(video_file)
        duration = get_video_duration(video_file)
        size = os.path.getsize(video_file)
        size_mb = size / (1024 * 1024)  # Convert to MB
        
        return {
            "id": video_id,
            "title": video_file.stem,
            "path": str(video_file),
            "duration": duration,
            "size": f"{size_mb:.1f}MB"
        }
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        return None

@app.get("/videos")
async def get_videos():
    try:
        tracked_videos = []
        untracked_videos = []
        
        # Get all video files from storage
        video_files = list(VIDEOS_DIR.glob("*.mp4"))
        logger.info(f"Found {len(video_files)} video files")
        
        for video_file in video_files:
            video_info = get_video_info(video_file)
            if video_info:
                # Check if video exists in database
                video_id = video_info["id"]
                video_record = db_manager.get_video_by_id(video_id)
                
                if video_record:
                    logger.info(f"Video {video_file.name} is tracked")
                    tracked_videos.append({
                        **video_info,
                        "k2s_status": video_record.k2s_status.value,
                        "k2s_link": video_record.k2s_link
                    })
                else:
                    logger.info(f"Video {video_file.name} is untracked")
                    untracked_videos.append({
                        **video_info,
                        "k2s_status": "untracked",
                        "k2s_link": None
                    })
        
        return {
            "tracked": tracked_videos,
            "untracked": untracked_videos
        }
    except Exception as e:
        logger.error(f"Error getting videos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/clips")
async def get_clips():
    try:
        clips = []
        for clip_path in CLIPS_DIR.glob("*.mp4"):
            clip_name = clip_path.name
            clip_exists = db.query(Clip).filter(Clip.filename == clip_name).first()
            
            clips.append({
                "id": abs(hash(str(clip_path))),
                "title": clip_path.stem,
                "filename": clip_name,
                "status": "tracked" if clip_exists else "untracked",
                "size": f"{os.path.getsize(clip_path) / (1024*1024):.1f}MB",
                "createdAt": datetime.fromtimestamp(os.path.getctime(clip_path)).strftime("%Y-%m-%d")
            })
        
        return clips
    except Exception as e:
        logger.error(f"Error scanning clips: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pending-uploads")
async def get_pending_uploads():
    try:
        pending_clips = db_manager.get_clips_by_status(TelegramStatus.PENDING)
        return {
            "count": len(pending_clips),
            "clips": [clip.filename for clip in pending_clips]
        }
    except Exception as e:
        logger.error(f"Error getting pending uploads: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-clip/{clip_id}")
async def upload_clip(clip_id: int):
    try:
        clip = db.query(ClipResponse).filter(ClipResponse.id == clip_id).first()
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")

        # Get the parent video to access its K2S link
        video = db_manager.get_video_by_id(clip.video_id)
        k2s_link = video.k2s_link if video else "No K2S link available"
        
        # Create caption with K2S link
        caption = f"🎬 {k2s_link}"
        
        # Upload to Telegram
        response = telegram_uploader.send_video(clip.path, caption=caption)
        
        if response and response.json().get('ok'):
            message_id = response.json()['result']['message_id']
            clean_channel_id = telegram_uploader.channel_id.replace('-100', '')
            telegram_link = f"https://t.me/c/{clean_channel_id}/{message_id}"
            
            db_manager.update_clip_telegram_status(clip.id, TelegramStatus.UPLOADED, telegram_link)
            return {"status": "success", "telegram_link": telegram_link}
        else:
            db_manager.update_clip_telegram_status(clip.id, TelegramStatus.FAILED)
            raise HTTPException(status_code=500, detail="Failed to upload to Telegram")

    except Exception as e:
        logger.error(f"Error uploading clip: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    try:
        # Get videos from database
        videos_query = db.query(Video)
        total_videos = videos_query.count()
        print("\n=== Getting Stats ===")
        print(f"Total videos in database: {total_videos}")
        
        # Get clips from database
        clips_query = db.query(Clip)
        total_clips = clips_query.count()
        
        # Get videos with clips
        videos_with_clips = db.query(Video).join(Clip).distinct().count()
        videos_without_clips = total_videos - videos_with_clips
        
        # Get clips by status
        uploaded_clips = clips_query.filter(Clip.telegram_status == TelegramStatus.UPLOADED).count()
        unuploaded_clips = total_clips - uploaded_clips
        
        # Get untracked videos (files in directory but not in db)
        video_files = list(VIDEOS_DIR.glob("*.mp4"))
        print(f"\nFound video files in directory:")
        for f in video_files:
            print(f"  - {f.name}")
        
        tracked_filenames = [v.filename for v in db.query(Video).all()]
        print(f"\nTracked filenames in database:")
        for f in tracked_filenames:
            print(f"  - {f}")
        
        untracked_videos = [f for f in video_files if f.name not in tracked_filenames]
        print(f"\nUntracked videos:")
        for f in untracked_videos:
            print(f"  - {f.name}")
        
        untracked_count = len(untracked_videos)
        print(f"\nUntracked count: {untracked_count}")
        
        stats = {
            "untrackedVideos": untracked_count,
            "unuploadedVideos": videos_query.filter(Video.k2s_status != K2SStatus.UPLOADED).count(),
            "uploadedVideosWithoutClips": videos_without_clips,
            "uploadedVideosWithClips": videos_with_clips,
            "unuploadedClips": unuploaded_clips,
            "uploadedClips": uploaded_clips,
        }
        print(f"\nReturning stats: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/refresh")
async def refresh_files():
    try:
        videos = []
        for video_file in VIDEOS_DIR.glob("*.mp4"):
            video_info = get_video_info(video_file)
            if video_info:
                videos.append(video_info)
        
        clips = list(CLIPS_DIR.glob("*.mp4"))
        
        return {
            "status": "success",
            "message": f"Found {len(videos)} videos and {len(clips)} clips",
            "videos": len(videos),
            "clips": len(clips)
        }
    except Exception as e:
        logger.error(f"Error refreshing files: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/videos/{video_id}/stream")
async def stream_video(video_id: int):
    try:
        logger.info(f"=== Starting streaming request for video ID: {video_id} ===")
        # Find the video file with matching ID
        video_files = list(VIDEOS_DIR.glob("*.mp4"))
        logger.info(f"Videos directory: {VIDEOS_DIR}")
        logger.info(f"Videos directory exists: {VIDEOS_DIR.exists()}")
        logger.info(f"Found video files: {[str(f) for f in video_files]}")
        
        if not video_files:
            logger.error("No video files found in directory")
            raise HTTPException(status_code=404, detail="No videos available")
        
        # First try to find by exact filename match
        for video_file in video_files:
            try:
                # Generate stable ID for the video
                current_id = get_video_id(video_file)
                logger.info(f"Checking file: {video_file.name}")
                logger.info(f"Generated ID: {current_id}")
                logger.info(f"Target ID: {video_id}")
                logger.info(f"IDs match: {current_id == video_id}")
                
                if current_id == video_id:
                    logger.info(f"Found matching video: {video_file}")
                    abs_path = str(video_file.resolve())
                    logger.info(f"Absolute path: {abs_path}")
                    
                    # Verify file exists and is readable
                    exists = os.path.exists(abs_path)
                    readable = os.access(abs_path, os.R_OK)
                    logger.info(f"File exists: {exists}, File readable: {readable}")
                    
                    if not exists:
                        logger.error(f"File does not exist: {abs_path}")
                        continue
                        
                    if not readable:
                        logger.error(f"File is not readable: {abs_path}")
                        continue
                    
                    file_size = os.path.getsize(abs_path)
                    logger.info(f"File size: {file_size} bytes")
                    
                    try:
                        headers = {
                            'Accept-Ranges': 'bytes',
                            'Content-Type': 'video/mp4',
                            'Cache-Control': 'no-cache',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'GET, OPTIONS',
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Expose-Headers': 'Content-Range, Accept-Ranges, Content-Length, Content-Type'
                        }
                        logger.info(f"Preparing to stream with headers: {headers}")
                        
                        return FileResponse(
                            path=abs_path,
                            media_type="video/mp4",
                            headers=headers,
                            filename=video_file.name
                        )
                        
                    except IOError as e:
                        logger.error(f"Failed to open video file: {str(e)}")
                        logger.exception("IO Error traceback:")
                        raise HTTPException(status_code=500, detail=f"Failed to open video file: {str(e)}")
            except Exception as e:
                logger.error(f"Error processing video file {video_file.name}: {str(e)}")
                logger.exception("Processing error traceback:")
                raise HTTPException(status_code=500, detail=f"Error processing video file: {str(e)}")
                
        logger.warning(f"No video found with ID: {video_id}")
        raise HTTPException(status_code=404, detail="Video not found")
    except Exception as e:
        logger.error(f"Unhandled error in stream_video: {str(e)}")
        logger.exception("Unhandled error traceback:")
        raise HTTPException(status_code=500, detail=str(e))

# Add test code after directory creation
test_video = VIDEOS_DIR / "rickroll_test.mp4"
if test_video.exists():
    test_id = get_video_id(test_video)
    logger.info(f"Test video path: {test_video}")
    logger.info(f"Test video ID: {test_id}")

@app.post("/videos/{video_id}/create-clip")
async def create_clip(video_id: int, clip_data: ClipCreate):
    try:
        print("\n" + "="*50)
        print(f"Starting clip creation for video {video_id}")
        print(f"Request data: start_time={clip_data.start_time}, end_time={clip_data.end_time}, output_name={clip_data.output_name}")
        print("="*50)
        
        # First check if video exists
        video_files = list(VIDEOS_DIR.glob("*.mp4"))
        print(f"\nFound video files:")
        for f in video_files:
            print(f"  - {f}")
        
        video_file = None
        for file in video_files:
            current_id = get_video_id(file)
            print(f"\nChecking file: {file.name}")
            print(f"Generated ID: {current_id}")
            print(f"Target ID: {video_id}")
            print(f"Match: {current_id == video_id}")
            if current_id == video_id:
                video_file = file
                break
        
        if not video_file:
            print(f"\nERROR: Video file not found for ID {video_id}")
            raise HTTPException(status_code=404, detail=f"Video with ID {video_id} not found")
        
        print(f"\nFound video file: {video_file}")
        
        # Check if video exists in database, if not add it
        video_record = db_manager.get_video_by_id(video_id)
        print(f"\nDatabase lookup result:")
        print(f"Video record: {video_record}")
        
        if not video_record:
            print(f"\nAdding video to database: {video_file.name}")
            video_record = db_manager.add_video(
                id=video_id,
                filename=video_file.name,
                path=str(video_file),
                k2s_link=None
            )
            print(f"Added video record: {video_record}")
        
        print(f"\nCreating clip:")
        print(f"  video_id: {video_id}")
        print(f"  start_time: {clip_data.start_time}")
        print(f"  end_time: {clip_data.end_time}")
        
        try:
            clip = clip_creator.create_clip(
                video_id=video_id,
                start_time=clip_data.start_time,
                end_time=clip_data.end_time,
                k2s_link=None
            )
            print(f"\nSuccessfully created clip: {clip}")
        except Exception as clip_error:
            print(f"\nERROR during clip creation:")
            print(f"Error type: {type(clip_error)}")
            print(f"Error message: {str(clip_error)}")
            print("\nTraceback:")
            import traceback
            print(traceback.format_exc())
            raise
        
        return {
            "status": "success",
            "clip": {
                "id": clip.id,
                "filename": clip.filename,
                "path": clip.path,
                "start_time": clip.start_time,
                "end_time": clip.end_time,
                "k2s_link": clip.k2s_link
            }
        }
    except ValueError as e:
        print(f"\nERROR - Invalid input:")
        print(str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"\nERROR - Unhandled exception:")
        print(f"Error type: {type(e)}")
        print(f"Error message: {str(e)}")
        print("\nFull traceback:")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/videos/track-all")
async def track_all_videos():
    try:
        print("\n=== Adding all untracked videos to database ===")
        added_videos = []
        
        # Get all video files from storage
        video_files = list(VIDEOS_DIR.glob("*.mp4"))
        print(f"Found {len(video_files)} video files")
        
        for video_file in video_files:
            try:
                video_id = get_video_id(video_file)
                print(f"\nChecking video: {video_file.name}")
                
                # Check if already tracked
                existing = db_manager.get_video_by_id(video_id)
                if not existing:
                    print(f"Adding video to database: {video_file.name}")
                    video = db_manager.add_video(
                        id=video_id,
                        filename=video_file.name,
                        path=str(video_file)
                    )
                    added_videos.append({
                        "id": video.id,
                        "filename": video.filename,
                        "path": video.path
                    })
                else:
                    print(f"Video already in database: {video_file.name}")
            except Exception as e:
                print(f"Error processing video {video_file.name}: {str(e)}")
                continue
        
        return {
            "status": "success",
            "added_count": len(added_videos),
            "added_videos": added_videos
        }
        
    except Exception as e:
        logger.error(f"Error adding all videos to database: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Cleanup on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,           # Enable auto-reload
        reload_dirs=["./"],    # Watch the current directory
        workers=1              # Use single worker for development
    ) 