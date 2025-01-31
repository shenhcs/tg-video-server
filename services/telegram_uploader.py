# upload clip and link to telegram

import os
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

class TelegramUploader:
    def __init__(self):
        self.bot_token = os.getenv('TG_BOT_TOKEN')
        self.channel_id = os.getenv('TG_CHANNEL_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/"
        print(f"Bot Token: {self.bot_token}")
        print(f"Channel ID: {self.channel_id}") 

    def send_text(self, text):
        """Send plain text message"""
        url = self.base_url + "sendMessage"
        payload = {
            "chat_id": self.channel_id,
            "text": text,
            "parse_mode": "HTML"  # Supports HTML formatting
        }
        return requests.post(url, json=payload)

    def send_photo(self, photo_path, caption=""):
        """Send photo with optional caption"""
        url = self.base_url + "sendPhoto"
        files = {
            "photo": open(photo_path, "rb")
        }
        data = {
            "chat_id": self.channel_id,
            "caption": caption,
            "parse_mode": "HTML"  # Supports HTML formatting in caption
        }
        return requests.post(url, files=files, data=data)

    def send_video(self, video_path, caption="", thumb=None):
        """Send video with optional caption and thumbnail"""
        # Check file size first (50MB limit)
        MAX_SIZE = 50 * 1024 * 1024  # 50MB in bytes
        
        try:
            file_size = os.path.getsize(video_path)
            if file_size > MAX_SIZE:
                print(f"Error: Video file is too large ({file_size/1024/1024:.2f}MB). Maximum size is 50MB")
                return None
            
            url = self.base_url + "sendVideo"
            
            with open(video_path, "rb") as video_file:
                files = {
                    "video": video_file
                }
                if thumb:
                    with open(thumb, "rb") as thumb_file:
                        files["thumb"] = thumb_file
                    
                data = {
                    "chat_id": self.channel_id,
                    "caption": caption,
                    "parse_mode": "HTML",
                    "supports_streaming": True
                }
                
                try:
                    return requests.post(url, files=files, data=data, timeout=60)
                except requests.exceptions.RequestException as e:
                    print(f"Error uploading video: {e}")
                    return None
                
        except FileNotFoundError:
            print(f"Error: Video file not found: {video_path}")
            return None
        except Exception as e:
            print(f"Error: {str(e)}")
            return None

# Usage example
def main():
    uploader = TelegramUploader()
    
    # Simple text test
    response = uploader.send_text("Test message")
    print(f"Text Response: {response.json()}")

    # Test photo
    response = uploader.send_photo("test_photo.jpeg")
    print(f"Photo Response: {response.json()}")

    # Test video
    response = uploader.send_video("Rick Astley Free Download Borrow and Streaming  Internet Archive.mp4")
    if response:  # Check if response is not None
        print(f"Video Response: {response.json()}")
    # Video was too large (110.96MB) - need a smaller video file under 50MB

if __name__ == "__main__":
    main()

    