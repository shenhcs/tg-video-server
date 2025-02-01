import logging
from pathlib import Path
from database.models import K2SStatus, Video
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class VideoManager:
    def __init__(self, db_manager, k2s_uploader, telegram_bot):
        self.db = db_manager
        self.k2s = k2s_uploader
        self.telegram = telegram_bot

    def process_new_videos(self):
        """Main pipeline for processing videos"""
        new_videos = self.db.get_new_videos()
        
        for video_id, filename, path in new_videos:
            try:
                # Upload to K2S
                k2s_link = self.k2s.upload(path)
                
                # Update status
                self.db.update_video_status(
                    video_id, 
                    status='processed',
                    k2s_status='uploaded',
                    k2s_link=k2s_link
                )
                logger.info(f"Processed video: {filename}")
            except Exception as e:
                logger.error(f"Failed to process video {filename}: {e}")
                self.db.update_video_status(
                    video_id,
                    k2s_status='failed'
                )

    def upload_video(self, video_id: int) -> dict:
        """
        Upload a single video to K2S
        Args:
            video_id: ID of the video to upload
        Returns:
            dict with status and upload details
        """
        try:
            # Get video from database
            video = self.db.get_video_by_id(video_id)
            if not video:
                raise ValueError(f"Video with ID {video_id} not found")

            logger.info(f"Starting upload for video: {video.filename}")
            
            # Update status to queued
            self.db.update_video_k2s_status(video_id, K2SStatus.QUEUED)
            
            try:
                # Upload to K2S
                logger.info(f"Uploading to K2S: {video.path}")
                k2s_link = self.k2s.upload_file(video.path)
                logger.info(f"K2S upload successful, got link: {k2s_link}")
                
                # Update video with K2S link and status
                self.db.update_video_k2s_status(video_id, K2SStatus.UPLOADED, k2s_link)
                
                return {
                    "status": "success",
                    "video": {
                        "id": video.id,
                        "filename": video.filename,
                        "path": video.path,
                        "k2s_link": k2s_link,
                        "k2s_status": K2SStatus.UPLOADED.value
                    }
                }
                
            except Exception as upload_error:
                logger.error(f"K2S upload failed for {video.filename}: {str(upload_error)}")
                self.db.update_video_k2s_status(video_id, K2SStatus.FAILED)
                raise upload_error
                
        except Exception as e:
            logger.error(f"Error uploading video {video_id}: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def upload_all_videos(self) -> dict:
        """
        Upload all unuploaded videos to K2S
        Returns:
            dict with upload results
        """
        try:
            uploaded_videos = []
            errors = []
            
            # Get all unuploaded videos from database
            unuploaded_videos = self.db.get_videos_by_status([K2SStatus.PENDING, K2SStatus.FAILED])
            logger.info(f"Found {len(unuploaded_videos)} unuploaded videos")
            
            for video in unuploaded_videos:
                try:
                    result = self.upload_video(video.id)
                    if result["status"] == "success":
                        uploaded_videos.append(result["video"])
                except Exception as e:
                    errors.append({
                        "video_id": video.id,
                        "filename": video.filename,
                        "error": str(e)
                    })
            
            return {
                "status": "success",
                "uploaded_count": len(uploaded_videos),
                "error_count": len(errors),
                "uploaded_videos": uploaded_videos,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error uploading all videos: {str(e)}")
            raise

    def track_video(self, video_path: Path) -> Optional[Video]:
        """
        Add a video file to the database for tracking
        Args:
            video_path: Path to the video file
        Returns:
            Video object if successful, None if already tracked
        """
        try:
            # Generate video ID
            video_id = self._generate_video_id(video_path)
            
            # Check if already tracked
            existing = self.db.get_video_by_id(video_id)
            if existing:
                logger.info(f"Video already tracked: {video_path.name}")
                return None
                
            # Add to database
            video = self.db.add_video(
                id=video_id,
                filename=video_path.name,
                path=str(video_path)
            )
            logger.info(f"Added video to tracking: {video.filename}")
            return video
            
        except Exception as e:
            logger.error(f"Error tracking video {video_path.name}: {str(e)}")
            raise

    def track_all_videos(self, videos_dir: Path) -> dict:
        """
        Add all untracked videos in directory to database
        Args:
            videos_dir: Directory containing videos
        Returns:
            dict with tracking results
        """
        try:
            added_videos = []
            errors = []
            
            # Get all video files from directory
            video_files = list(videos_dir.glob("*.mp4"))
            logger.info(f"Found {len(video_files)} video files")
            
            for video_file in video_files:
                try:
                    video = self.track_video(video_file)
                    if video:
                        added_videos.append({
                            "id": video.id,
                            "filename": video.filename,
                            "path": video.path
                        })
                except Exception as e:
                    errors.append({
                        "filename": video_file.name,
                        "error": str(e)
                    })
            
            return {
                "status": "success",
                "added_count": len(added_videos),
                "error_count": len(errors),
                "added_videos": added_videos,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error tracking all videos: {str(e)}")
            raise

    def get_video_info(self, video_path: Path) -> dict:
        """
        Get information about a video file
        Args:
            video_path: Path to the video file
        Returns:
            dict with video information
        """
        try:
            import subprocess
            import json
            
            # Get basic file info
            video_id = self._generate_video_id(video_path)
            size = video_path.stat().st_size
            size_mb = size / (1024 * 1024)  # Convert to MB
            
            # Get duration using ffprobe
            duration = "00:00:00"
            try:
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
                duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except Exception as e:
                logger.warning(f"Error getting video duration: {str(e)}")
            
            return {
                "id": video_id,
                "title": video_path.stem,
                "filename": video_path.name,
                "path": str(video_path),
                "duration": duration,
                "size": f"{size_mb:.1f}MB"
            }
            
        except Exception as e:
            logger.error(f"Error getting video info: {str(e)}")
            raise

    def _generate_video_id(self, video_path: Path) -> int:
        """
        Generate a stable ID for a video file based on its name and size
        Args:
            video_path: Path to the video file
        Returns:
            Generated video ID
        """
        try:
            import hashlib
            
            file_size = video_path.stat().st_size
            hash_input = f"{video_path.name}_{file_size}"
            
            # Use MD5 for stable hash
            hash_obj = hashlib.md5(hash_input.encode())
            hash_bytes = hash_obj.digest()[:8]
            video_id = int.from_bytes(hash_bytes, byteorder='big')
            
            # Round to nearest thousand
            rounded_id = round(video_id / 1000) * 1000
            
            return rounded_id
            
        except Exception as e:
            logger.error(f"Error generating video ID: {str(e)}")
            raise 