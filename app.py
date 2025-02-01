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
from services.video_manager import VideoManager
from services.clip_manager import ClipManager
from services.k2s_uploader import K2SUploader
from typing import Optional, List
from datetime import datetime
from pathlib import Path
from fastapi.staticfiles import StaticFiles
import subprocess

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

# Load config
with open('config.json') as f:
    config = json.load(f)

# Storage paths
VIDEOS_DIR = Path(__file__).parent / config['paths']['videos_dir']
CLIPS_DIR = Path(__file__).parent / config['paths']['clips_dir']

# Mount storage directory for static file serving
storage_path = Path("storage").resolve()
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

# Initialize database first
init_db()
logger.info("Database tables initialized")

# Initialize services
db = Session()
db_manager = DatabaseManager(db)
k2s_uploader = K2SUploader()
video_manager = VideoManager(db_manager, k2s_uploader, None)  # No telegram bot for now
clip_manager = ClipManager(db_manager, k2s_uploader, None)  # No telegram bot for now

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

def scan_videos():
    """Scan storage directory for videos and add them to database if not already present"""
    try:
        print("\n" + "="*50)
        print("Scanning storage for videos...")
        
        result = video_manager.track_all_videos(VIDEOS_DIR)
        print(f"\nScan complete:")
        print(f"Added {result['added_count']} videos")
        print(f"Encountered {result['error_count']} errors")
        print("="*50)
        
    except Exception as e:
        print(f"Error scanning videos: {str(e)}")
        print("\nTraceback:")
        import traceback
        print(traceback.format_exc())

# Create directories and scan videos on startup
try:
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    os.makedirs(CLIPS_DIR, exist_ok=True)
    logger.info("Created directories successfully")
    scan_videos()
except Exception as e:
    logger.error(f"Error during startup: {str(e)}")
    logger.exception("Startup error traceback:")

@app.get("/videos")
async def get_videos():
    try:
        uploaded_videos = []
        unuploaded_videos = []
        
        # Get all video files from storage
        video_files = list(VIDEOS_DIR.glob("*.mp4"))
        logger.info(f"Found {len(video_files)} video files")
        
        for video_file in video_files:
            video_info = video_manager.get_video_info(video_file)
            if video_info:
                # Check if video exists in database
                video_id = video_info["id"]
                video_record = db_manager.get_video_by_id(video_id)
                
                if video_record:
                    logger.info(f"Video {video_file.name} is tracked")
                    video_data = {
                        **video_info,
                        "k2s_status": video_record.k2s_status.value,
                        "k2s_link": video_record.k2s_link
                    }
                    
                    # Separate based on k2s_status
                    if video_record.k2s_status == K2SStatus.UPLOADED:
                        uploaded_videos.append(video_data)
                    else:
                        unuploaded_videos.append(video_data)
                else:
                    logger.info(f"Video {video_file.name} is untracked")
                    unuploaded_videos.append({
                        **video_info,
                        "k2s_status": "untracked",
                        "k2s_link": None
                    })
        
        return {
            "uploaded": uploaded_videos,
            "unuploaded": unuploaded_videos
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

@app.post("/videos/{video_id}/create-clip")
async def create_clip(video_id: int, clip_data: ClipCreate):
    try:
        print("\n" + "="*50)
        print(f"Starting clip creation for video {video_id}")
        print(f"Request data: start_time={clip_data.start_time}, end_time={clip_data.end_time}, output_name={clip_data.output_name}")
        
        clip = clip_manager.create_clip(
            video_id=video_id,
            start_time=clip_data.start_time,
            end_time=clip_data.end_time,
            output_name=clip_data.output_name
        )
        
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
        result = video_manager.track_all_videos(VIDEOS_DIR)
        return result
    except Exception as e:
        logger.error(f"Error adding all videos to database: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/videos/upload-all")
async def upload_all_videos():
    try:
        result = video_manager.upload_all_videos()
        return result
    except Exception as e:
        logger.error(f"Error uploading all videos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/videos/{video_id}/upload")
async def upload_video(video_id: int):
    try:
        result = video_manager.upload_video(video_id)
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/videos/{video_id}/stream")
async def stream_video(video_id: int):
    try:
        logger.info(f"=== Starting streaming request for video ID: {video_id} ===")
        # Find the video file with matching ID
        video_files = list(VIDEOS_DIR.glob("*.mp4"))
        logger.info(f"Found video files: {[str(f) for f in video_files]}")
        
        if not video_files:
            logger.error("No video files found in directory")
            raise HTTPException(status_code=404, detail="No videos available")
        
        # First try to find by exact filename match
        for video_file in video_files:
            try:
                # Generate stable ID for the video
                current_id = video_manager._generate_video_id(video_file)
                logger.info(f"Checking file: {video_file.name}")
                logger.info(f"Generated ID: {current_id}")
                logger.info(f"Target ID: {video_id}")
                
                if current_id == video_id:
                    logger.info(f"Found matching video: {video_file}")
                    abs_path = str(video_file.resolve())
                    
                    # Verify file exists and is readable
                    exists = os.path.exists(abs_path)
                    readable = os.access(abs_path, os.R_OK)
                    logger.info(f"File exists: {exists}, File readable: {readable}")
                    
                    if not exists or not readable:
                        continue
                    
                        headers = {
                            'Accept-Ranges': 'bytes',
                            'Content-Type': 'video/mp4',
                            'Cache-Control': 'no-cache',
                            'Access-Control-Allow-Origin': '*',
                            'Access-Control-Allow-Methods': 'GET, OPTIONS',
                            'Access-Control-Allow-Headers': '*',
                            'Access-Control-Expose-Headers': 'Content-Range, Accept-Ranges, Content-Length, Content-Type'
                        }
                        
                        return FileResponse(
                            path=abs_path,
                            media_type="video/mp4",
                            headers=headers,
                            filename=video_file.name
                        )
                        
            except Exception as e:
                logger.error(f"Error processing video file {video_file.name}: {str(e)}")
                continue
                
        logger.warning(f"No video found with ID: {video_id}")
        raise HTTPException(status_code=404, detail="Video not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming video: {str(e)}")
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
        tracked_filenames = [v.filename for v in db.query(Video).all()]
        untracked_videos = [f for f in video_files if f.name not in tracked_filenames]
        untracked_count = len(untracked_videos)
        
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
            video_info = video_manager.get_video_info(video_file)
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
        reload=True,
        reload_dirs=["./"],
        workers=1
    ) 