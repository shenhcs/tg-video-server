from sqlalchemy.orm import Session
from .models import Video, Clip, VideoStatus, K2SStatus, TelegramStatus
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, session: Session):
        self.session = session

    def add_video(self, filename: str, path: str, id: int = None) -> Video:
        """Add a new video to the database"""
        try:
            video = Video(
                id=id,
                filename=filename,
                path=str(path),
                status=VideoStatus.NEW,
                k2s_status=K2SStatus.PENDING
            )
            self.session.add(video)
            self.session.commit()
            logger.info(f"Added video {filename} to database")
            return video
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error adding video {filename}: {str(e)}")
            raise

    def get_video_by_id(self, video_id: int) -> Video:
        """Get video by ID"""
        return self.session.query(Video).filter(Video.id == video_id).first()

    def get_videos_by_status(self, k2s_status: K2SStatus) -> list[Video]:
        """Get videos by K2S status"""
        return self.session.query(Video).filter(Video.k2s_status == k2s_status).all()

    def update_video_k2s_status(self, video_id: int, status: K2SStatus, k2s_link: str = None):
        """Update video K2S status"""
        try:
            video = self.get_video_by_id(video_id)
            if video:
                video.k2s_status = status
                if k2s_link:
                    video.k2s_link = k2s_link
                self.session.commit()
                logger.info(f"Updated video {video.filename} K2S status to {status}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating video {video_id} K2S status: {str(e)}")
            raise

    def add_clip(self, video_id: int, filename: str, path: str, start_time: int, end_time: int, k2s_link: str = None) -> Clip:
        """Add a new clip to the database"""
        try:
            print(f"\n=== Adding clip to database ===")
            print(f"Parameters: video_id={video_id}, filename={filename}, path={path}")
            print(f"start_time={start_time}, end_time={end_time}, k2s_link={k2s_link}")
            
            # Get parent video
            video = self.get_video_by_id(video_id)
            print(f"Found parent video: {video}")
            if not video:
                print(f"ERROR: Video with ID {video_id} not found")
                raise ValueError(f"Video with ID {video_id} not found")
            
            clip = Clip(
                video_id=video_id,
                filename=filename,
                path=str(path),
                start_time=start_time,
                end_time=end_time,
                k2s_link=k2s_link,  # This can be None
                telegram_status=TelegramStatus.PENDING
            )
            print(f"Created clip object: {clip}")
            
            self.session.add(clip)
            self.session.commit()
            print(f"Successfully added clip to database")
            return clip
        except Exception as e:
            self.session.rollback()
            print(f"ERROR adding clip to database: {str(e)}")
            print("Full traceback:")
            import traceback
            print(traceback.format_exc())
            raise

    def get_clip_by_id(self, clip_id: int) -> Clip:
        """Get clip by ID"""
        return self.session.query(Clip).filter(Clip.id == clip_id).first()

    def get_clips_by_status(self, telegram_status: TelegramStatus) -> list[Clip]:
        """Get clips by Telegram status"""
        return self.session.query(Clip).filter(Clip.telegram_status == telegram_status).all()

    def update_clip_telegram_status(self, clip_id: int, status: TelegramStatus, telegram_link: str = None):
        """Update clip Telegram status"""
        try:
            clip = self.get_clip_by_id(clip_id)
            if clip:
                clip.telegram_status = status
                if telegram_link:
                    clip.telegram_link = telegram_link
                self.session.commit()
                logger.info(f"Updated clip {clip.filename} Telegram status to {status}")
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating clip {clip_id} Telegram status: {str(e)}")
            raise 

    def get_video_by_filename(self, filename: str) -> Video:
        """Get video by filename"""
        return self.session.query(Video).filter(Video.filename == filename).first() 