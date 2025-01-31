from main import TelegramUploader
import os

def test_uploader():
    uploader = TelegramUploader()
    
    print("\n=== Testing Text Upload ===")
    text_response = uploader.send_text("🔄 Test Message\nThis is a <b>bold</b> test with <i>italic</i> text")
    print(f"Text Status: {text_response.status_code if text_response else 'Failed'}")
    
    print("\n=== Testing Photo Upload ===")
    # Test with small photo file
    if os.path.exists("test_photo.jpeg"):
        photo_response = uploader.send_photo(
            "test_photo.jpeg",
            caption="📸 Test photo upload with #hashtag"
        )
        print(f"Photo Status: {photo_response.status_code if photo_response else 'Failed'}")
    else:
        print("Warning: test_photo.jpeg not found")
    
    print("\n=== Testing Video Upload ===")
    # Test with small video file (ensure it's under 50MB)
    if os.path.exists("test_video.mp4"):
        video_response = uploader.send_video(
            "test_video.mp4",
            caption="🎥 Test video upload #test"
        )
        print(f"Video Status: {video_response.status_code if video_response else 'Failed'}")
    else:
        print("Warning: test_video.mp4 not found")

if __name__ == "__main__":
    try:
        test_uploader()
    except Exception as e:
        print(f"Test failed with error: {str(e)}") 