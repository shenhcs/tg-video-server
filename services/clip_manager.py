import logging
from pathlib import Path
from database.models import TelegramStatus, Clip

logger = logging.getLogger(__name__)

class ClipManager:
    def __init__(self, db_manager, k2s_uploader, telegram_bot):
        self.db = db_manager
        self.k2s = k2s_uploader
        self.telegram = telegram_bot

    def create_clip(self, video_id: int, start_time: str, end_time: str, output_name: str) -> Clip:
        """
        Create a new clip from a video
        Args:
            video_id: ID of the source video
            start_time: Start time in HH:MM:SS format
            end_time: End time in HH:MM:SS format
            output_name: Name for the output clip file
        Returns:
            Created Clip object
        """
        try:
            logger.info(f"Creating clip from video {video_id}: {start_time} to {end_time}")
            
            # Get the source video
            video = self.db.get_video_by_id(video_id)
            if not video:
                raise ValueError(f"Video with ID {video_id} not found")

            # Create the clip using ffmpeg
            output_path = Path("storage/clips") / f"{output_name}.mp4"
            self._create_clip_file(video.path, output_path, start_time, end_time)
            
            # Add clip to database
            clip = self.db.add_clip(
                video_id=video_id,
                filename=output_path.name,
                path=str(output_path),
                start_time=start_time,
                end_time=end_time
            )
            
            logger.info(f"Successfully created clip: {clip.filename}")
            return clip
            
        except Exception as e:
            logger.error(f"Error creating clip: {str(e)}")
            raise

    def _create_clip_file(self, input_path: str, output_path: Path, start_time: str, end_time: str):
        """
        Create a clip file using ffmpeg
        Args:
            input_path: Path to input video
            output_path: Path for output clip
            start_time: Start time in HH:MM:SS format
            end_time: End time in HH:MM:SS format
        """
        try:
            import subprocess
            
            cmd = [
                'ffmpeg',
                '-i', input_path,
                '-ss', start_time,
                '-to', end_time,
                '-c', 'copy',
                str(output_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg error: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error creating clip file: {str(e)}")
            raise

    def upload_clip(self, clip_id: int) -> dict:
        """
        Upload a clip to Telegram
        Args:
            clip_id: ID of the clip to upload
        Returns:
            dict with status and upload details
        """
        try:
            # Get clip from database
            clip = self.db.get_clip_by_id(clip_id)
            if not clip:
                raise ValueError(f"Clip with ID {clip_id} not found")

            logger.info(f"Uploading clip: {clip.filename}")
            
            # Update status to queued
            self.db.update_clip_telegram_status(clip_id, TelegramStatus.QUEUED)
            
            # Get parent video's K2S link for caption
            video = self.db.get_video_by_id(clip.video_id)
            k2s_link = video.k2s_link if video else "No K2S link available"
            
            # Create caption with K2S link
            caption = f"🎬 {k2s_link}"
            
            # Upload to Telegram
            if self.telegram:
                response = self.telegram.send_video(clip.path, caption=caption)
                
                if response and response.json().get('ok'):
                    message_id = response.json()['result']['message_id']
                    clean_channel_id = self.telegram.channel_id.replace('-100', '')
                    telegram_link = f"https://t.me/c/{clean_channel_id}/{message_id}"
                    
                    self.db.update_clip_telegram_status(clip_id, TelegramStatus.UPLOADED, telegram_link)
                    return {
                        "status": "success",
                        "telegram_link": telegram_link
                    }
                else:
                    raise RuntimeError("Failed to upload to Telegram")
            else:
                logger.warning("No Telegram bot configured, skipping upload")
                return {
                    "status": "skipped",
                    "message": "No Telegram bot configured"
                }
                
        except Exception as e:
            logger.error(f"Error uploading clip {clip_id}: {str(e)}")
            self.db.update_clip_telegram_status(clip_id, TelegramStatus.FAILED)
            raise

    def upload_all_clips(self) -> dict:
        """
        Upload all unuploaded clips to Telegram
        Returns:
            dict with upload results
        """
        try:
            uploaded_clips = []
            errors = []
            
            # Get all unuploaded clips
            unuploaded_clips = self.db.get_clips_by_status(TelegramStatus.PENDING)
            logger.info(f"Found {len(unuploaded_clips)} unuploaded clips")
            
            for clip in unuploaded_clips:
                try:
                    result = self.upload_clip(clip.id)
                    if result["status"] == "success":
                        uploaded_clips.append({
                            "id": clip.id,
                            "filename": clip.filename,
                            "telegram_link": result["telegram_link"]
                        })
                except Exception as e:
                    errors.append({
                        "clip_id": clip.id,
                        "filename": clip.filename,
                        "error": str(e)
                    })
            
            return {
                "status": "success",
                "uploaded_count": len(uploaded_clips),
                "error_count": len(errors),
                "uploaded_clips": uploaded_clips,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Error uploading all clips: {str(e)}")
            raise 