import logging
from pathlib import Path
from database.models import K2SStatus

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