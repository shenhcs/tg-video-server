#open video
#select start and end time
#create clip
#set clip in db

import tkinter as tk
from tkinter import ttk, messagebox
import vlc
import os
from moviepy.editor import VideoFileClip
import time
import json
from dotenv import load_dotenv
from PIL import Image, ImageTk
import sqlite3

class VideoClipper:
    def __init__(self, root):
        # Load configurations
        load_dotenv()
        with open('config.json') as f:
            self.config = json.load(f)
        
        self.root = root
        self.root.title("Video Clipper")
        self.root.geometry("1200x700")
        
        # Use config values
        self.videos_root = self.config['paths']['videos_dir']
        os.makedirs(self.videos_root, exist_ok=True)
        
        self.current_video_path = None
        self.current_video_dir = None
        self.is_playing = False
        
        # Initialize VLC
        self.instance = vlc.Instance('--no-video-title-show')
        self.player = self.instance.media_player_new()
        
        self.setup_ui()
        self.load_video_list()
        
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
        
        # Add right-click context menu
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Rename", command=self.rename_video)
        self.video_listbox.bind('<Button-3>', self.show_context_menu)
        
        # Add video panel
        video_frame = ttk.LabelFrame(right_panel, text="Video Player", padding="10")
        video_frame.pack(fill=tk.BOTH, expand=False, pady=10)
        
        # Video display
        self.video_frame = ttk.Frame(video_frame, width=800, height=450)
        self.video_frame.pack(fill=tk.BOTH, expand=True)
        self.video_frame.pack_propagate(False)  # Keep the frame size
        
        # Create a black background frame for VLC
        self.video_canvas = ttk.Frame(self.video_frame, style='Black.TFrame')
        self.video_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Create a style for black background
        style = ttk.Style()
        style.configure('Black.TFrame', background='black')
        
        # Video controls
        controls_frame = ttk.Frame(self.video_frame)
        controls_frame.pack(fill=tk.X, pady=5)
        
        # Play/Pause button
        self.play_button = ttk.Button(controls_frame, text="Play", command=self.toggle_play)
        self.play_button.pack(side=tk.LEFT, padx=5)
        
        # Time display
        self.time_label = ttk.Label(controls_frame, text="00:00:00 / 00:00:00")
        self.time_label.pack(side=tk.RIGHT, padx=5)
        
        # Seekbar
        self.seek_var = tk.DoubleVar()
        self.seekbar = ttk.Scale(
            controls_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.seek_var,
            command=self.on_seek
        )
        self.seekbar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Add binding for seekbar value changes
        self.seek_var.trace_add('write', lambda *args: self.update_preview())
        
        # Clip creation controls
        clip_frame = ttk.LabelFrame(right_panel, text="Create Clip", padding="10")
        clip_frame.pack(fill=tk.X, pady=10)
        
        # Create left and right frames for controls and preview
        clip_controls = ttk.Frame(clip_frame)
        clip_controls.pack(side=tk.LEFT, fill=tk.Y, padx=5)
        
        preview_frame = ttk.LabelFrame(clip_frame, text="Clip Preview")
        preview_frame.pack(side=tk.RIGHT, padx=10, pady=5)
        
        # Preview
        self.clip_preview = ttk.Label(preview_frame, background='black')
        self.clip_preview.pack(padx=5, pady=5)
        
        # Add preview placeholder
        self.no_preview = ImageTk.PhotoImage(Image.new('RGB', (320, 180), color='black'))  # Larger preview
        self.clip_preview.configure(image=self.no_preview)
        
        # Time controls
        time_frame = ttk.Frame(clip_controls)
        time_frame.pack(fill=tk.X, pady=5)
        
        # Start time with format
        ttk.Label(time_frame, text="Start Time:").pack(side=tk.LEFT, padx=5)
        self.start_time = ttk.Entry(time_frame, width=10)
        self.start_time.insert(0, "00:00:00")
        self.start_time.pack(side=tk.LEFT, padx=5)
        self.start_time.bind('<FocusOut>', self.validate_time_format)
        self.start_time.bind('<Return>', self.validate_time_format)
        self.start_time.bind('<KeyRelease>', lambda e: self.update_preview())
        
        # Set current time buttons
        ttk.Button(time_frame, text="Set Current", command=lambda: self.set_current_time('start')).pack(side=tk.LEFT, padx=5)
        
        # End time with format
        ttk.Label(time_frame, text="End Time:").pack(side=tk.LEFT, padx=5)
        self.end_time = ttk.Entry(time_frame, width=10)
        self.end_time.insert(0, "00:00:00")
        self.end_time.pack(side=tk.LEFT, padx=5)
        self.end_time.bind('<FocusOut>', self.validate_time_format)
        self.end_time.bind('<Return>', self.validate_time_format)
        self.end_time.bind('<KeyRelease>', lambda e: self.update_preview())
        
        ttk.Button(time_frame, text="Set Current", command=lambda: self.set_current_time('end')).pack(side=tk.LEFT, padx=5)
        
        # Output filename
        output_frame = ttk.Frame(clip_controls)
        output_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(output_frame, text="Output Name:").pack(side=tk.LEFT, padx=5)
        self.output_name = ttk.Entry(output_frame, width=30)
        self.output_name.pack(side=tk.LEFT, padx=5)
        
        # Format options
        formats_frame = ttk.Frame(clip_controls)
        formats_frame.pack(fill=tk.X, pady=5)
        
        # Checkbox for MP4 format (always checked and disabled)
        self.create_mp4 = tk.BooleanVar(value=True)
        ttk.Checkbutton(formats_frame, text="MP4", variable=self.create_mp4, state='disabled').pack(side=tk.LEFT, padx=10)
        
        # Create button
        self.create_button = ttk.Button(clip_controls, text="Create Clip", command=self.create_clip)
        self.create_button.pack(pady=10)
    
    def load_video_list(self):
        # Clear and reload video list
        self.video_listbox.delete(0, tk.END)
        
        try:
            # List directories in videos root
            for dir_name in os.listdir(self.videos_root):
                dir_path = os.path.join(self.videos_root, dir_name)
                if os.path.isdir(dir_path):
                    # Check for video file
                    video_path = os.path.join(dir_path, self.config['paths']['video_file'])
                    if os.path.exists(video_path):
                        self.video_listbox.insert(tk.END, dir_name)
                        print(f"Found video: {dir_name}")
                    
        except Exception as e:
            print(f"Error loading videos: {e}")
    
    def get_video_dir(self, dir_name):
        """Get or create the directory for a video"""
        video_dir = os.path.join(self.videos_root, dir_name)
        
        # Create directory structure if it doesn't exist
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(os.path.join(video_dir, self.config['paths']['clips_dir']), exist_ok=True)
        
        # Create links.txt if it doesn't exist
        links_file = os.path.join(video_dir, self.config['paths']['links_file'])
        if not os.path.exists(links_file):
            with open(links_file, 'w') as f:
                f.write("Telegram: \nK2S: \n")
        
        return video_dir
    
    def get_default_output_name(self, video_name):
        """Generate default output name with incrementing number if needed"""
        # Remove extension from video name
        base_name = os.path.splitext(video_name)[0]
        
        # Get clips directory for this video
        clips_dir = os.path.join(self.current_video_dir, self.config['paths']['clips_dir'])
        
        # Start with base_name_clip
        output_name = f"{base_name}_clip"
        
        # Check if file exists and increment number if needed
        counter = 1
        while os.path.exists(os.path.join(clips_dir, f"{output_name}.mp4")):
            output_name = f"{base_name}_clip_{counter}"
            counter += 1
        
        return output_name
    
    def on_video_select(self, event):
        if not self.video_listbox.curselection():
            return
            
        # Clean up previous video preview
        if hasattr(self, 'preview_video') and self.preview_video is not None:
            self.preview_video.close()
            self.preview_video = None
            
        # Stop previous video
        self.player.stop()
        
        # Load new video
        selected_dir = self.video_listbox.get(self.video_listbox.curselection())
        self.current_video_dir = os.path.join(self.videos_root, selected_dir)
        self.current_video_path = os.path.join(self.current_video_dir, self.config['paths']['video_file'])
        
        # Set default output name
        default_name = self.get_default_output_name(selected_dir)
        self.output_name.delete(0, tk.END)
        self.output_name.insert(0, default_name)
        
        # Create media and set it to the player
        media = self.instance.media_new(self.current_video_path)
        self.player.set_media(media)
        
        # Set the video output to our frame
        if os.name == 'nt':  # Windows
            self.player.set_hwnd(self.video_canvas.winfo_id())
        else:  # Linux/Mac
            self.player.set_xwindow(self.video_canvas.winfo_id())
        
        # Get video length for the seekbar
        media.parse()
        self.total_time = media.get_duration() / 1000  # Convert to seconds
        self.seekbar.configure(to=self.total_time)
        
        # Start playback
        self.toggle_play()
    
    def create_clip(self):
        if self.current_video_path is None:
            return
        
        try:
            # Convert time format to seconds
            start = self.time_to_seconds(self.start_time.get())
            end = self.time_to_seconds(self.end_time.get())
            output_name = self.output_name.get()
            
            if not output_name:
                # Use default name if empty
                output_name = self.get_default_output_name(os.path.basename(self.current_video_path))
                self.output_name.delete(0, tk.END)
                self.output_name.insert(0, output_name)
                
            # Get clips directory for this video
            clips_dir = os.path.join(self.current_video_dir, self.config['paths']['clips_dir'])
            
            # Create MP4 output
            output_path = os.path.join(clips_dir, f"{output_name}.mp4")
            
            # Load video and create clip
            video = VideoFileClip(self.current_video_path)
            clip = video.subclip(start, end)
            clip.write_videofile(output_path, codec='libx264', audio_codec='aac')
            video.close()
            
            # Show success message
            messagebox.showinfo("Success", f"Created clip: {output_name}.mp4")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create clip: {str(e)}")
    
    def validate_time_format(self, event=None):
        """Ensure time is in HH:MM:SS format"""
        widget = event.widget
        time_str = widget.get()
        
        try:
            # Split into hours, minutes, seconds
            parts = time_str.replace(":", "").strip()
            if len(parts) <= 6:
                parts = parts.zfill(6)
                formatted = f"{parts[0:2]}:{parts[2:4]}:{parts[4:6]}"
                widget.delete(0, tk.END)
                widget.insert(0, formatted)
            else:
                widget.delete(0, tk.END)
                widget.insert(0, "00:00:00")
        except:
            widget.delete(0, tk.END)
            widget.insert(0, "00:00:00")
    
    def time_to_seconds(self, time_str):
        """Convert HH:MM:SS to seconds"""
        try:
            h, m, s = map(int, time_str.split(':'))
            return h * 3600 + m * 60 + s
        except:
            return 0
    
    def toggle_play(self):
        if self.current_video_path is None:
            return
        
        if self.is_playing:
            self.player.pause()
        else:
            self.player.play()
        
        self.is_playing = not self.is_playing
        self.play_button.configure(text="Pause" if self.is_playing else "Play")
        
        # Start updating the UI
        self.update_ui()
    
    def update_ui(self):
        if self.current_video_path and self.is_playing:
            # Update seekbar
            current_time = self.player.get_time() / 1000  # Convert to seconds
            self.seek_var.set(current_time)
            
            # Update time label
            current_str = time.strftime('%H:%M:%S', time.gmtime(current_time))
            total_str = time.strftime('%H:%M:%S', time.gmtime(self.total_time))
            self.time_label.configure(text=f"{current_str} / {total_str}")
            
            # Schedule next update
            self.root.after(100, self.update_ui)
    
    def on_seek(self, value):
        if self.current_video_path:
            time_ms = int(float(value) * 1000)  # Convert to milliseconds
            self.player.set_time(time_ms)
            self.update_preview()  # Update preview when seeking
    
    def update_preview(self):
        """Update the preview frame based on current time"""
        if not self.current_video_path:
            return
            
        try:
            # Get current time from seekbar
            current_time = self.seek_var.get()  # in seconds
            
            # Get start and end times
            start_time = self.time_to_seconds(self.start_time.get())
            end_time = self.time_to_seconds(self.end_time.get())
            
            # Only show preview if current time is within the clip range
            if start_time <= current_time <= end_time:
                # Cache video object if not already cached
                if not hasattr(self, 'preview_video') or self.preview_video is None:
                    self.preview_video = VideoFileClip(self.current_video_path)
                
                # Get frame at current time
                frame = self.preview_video.get_frame(current_time)
                
                # Convert to PIL Image
                image = Image.fromarray(frame)
                
                # Calculate target size maintaining aspect ratio
                target_width = 320
                target_height = 180  # 16:9 aspect ratio
                
                # Calculate resize dimensions keeping aspect ratio
                aspect = image.width / image.height
                if aspect > target_width/target_height:  # Image is wider
                    new_width = target_width
                    new_height = int(target_width / aspect)
                else:  # Image is taller
                    new_height = target_height
                    new_width = int(target_height * aspect)
                
                # Resize image
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                # Create black background
                bg = Image.new('RGB', (target_width, target_height), 'black')
                
                # Paste resized image in center
                x = (target_width - new_width) // 2
                y = (target_height - new_height) // 2
                bg.paste(image, (x, y))
                
                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(bg)
                
                # Update preview
                self.clip_preview.configure(image=photo)
                self.clip_preview.image = photo  # Keep a reference
            else:
                # Show black frame if outside clip range
                self.clip_preview.configure(image=self.no_preview)
            
        except Exception as e:
            print(f"Error updating preview: {e}")
            self.clip_preview.configure(image=self.no_preview)
    
    def set_current_time(self, which):
        """Set the current video time to the start or end time field"""
        if not self.current_video_path:
            return
            
        # Get current time from seekbar
        current_time = self.seek_var.get()  # This is already in seconds
        time_str = time.strftime('%H:%M:%S', time.gmtime(current_time))
        
        # Update the appropriate entry
        if which == 'start':
            self.start_time.delete(0, tk.END)
            self.start_time.insert(0, time_str)
            self.update_preview()
        else:
            self.end_time.delete(0, tk.END)
            self.end_time.insert(0, time_str)
            self.update_preview()

    def show_context_menu(self, event):
        """Show context menu on right click"""
        try:
            # Get clicked item index
            index = self.video_listbox.nearest(event.y)
            if index >= 0:
                self.video_listbox.selection_clear(0, tk.END)
                self.video_listbox.selection_set(index)
                self.video_listbox.activate(index)
                self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def rename_video(self):
        """Rename video directory"""
        selection = self.video_listbox.curselection()
        if not selection:
            return
            
        current_name = self.video_listbox.get(selection[0])
        old_dir = os.path.join(self.videos_root, current_name)
        
        # Create rename dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Video")
        dialog.geometry("400x120")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center dialog on screen
        dialog.geometry("+%d+%d" % (
            self.root.winfo_rootx() + self.root.winfo_width()//2 - 200,
            self.root.winfo_rooty() + self.root.winfo_height()//2 - 60
        ))
        
        # Add widgets
        ttk.Label(dialog, text="Enter new name:").pack(pady=10)
        
        # Entry with current name
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=40)
        name_entry.pack(padx=10, pady=5)
        name_entry.select_range(0, tk.END)
        name_entry.focus()
        
        def do_rename():
            new_name = name_var.get().strip()
            if new_name:
                # Check if new name already exists
                new_dir = os.path.join(self.videos_root, new_name)
                if new_name != current_name and os.path.exists(new_dir):
                    messagebox.showerror("Error", "A directory with this name already exists!")
                    return
                
                try:
                    # Rename directory
                    os.rename(old_dir, new_dir)
                    
                    # Update listbox
                    self.load_video_list()
                    
                    # If this was the current video, update paths
                    if self.current_video_dir == old_dir:
                        self.current_video_dir = new_dir
                        self.current_video_path = os.path.join(new_dir, self.config['paths']['video_file'])
                    
                    dialog.destroy()
                    
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to rename: {str(e)}")
                    return
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="OK", command=do_rename).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        
        # Bind Enter key to OK button
        dialog.bind('<Return>', lambda e: do_rename())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def scan_for_new_videos(self):
        """Scan videos directory and add untracked videos with 'new' status"""
        conn = sqlite3.connect('videos.db')
        cursor = conn.cursor()
        
        # Get all tracked video paths
        cursor.execute("SELECT path FROM videos")
        tracked_paths = set(row[0] for row in cursor.fetchall())
        
        # Scan filesystem
        for dir_name in os.listdir(self.videos_root):
            dir_path = os.path.join(self.videos_root, dir_name)
            if os.path.isdir(dir_path):
                video_path = os.path.join(dir_path, self.config['paths']['video_file'])
                
                if os.path.exists(video_path) and video_path not in tracked_paths:
                    cursor.execute("""
                        INSERT INTO videos (
                            filename, 
                            path, 
                            status,
                            k2s_status,
                            created_at
                        ) VALUES (?, ?, 'new', 'pending', CURRENT_TIMESTAMP)
                    """, (dir_name, video_path))
                    print(f"Added new video: {dir_name}")
        
        conn.commit()
        conn.close()

    def get_new_videos(self):
        """Get list of videos with 'new' status"""
        conn = sqlite3.connect('videos.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, filename, path 
            FROM videos 
            WHERE status = 'new'
            ORDER BY created_at ASC
        """)
        
        new_videos = cursor.fetchall()
        conn.close()
        return new_videos

if __name__ == "__main__":
    root = tk.Tk()
    app = VideoClipper(root)
    root.mainloop() 