"""
Main Application Launcher - Action Recording & Playback System
Choose between recording new actions or playing back existing recordings
"""
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys
import subprocess
from datetime import datetime


class LauncherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Action Recording & Playback System")
        self.root.geometry("600x500")
        self.root.resizable(False, False)

        # Center the window
        self.center_window()

        # Create GUI elements
        self.create_widgets()
        self.setup_layout()

    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def create_widgets(self):
        """Create all GUI widgets"""

        # Main title
        title_frame = ttk.Frame(self.root)
        title_label = ttk.Label(title_frame, text="Action Recording & Playback System",
                                font=("Arial", 16, "bold"))
        subtitle_label = ttk.Label(title_frame, text="Record and replay mouse & keyboard actions",
                                   font=("Arial", 10), foreground="gray")

        # Main action buttons frame
        actions_frame = ttk.LabelFrame(self.root, text="Choose Action")

        # Recording section
        record_frame = ttk.Frame(actions_frame)
        record_icon = ttk.Label(record_frame, text="🔴", font=("Arial", 24))
        record_title = ttk.Label(record_frame, text="Record Actions", font=("Arial", 12, "bold"))
        record_desc = ttk.Label(record_frame, text="Capture mouse movements, clicks, and keyboard input\n"
                                                   "• Real-time recording with F10 hotkey\n"
                                                   "• 100 FPS input monitoring\n"
                                                   "• Mouse movement optimization\n"
                                                   "• Save recordings as JSON files",
                                font=("Arial", 9), justify="left")
        record_btn = ttk.Button(record_frame, text="Start Recording Interface",
                                command=self.launch_recorder, style="Accent.TButton")

        # Playback section
        playback_frame = ttk.Frame(actions_frame)
        playback_icon = ttk.Label(playback_frame, text="▶️", font=("Arial", 24))
        playback_title = ttk.Label(playback_frame, text="Playback Actions", font=("Arial", 12, "bold"))
        playback_desc = ttk.Label(playback_frame, text="Replay previously recorded actions\n"
                                                       "• Load recordings from JSON files\n"
                                                       "• Adjustable playback speed\n"
                                                       "• Target specific windows or global\n"
                                                       "• Pause/resume/stop controls",
                                  font=("Arial", 9), justify="left")
        playback_btn = ttk.Button(playback_frame, text="Start Playback Interface",
                                  command=self.launch_playback, style="Accent.TButton")

        # Info section
        info_frame = ttk.LabelFrame(self.root, text="Quick Info")

        # System requirements
        req_frame = ttk.Frame(info_frame)
        req_title = ttk.Label(req_frame, text="System Requirements:", font=("Arial", 10, "bold"))
        req_text = ttk.Label(req_frame,
                             text="• Windows OS\n• Python 3.7+\n• pywin32 library\n• No admin rights required",
                             font=("Arial", 9), justify="left")

        # File info
        file_frame = ttk.Frame(info_frame)
        file_title = ttk.Label(file_frame, text="File Locations:", font=("Arial", 10, "bold"))
        file_text = ttk.Label(file_frame, text="• Recordings: ./runs/\n• Logs: ./logs/\n• Format: JSON",
                              font=("Arial", 9), justify="left")

        # Status frame
        status_frame = ttk.Frame(self.root)
        self.status_text = ttk.Label(status_frame, text="Ready - Choose an action above",
                                     font=("Arial", 9), foreground="green")

        # Bottom buttons
        bottom_frame = ttk.Frame(self.root)
        help_btn = ttk.Button(bottom_frame, text="Help", command=self.show_help)
        about_btn = ttk.Button(bottom_frame, text="About", command=self.show_about)
        exit_btn = ttk.Button(bottom_frame, text="Exit", command=self.root.quit)

        # Store references
        self.title_frame = title_frame
        self.title_label = title_label
        self.subtitle_label = subtitle_label
        self.actions_frame = actions_frame
        self.record_frame = record_frame
        self.record_icon = record_icon
        self.record_title = record_title
        self.record_desc = record_desc
        self.record_btn = record_btn
        self.playback_frame = playback_frame
        self.playback_icon = playback_icon
        self.playback_title = playback_title
        self.playback_desc = playback_desc
        self.playback_btn = playback_btn
        self.info_frame = info_frame
        self.req_frame = req_frame
        self.req_title = req_title
        self.req_text = req_text
        self.file_frame = file_frame
        self.file_title = file_title
        self.file_text = file_text
        self.status_frame = status_frame
        self.bottom_frame = bottom_frame
        self.help_btn = help_btn
        self.about_btn = about_btn
        self.exit_btn = exit_btn

    def setup_layout(self):
        """Setup widget layout"""

        # Title section
        self.title_frame.pack(fill="x", padx=20, pady=(20, 10))
        self.title_label.pack()
        self.subtitle_label.pack(pady=(5, 0))

        # Main actions section
        self.actions_frame.pack(fill="both", expand=True, padx=20, pady=10)

        # Recording section
        self.record_frame.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=10)
        self.record_icon.pack(pady=(0, 10))
        self.record_title.pack()
        self.record_desc.pack(pady=(10, 15), padx=10)
        self.record_btn.pack(pady=(0, 10))

        # Separator
        separator = ttk.Separator(self.actions_frame, orient="vertical")
        separator.pack(side="left", fill="y", padx=5)

        # Playback section
        self.playback_frame.pack(side="right", fill="both", expand=True, padx=(5, 10), pady=10)
        self.playback_icon.pack(pady=(0, 10))
        self.playback_title.pack()
        self.playback_desc.pack(pady=(10, 15), padx=10)
        self.playback_btn.pack(pady=(0, 10))

        # Info section
        self.info_frame.pack(fill="x", padx=20, pady=(0, 10))

        info_content = ttk.Frame(self.info_frame)
        info_content.pack(fill="x", padx=10, pady=10)

        # Requirements
        self.req_frame.pack(side="left", fill="x", expand=True)
        self.req_title.pack(anchor="w")
        self.req_text.pack(anchor="w", pady=(5, 0))

        # File locations
        self.file_frame.pack(side="right", fill="x", expand=True)
        self.file_title.pack(anchor="w")
        self.file_text.pack(anchor="w", pady=(5, 0))

        # Status
        self.status_frame.pack(fill="x", padx=20, pady=(0, 10))
        self.status_text.pack()

        # Bottom buttons
        self.bottom_frame.pack(fill="x", padx=20, pady=(0, 20))
        self.help_btn.pack(side="left")
        self.about_btn.pack(side="left", padx=(10, 0))
        self.exit_btn.pack(side="right")

    def update_status(self, message: str, color: str = "black"):
        """Update status message"""
        self.status_text.config(text=message, foreground=color)
        self.root.update()

    def launch_recorder(self):
        """Launch the recording interface"""
        try:
            self.update_status("Starting recording interface...", "blue")

            # Check if recording module exists
            if not os.path.exists("repeater_gui.py"):
                messagebox.showerror("Error", "Recording interface (repeater_gui.py) not found!")
                self.update_status("Error: Recording interface not found", "red")
                return

            # Launch recorder GUI
            if sys.platform.startswith('win'):
                subprocess.Popen([sys.executable, "repeater_gui.py"],
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen([sys.executable, "repeater_gui.py"])

            self.update_status("Recording interface launched successfully", "green")

        except Exception as e:
            error_msg = f"Failed to launch recording interface: {e}"
            messagebox.showerror("Error", error_msg)
            self.update_status("Error launching recording interface", "red")

    def launch_playback(self):
        """Launch the playback interface"""
        try:
            self.update_status("Starting playback interface...", "blue")

            # Check if playback module exists
            if not os.path.exists("playback_gui.py"):
                messagebox.showerror("Error", "Playback interface (playback_gui.py) not found!")
                self.update_status("Error: Playback interface not found", "red")
                return

            # Launch playback GUI
            if sys.platform.startswith('win'):
                subprocess.Popen([sys.executable, "playback_gui.py"],
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                subprocess.Popen([sys.executable, "playback_gui.py"])

            self.update_status("Playback interface launched successfully", "green")

        except Exception as e:
            error_msg = f"Failed to launch playback interface: {e}"
            messagebox.showerror("Error", error_msg)
            self.update_status("Error launching playback interface", "red")

    def show_help(self):
        """Show help information"""
        help_text = """Action Recording & Playback System - Help

RECORDING:
1. Click "Start Recording Interface"
2. Select a target window from the list
3. Click "Start Recording" or press F10
4. Perform your actions (mouse movements, clicks, keys)
5. Press F10 again or click "Stop Recording"
6. Save your recording with a name

PLAYBACK:
1. Click "Start Playback Interface"
2. Select a recording from the list or load a file
3. Optionally select a target window
4. Adjust playback speed if needed
5. Click "Play" to start playback
6. Use Pause/Stop controls as needed

FEATURES:
• Real-time input capture at 100 FPS
• Mouse movement optimization
• Relative/absolute coordinate modes
• Variable playback speed (0.1x to 5.0x)
• Detailed logging and statistics
• No administrator privileges required

FILE FORMATS:
• Recordings saved as JSON files in ./runs/
• Logs saved in ./logs/
• Human-readable format for debugging

HOTKEYS:
• F10: Start/Stop recording (recording mode only)
• GUI buttons for all other controls

TIPS:
• Use relative coordinates for window-specific actions
• Use global coordinates for desktop-wide automation
• Enable debug logging to see detailed key events
• Check logs if something doesn't work as expected"""

        # Create help window
        help_window = tk.Toplevel(self.root)
        help_window.title("Help")
        help_window.geometry("600x500")
        help_window.resizable(True, True)

        # Help text widget
        help_frame = ttk.Frame(help_window)
        help_frame.pack(fill="both", expand=True, padx=10, pady=10)

        help_text_widget = tk.Text(help_frame, wrap=tk.WORD, font=("Consolas", 9))
        help_scrollbar = ttk.Scrollbar(help_frame, orient="vertical", command=help_text_widget.yview)
        help_text_widget.configure(yscrollcommand=help_scrollbar.set)

        help_text_widget.pack(side="left", fill="both", expand=True)
        help_scrollbar.pack(side="right", fill="y")

        help_text_widget.insert("1.0", help_text)
        help_text_widget.config(state=tk.DISABLED)

        # Close button
        close_btn = ttk.Button(help_window, text="Close", command=help_window.destroy)
        close_btn.pack(pady=10)

    def show_about(self):
        """Show about information"""
        about_text = f"""Action Recording & Playback System

Version: 1.0
Created: {datetime.now().strftime('%Y')}

A Windows automation tool for recording and playing back
mouse and keyboard actions.

COMPONENTS:
• recording.py - Input capture and recording engine
• repeater_gui.py - Recording interface
• playback.py - Action playback engine  
• playback_gui.py - Playback interface
• launcher.py - Main application launcher

TECHNOLOGIES:
• Python 3.7+
• tkinter - GUI framework
• pywin32 - Windows API access
• JSON - Data storage format

FEATURES:
• High-precision input capture (100 FPS)
• Mouse movement optimization
• Keyboard combination support
• Variable playback speeds
• Window-relative coordinates
• Comprehensive logging

NO ADMIN REQUIRED:
Uses polling instead of hooks for compatibility.

For support or updates, check the project documentation."""

        messagebox.showinfo("About", about_text)

    def check_dependencies(self):
        """Check if required dependencies are available"""
        missing = []

        try:
            import win32api
            import win32con
            import win32gui
        except ImportError:
            missing.append("pywin32")

        if missing:
            messagebox.showerror("Missing Dependencies",
                                 f"Missing required packages: {', '.join(missing)}\n\n"
                                 "Please install with:\n"
                                 "pip install pywin32")
            return False

        return True

    def check_files(self):
        """Check if required files exist"""
        files = ["recording.py", "repeater_gui.py", "playback.py", "playback_gui.py"]
        missing = [f for f in files if not os.path.exists(f)]

        if missing:
            messagebox.showwarning("Missing Files",
                                   f"Some components are missing:\n{chr(10).join(missing)}\n\n"
                                   "Some features may not work correctly.")
            return False

        return True

    def create_directories(self):
        """Create necessary directories"""
        directories = ["runs", "logs"]
        for directory in directories:
            if not os.path.exists(directory):
                try:
                    os.makedirs(directory)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to create directory {directory}: {e}")

    def run(self):
        """Start the application"""
        # Initial checks
        if not self.check_dependencies():
            return

        self.check_files()
        self.create_directories()

        # Show directory info
        runs_count = len([f for f in os.listdir("runs") if f.endswith('.json')]) if os.path.exists("runs") else 0
        if runs_count > 0:
            self.update_status(f"Ready - {runs_count} recordings found in ./runs/", "green")
        else:
            self.update_status("Ready - No recordings found, start by recording some actions", "blue")

        # Start GUI
        self.root.mainloop()


def main():
    """Main entry point"""
    try:
        app = LauncherGUI()
        app.run()
    except Exception as e:
        print(f"Failed to start launcher: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()