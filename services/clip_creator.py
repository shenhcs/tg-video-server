import os
from pathlib import Path
import json
from database.models import TelegramStatus
import logging
import time
import subprocess

logger = logging.getLogger(__name__)

class ClipCreator:
    def __init__(self, db_manager):
        # Load config
        with open('config.json') as f:
            self.config = json.load(f)
        self.db_manager = db_manager

    def _convert_time_to_seconds(self, time_str: str) -> float:
        """Convert HH:MM:SS[.mmm] format to seconds"""
        try:
            # First check if the string matches the format
            if not isinstance(time_str, str):
                raise ValueError(f"Time must be a string, got {type(time_str)}")
            
            # Split into time and milliseconds parts
            time_parts = time_str.split('.')
            time_component = time_parts[0]
            ms_component = time_parts[1] if len(time_parts) > 1 else '0'
            
            # Check if format matches HH:MM:SS
            if len(time_component.split(':')) != 3:
                raise ValueError("Time must be in HH:MM:SS[.mmm] format")
            
            hours, minutes, seconds = time_component.split(':')
            
            # Validate each component
            try:
                hours = int(hours)
                minutes = int(minutes)
                seconds = int(seconds)
                ms = int(ms_component.ljust(3, '0')[:3])  # Pad with zeros if needed and take first 3 digits
            except ValueError:
                raise ValueError("Hours, minutes, seconds, and milliseconds must be numbers")
                
            # Validate ranges
            if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59 and 0 <= ms <= 999):
                raise ValueError("Invalid time values. Hours: 0-23, Minutes: 0-59, Seconds: 0-59, Milliseconds: 0-999")
            
            total_seconds = hours * 3600 + minutes * 60 + seconds + (ms / 1000)
            logger.info(f"Converted time {time_str} to {total_seconds} seconds")
            return total_seconds
            
        except ValueError as e:
            logger.error(f"Time format error for '{time_str}': {str(e)}")
            raise ValueError(f"Invalid time format '{time_str}'. Use HH:MM:SS[.mmm] (e.g., 00:01:30.500 for 1 minute 30.5 seconds)")
        except Exception as e:
            logger.error(f"Unexpected error converting time '{time_str}': {str(e)}")
            raise

    def create_clip(self, video_id: int, start_time: str, end_time: str, k2s_link: str = None):
        """
        Create a clip from a video and store it in the database
        Args:
            video_id: ID of the parent video
            start_time: Start time in HH:MM:SS format
            end_time: End time in HH:MM:SS format
            k2s_link: Keep2Share link of the parent video (optional)
        Returns:
            Created clip object
        """
        try:
            print("\n" + "-"*50)
            print("Starting clip creation process")
            print(f"Parameters:")
            print(f"  video_id: {video_id}")
            print(f"  start_time: {start_time}")
            print(f"  end_time: {end_time}")
            print(f"  k2s_link: {k2s_link}")
            print("-"*50)
            
            # Convert times to seconds
            print("\nConverting times to seconds...")
            start_seconds = self._convert_time_to_seconds(start_time)
            end_seconds = self._convert_time_to_seconds(end_time)
            print(f"Converted start time: {start_seconds}s")
            print(f"Converted end time: {end_seconds}s")

            # Validate time range
            if start_seconds >= end_seconds:
                print("\nERROR: Invalid time range - end time must be after start time")
                raise ValueError("End time must be after start time")

            # Get parent video
            print("\nLooking up video in database...")
            video = self.db_manager.get_video_by_id(video_id)
            if not video:
                print(f"ERROR: Video {video_id} not found in database")
                raise ValueError(f"Video with ID {video_id} not found")
            print(f"Found video: {video.filename}")

            # Create output filename
            print("\nGenerating output filename...")
            base_name = os.path.splitext(video.filename)[0]
            output_name = f"{base_name}_clip"
            
            # Get clips directory and ensure it exists
            clips_dir = os.path.join(os.getcwd(), self.config['paths']['clips_dir'])
            os.makedirs(clips_dir, exist_ok=True)
            print(f"Using clips directory: {clips_dir}")
            
            # Find unique filename
            counter = 1
            while os.path.exists(os.path.join(clips_dir, f"{output_name}.mp4")):
                output_name = f"{base_name}_clip_{counter}"
                counter += 1
            
            output_path = os.path.join(clips_dir, f"{output_name}.mp4")
            print(f"Output path: {output_path}")
            
            # Verify source video exists and is readable
            print("\nVerifying source video...")
            if not os.path.exists(video.path):
                print(f"ERROR: Source video file not found: {video.path}")
                raise ValueError(f"Source video file not found: {video.path}")
            if not os.access(video.path, os.R_OK):
                print(f"ERROR: Source video file not readable: {video.path}")
                raise ValueError(f"Source video file not readable: {video.path}")
            print("Source video verified")
            
            print("\nPreparing ffmpeg command...")
            # Create clip using ffmpeg
            duration = end_seconds - start_seconds
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(start_seconds),
                '-i', video.path,
                '-t', str(duration),
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-strict', 'experimental',
                output_path
            ]
            print(f"Command: {' '.join(cmd)}")
            
            # Run ffmpeg command
            print("\nRunning ffmpeg...")
            process = subprocess.run(cmd, capture_output=True, text=True)
            if process.returncode != 0:
                print(f"ERROR: FFmpeg failed with output:")
                print(process.stderr)
                raise Exception(f"FFmpeg error: {process.stderr}")
            print("FFmpeg completed successfully")
            
            # Add clip to database
            print("\nAdding clip to database...")
            try:
                clip = self.db_manager.add_clip(
                    video_id=video_id,
                    filename=f"{output_name}.mp4",
                    path=output_path,
                    start_time=start_seconds,
                    end_time=end_seconds,
                    k2s_link=k2s_link
                )
                print("Successfully added clip to database")
                return clip
            except Exception as db_error:
                print(f"ERROR adding clip to database: {str(db_error)}")
                raise
            
        except ValueError as e:
            print(f"\nERROR - Invalid input: {str(e)}")
            raise
        except Exception as e:
            print(f"\nERROR - Clip creation failed: {str(e)}")
            print("\nFull traceback:")
            import traceback
            print(traceback.format_exc())
            raise
