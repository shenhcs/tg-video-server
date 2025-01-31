import tkinter as tk
from tkinter import ttk, messagebox
import vlc
import os
from moviepy.editor import VideoFileClip
import time
import json
from dotenv import load_dotenv
from PIL import Image, ImageTk
from database.db_manager import DatabaseManager
from database.db import Session
from database.models import K2SStatus

class VideoClipper:
    def __init__(self, root):
        # Load configurations
        load_dotenv()
        with open('config.json') as f:
            self.config = json.load(f)
        
        self.root = root
        self.root.title("Video Clipper")
        self.root.geometry("1200x700")
        
        # Initialize database
        self.session = Session()
        self.db = DatabaseManager(self.session)
        
        # Use config values
        self.videos_root = os.path.join(os.getcwd(), self.config['paths']['videos_dir'])
        os.makedirs(self.videos_root, exist_ok=True)
        
        # Create all required directories
        for dir_name in ['new_videos_dir', 'videos_dir', 'clips_dir']:
            dir_path = os.path.join(os.getcwd(), self.config['paths'][dir_name])
            os.makedirs(dir_path, exist_ok=True)
        
        self.current_video_path = None
        self.is_playing = False
        
        # Initialize VLC with additional parameters to avoid timing errors
        vlc_args = [
            '--no-video-title-show',  # Don't show title
            '--no-xlib',  # Avoid X11 dependency
            '--quiet',    # Reduce logging
            '--no-snapshot-preview',  # Disable snapshot preview
            '--live-caching=300',  # Increase live caching
            '--network-caching=1000',  # Increase network caching
            '--disc-caching=1000',  # Increase disc caching
            '--file-caching=1000',  # Increase file caching
        ]
        self.instance = vlc.Instance(' '.join(vlc_args))
        self.player = self.instance.media_player_new()
        
        # Set up event manager for position tracking
        self.event_manager = self.player.event_manager()
        self.event_manager.event_attach(vlc.EventType.MediaPlayerPositionChanged, self._on_position_changed)
        
        self.setup_ui()
        self.load_video_list()

    def __del__(self):
        """Cleanup when the object is destroyed"""
        if hasattr(self, 'session'):
            self.session.close()

    def load_video_list(self):
        """Load list of videos that haven't been uploaded to K2S yet"""
        self.video_listbox.delete(0, tk.END)
        
        try:
            # Get all videos from the videos directory
            videos_dir = os.path.join(os.getcwd(), self.config['paths']['videos_dir'])
            for filename in os.listdir(videos_dir):
                video_path = os.path.join(videos_dir, filename)
                if os.path.isfile(video_path):
                    # Check if it's a video file
                    _, ext = os.path.splitext(filename)
                    if ext.lower() in self.config['video']['supported_formats']:
                        # Check if video is in database and not uploaded to K2S
                        video_record = self.db.get_video_by_filename(filename)
                        if not video_record:
                            # Add to database if not exists
                            video_record = self.db.add_video(filename, str(video_path))
                            print(f"Added new video to database: {filename}")
                        
                        # Only show videos that haven't been uploaded to K2S
                        if video_record.k2s_status != K2SStatus.UPLOADED:
                            self.video_listbox.insert(tk.END, filename)
                            print(f"Found unuploaded video: {filename}")
                    
        except Exception as e:
            print(f"Error loading videos: {e}")
            messagebox.showerror("Error", f"Failed to load videos: {str(e)}")

    def on_video_select(self, event):
        if not self.video_listbox.curselection():
            return
            
        # Stop previous video and release resources
        self.player.stop()
        if hasattr(self, 'media'):
            self.media.release()
        
        # Load new video
        selected_file = self.video_listbox.get(self.video_listbox.curselection())
        self.current_video_path = os.path.join(os.getcwd(), self.config['paths']['videos_dir'], selected_file)
        
        # Set default output name
        default_name = self.get_default_output_name(selected_file)
        self.output_name.delete(0, tk.END)
        self.output_name.insert(0, default_name)
        
        # Create media with caching options
        self.media = self.instance.media_new(self.current_video_path)
        self.media.add_option('network-caching=1000')
        self.media.add_option('file-caching=1000')
        self.media.add_option('live-caching=1000')
        self.player.set_media(self.media)
        
        # Set the video output to our frame
        if os.name == 'nt':  # Windows
            self.player.set_hwnd(self.video_canvas.winfo_id())
        else:  # Linux/Mac
            self.player.set_xwindow(self.video_canvas.winfo_id())
        
        # Parse media to get duration
        self.media.parse_with_options(
            vlc.MediaParseFlag.local,
            timeout=1000
        )
        self.duration = self.media.get_duration() / 1000  # Convert to seconds
        self.seekbar.configure(to=self.duration)
        self.seek_var.set(0)  # Reset position
        
        # Start playing
        self.toggle_play()
        
    def get_default_output_name(self, video_name):
        """Generate default output name with incrementing number if needed"""
        # Remove extension from video name
        base_name = os.path.splitext(video_name)[0]
        
        # Get clips directory
        clips_dir = os.path.join(os.getcwd(), self.config['paths']['clips_dir'])
        os.makedirs(clips_dir, exist_ok=True)
        
        # Start with base_name_clip
        output_name = f"{base_name}_clip"
        
        # Check if file exists and increment number if needed
        counter = 1
        while os.path.exists(os.path.join(clips_dir, f"{output_name}.mp4")):
            output_name = f"{base_name}_clip_{counter}"
            counter += 1
        
        return output_name 

    def setup_ui(self):
        # Main layout
        left_panel = ttk.Frame(self.root, padding="10")
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        right_panel = ttk.Frame(self.root, padding="10")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Left panel - Video list
        ttk.Label(left_panel, text="Videos:").pack(anchor=tk.W)
        
        # Create a frame to hold the listbox and scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create listbox with scrollbar
        self.video_listbox = tk.Listbox(list_frame, width=30, height=20, yscrollcommand=scrollbar.set)
        self.video_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        scrollbar.config(command=self.video_listbox.yview)
        
        self.video_listbox.bind('<<ListboxSelect>>', self.on_video_select)
        
        # Right panel - Video player
        # Video canvas
        self.video_canvas = ttk.Frame(right_panel, style='Black.TFrame')
        self.video_canvas.configure(width=800, height=450)
        self.video_canvas.pack(pady=10)
        self.video_canvas.pack_propagate(False)
        
        # Create style for black background
        style = ttk.Style()
        style.configure('Black.TFrame', background='black')
        
        # Controls frame
        controls = ttk.Frame(right_panel)
        controls.pack(fill=tk.X, pady=5)
        
        # Play button
        self.play_button = ttk.Button(controls, text="Play", command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT, padx=5)
        
        # Seekbar with DoubleVar
        self.seek_var = tk.DoubleVar()
        self.seekbar = ttk.Scale(
            controls,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.seek_var,
            command=self.on_seek
        )
        self.seekbar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Add bindings for seekbar dragging
        self.seekbar.bind("<Button-1>", self.on_seek_start)
        self.seekbar.bind("<ButtonRelease-1>", self.on_seek_end)
        self.is_seeking = False
        
        # Time label
        self.time_label = ttk.Label(controls, text="00:00:00 / 00:00:00")
        self.time_label.pack(side=tk.LEFT, padx=5)
        
        # Volume control
        volume_frame = ttk.Frame(controls)
        volume_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Label(volume_frame, text="🔊").pack(side=tk.LEFT)
        self.volume_scale = ttk.Scale(volume_frame, from_=0, to=100, orient=tk.HORIZONTAL, 
                                    command=self.on_volume_change, length=100)
        self.volume_scale.set(100)  # Default volume
        self.volume_scale.pack(side=tk.LEFT)
        
        # Clip controls
        clip_controls = ttk.LabelFrame(right_panel, text="Create Clip", padding="10")
        clip_controls.pack(fill=tk.X, pady=10)
        
        # Start/End time frame
        time_frame = ttk.Frame(clip_controls)
        time_frame.pack(fill=tk.X)
        
        # Start time
        ttk.Label(time_frame, text="Start:").pack(side=tk.LEFT)
        self.start_time = ttk.Entry(time_frame, width=10)
        self.start_time.pack(side=tk.LEFT, padx=5)
        ttk.Button(time_frame, text="Set", command=lambda: self.set_time('start')).pack(side=tk.LEFT)
        
        # End time
        ttk.Label(time_frame, text="End:").pack(side=tk.LEFT, padx=(20,0))
        self.end_time = ttk.Entry(time_frame, width=10)
        self.end_time.pack(side=tk.LEFT, padx=5)
        ttk.Button(time_frame, text="Set", command=lambda: self.set_time('end')).pack(side=tk.LEFT)
        
        # Output name
        name_frame = ttk.Frame(clip_controls)
        name_frame.pack(fill=tk.X, pady=10)
        ttk.Label(name_frame, text="Output name:").pack(side=tk.LEFT)
        self.output_name = ttk.Entry(name_frame)
        self.output_name.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Create button
        self.create_button = ttk.Button(clip_controls, text="Create", command=self.create_clip)
        self.create_button.pack(pady=10)
    
    def toggle_play(self):
        if not self.current_video_path:
            return
            
        if self.is_playing:
            self.player.pause()
            self.play_button.configure(text="Play")
        else:
            # Set media options before playing
            if self.player.get_media():
                self.player.get_media().add_option('network-caching=1000')
                self.player.get_media().add_option('file-caching=1000')
            self.player.play()
            self.play_button.configure(text="Pause")
            self.update_ui()
            
        self.is_playing = not self.is_playing
    
    def update_ui(self):
        """Schedule next UI update if playing"""
        if self.current_video_path and self.is_playing:
            self.root.after(100, self.update_ui)
    
    def on_seek_start(self, event):
        """Called when user starts dragging the seekbar"""
        self.is_seeking = True
        if self.is_playing:
            self.player.pause()
    
    def on_seek_end(self, event):
        """Called when user releases the seekbar"""
        if self.current_video_path:
            # Get final position
            time_ms = int(float(self.seek_var.get()) * 1000)
            self.player.set_time(time_ms)
            
            # Resume playback if it was playing
            if self.is_playing:
                self.player.play()
        
        self.is_seeking = False
    
    def on_seek(self, value):
        """Called during seekbar dragging"""
        if self.current_video_path and self.is_seeking:
            # Update time label while dragging
            current_time = float(value)
            current_str = time.strftime('%H:%M:%S', time.gmtime(current_time))
            total_str = time.strftime('%H:%M:%S', time.gmtime(self.duration))
            self.time_label.configure(text=f"{current_str} / {total_str}")
    
    def set_time(self, which):
        if not self.current_video_path:
            return
            
        current_time = time.strftime('%H:%M:%S', time.gmtime(self.player.get_time() // 1000))
        if which == 'start':
            self.start_time.delete(0, tk.END)
            self.start_time.insert(0, current_time)
        else:
            self.end_time.delete(0, tk.END)
            self.end_time.insert(0, current_time)
    
    def create_clip(self):
        if not self.current_video_path:
            return
            
        try:
            # Get start and end times
            start = time.strptime(self.start_time.get(), '%H:%M:%S')
            end = time.strptime(self.end_time.get(), '%H:%M:%S')
            
            start_seconds = start.tm_hour * 3600 + start.tm_min * 60 + start.tm_sec
            end_seconds = end.tm_hour * 3600 + end.tm_min * 60 + end.tm_sec
            
            if start_seconds >= end_seconds:
                messagebox.showerror("Error", "End time must be after start time")
                return
                
            # Get output name
            output_name = self.output_name.get()
            if not output_name:
                messagebox.showerror("Error", "Please enter an output name")
                return
                
            # Create clips directory if it doesn't exist
            clips_dir = os.path.join(os.getcwd(), self.config['paths']['clips_dir'])
            os.makedirs(clips_dir, exist_ok=True)
            
            # Output path
            output_path = os.path.join(clips_dir, f"{output_name}.mp4")
            
            # Check if file exists
            if os.path.exists(output_path):
                if not messagebox.askyesno("Warning", "File already exists. Overwrite?"):
                    return
            
            print(f"Creating clip from {self.current_video_path} to {output_path}")
            print(f"Time range: {start_seconds} to {end_seconds} seconds")
            
            # Create clip
            video = VideoFileClip(self.current_video_path)
            clip = video.subclip(start_seconds, end_seconds)
            clip.write_videofile(output_path)
            video.close()
            clip.close()
            
            # Get parent video record
            video_filename = os.path.basename(self.current_video_path)
            video_record = self.db.get_video_by_filename(video_filename)
            
            if video_record:
                # Add clip to database with parent video ID
                self.db.add_clip(
                    video_id=video_record.id,
                    filename=f"{output_name}.mp4",
                    path=output_path,
                    start_time=start_seconds,
                    end_time=end_seconds
                )
                messagebox.showinfo("Success", f"Clip created successfully at {output_path}")
            else:
                messagebox.showerror("Error", f"Parent video {video_filename} not found in database")
            
        except ValueError:
            messagebox.showerror("Error", "Invalid time format. Use HH:MM:SS")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create clip: {str(e)}")
            print(f"Error details: {str(e)}")

    def on_volume_change(self, value):
        """Handle volume slider changes"""
        if not self.current_video_path:
            return
        volume = int(float(value))
        self.player.audio_set_volume(volume)

    def _on_position_changed(self, event):
        """Called by VLC when the playback position changes"""
        if not self.is_seeking and self.current_video_path:
            current_time = self.player.get_time() / 1000  # Convert to seconds
            if current_time >= 0:
                self.seek_var.set(current_time)
                current_str = time.strftime('%H:%M:%S', time.gmtime(current_time))
                total_str = time.strftime('%H:%M:%S', time.gmtime(self.duration))
                self.time_label.configure(text=f"{current_str} / {total_str}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoClipper(root)
    root.mainloop() 