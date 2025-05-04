import json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from functools import partial
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import pyperclip first (the most reliable clipboard option)
try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
    logger.info("Using pyperclip for clipboard operations")
except ImportError:
    CLIPBOARD_AVAILABLE = False
    logger.warning("pyperclip not available, falling back to tkinter clipboard")

# Optional dependencies for enhanced features
try:
    import requests
    from io import BytesIO
    from PIL import Image, ImageTk
    IMAGE_PROCESSING_AVAILABLE = True
except ImportError:
    IMAGE_PROCESSING_AVAILABLE = False
    logger.warning("PIL or requests not available, channel icons will be disabled")

try:
    from thefuzz import process
    FUZZY_SEARCH_AVAILABLE = True
except ImportError:
    FUZZY_SEARCH_AVAILABLE = False
    logger.warning("thefuzz not available, falling back to simple search")


class TwitchChannelSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Twitch Channel Search")
        self.root.geometry("400x600")
        self.setup_ui()
        
        # Data holders
        self.channels = []
        self.filtered_channels = []
        self.channel_icons = {}
        self.search_index = []
        self.debounce_timer = None
        
        # Try to use a dark theme
        self.apply_theme()
        
        # Load channel data
        self.load_channels()
        
        # Set focus to search entry
        self.search_entry.focus_set()
        
        # Bind Escape key to exit
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        
    def apply_theme(self):
        """Apply dark theme if possible"""
        try:
            # Try to use ttk themed widgets with a dark theme
            style = ttk.Style()
            available_themes = style.theme_names()
            
            # Look for a dark theme
            dark_themes = ["clam", "alt", "vista"]
            for theme in dark_themes:
                if theme in available_themes:
                    style.theme_use(theme)
                    break
            
            # Configure colors for dark theme
            style.configure("Treeview", 
                           background="#333333", 
                           foreground="white", 
                           fieldbackground="#333333")
            style.map('Treeview', background=[('selected', '#4a6984')])
            
            # Configure entry widget colors
            style.configure("Dark.TEntry", 
                           foreground="white",
                           fieldbackground="#333333",
                           insertcolor="white")
            
            # Configure frame colors
            self.root.configure(background="#1e1e1e")
            
        except Exception as e:
            logger.warning(f"Failed to apply dark theme: {e}")
            
    def setup_ui(self):
        """Set up the UI components"""
        # Create main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Search entry
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search_changed)
        self.search_entry = ttk.Entry(main_frame, textvariable=self.search_var, font=("Segoe UI", 12))
        self.search_entry.pack(fill=tk.X, padx=5, pady=5)
        self.search_entry.bind("<Return>", self.on_search_activated)
        
        # Treeview for channels
        columns = ("name",)
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=20)
        self.tree.heading("name", text="Channel Name")
        self.tree.column("name", width=300)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Vertical scrollbar
        vsb = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=vsb.set)
        
        # Bind double-click and Enter on treeview
        self.tree.bind("<Double-1>", self.on_item_activated)
        self.tree.bind("<Return>", self.on_item_activated)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def load_channels(self):
        """Load channel data from JSON file"""
        try:
            # Check multiple locations for the JSON file
            potential_paths = [
                # Current directory (for backward compatibility)
                os.path.join(os.path.dirname(__file__), "followed_channels.json"),
                
                # Check in %APPDATA%\OpenDeck if exists
                os.path.join(os.environ.get("APPDATA", ""), "OpenDeck", "followed_channels.json")
            ]
            
            json_path = None
            for path in potential_paths:
                if os.path.exists(path):
                    json_path = path
                    break
                    
            if json_path:
                with open(json_path, "r", encoding="utf-8") as f:
                    self.channels = json.load(f)
                self.status_var.set(f"Loaded {len(self.channels)} channels from {json_path}")
                logger.info(f"Loaded channels: {len(self.channels)} from {json_path}")

                # Build search index for faster matching
                self.build_search_index()

                # Show initial channels (first 10 items)
                self.filtered_channels = self.channels[:10]
                self.update_list_view()
            else:
                error_msg = "No channels data found. Please run fuzzy_search.py first."
                self.status_var.set(error_msg)
                logger.warning(error_msg)
                messagebox.showwarning("No Data", 
                                     "No channel data found. Please run fuzzy_search.py first to fetch your followed channels.")
        except json.JSONDecodeError as e:
            error_msg = f"Error parsing JSON file: {e}"
            self.status_var.set(error_msg)
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
        except Exception as e:
            error_msg = f"Error loading channels: {e}"
            self.status_var.set(error_msg)
            logger.error(error_msg)
            messagebox.showerror("Error", error_msg)
        
    def build_search_index(self):
        """Build search index for channel names"""
        self.search_index = []
        for channel in self.channels:
            name = channel["broadcaster_name"].lower()
            self.search_index.append(name)
            
    def on_search_changed(self, *args):
        """Handle search input changes with debounce"""
        # Cancel previous timer if it exists
        if self.debounce_timer is not None:
            self.root.after_cancel(self.debounce_timer)
        
        # Set a new timer to delay the search
        self.debounce_timer = self.root.after(150, self.perform_search)
    
    def perform_search(self):
        """Execute the search"""
        query = self.search_var.get().lower()
        self.debounce_timer = None
        
        if not query:
            self.filtered_channels = self.channels[:10]
        else:
            if FUZZY_SEARCH_AVAILABLE:
                # Use fuzzy search
                proc_result = process.extract(query, self.search_index, limit=10)
                self.filtered_channels = []
                for result_name, score in proc_result:
                    # Find the corresponding channel
                    channel = next((c for c in self.channels if c["broadcaster_name"].lower() == result_name), None)
                    if channel:
                        self.filtered_channels.append(channel)
            else:
                # Simple contains search
                self.filtered_channels = []
                for channel in self.channels:
                    if query in channel["broadcaster_name"].lower():
                        self.filtered_channels.append(channel)
                        if len(self.filtered_channels) >= 10:
                            break
        
        self.update_list_view()
    
    def update_list_view(self):
        """Update the treeview with filtered channels"""
        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Add filtered channels
        for channel in self.filtered_channels:
            name = channel["broadcaster_name"]
            channel_id = channel["broadcaster_id"]
            item_id = self.tree.insert("", "end", values=(name,), iid=channel_id)
            
            # Load channel icon if available
            if IMAGE_PROCESSING_AVAILABLE:
                profile_url = channel.get("profile_image_url")
                if profile_url and channel_id not in self.channel_icons:
                    # Load icon in background
                    threading.Thread(
                        target=self.load_channel_icon,
                        args=(channel_id, profile_url),
                        daemon=True
                    ).start()
        
        # Select the first item if available
        if self.filtered_channels:
            first_id = self.filtered_channels[0]["broadcaster_id"]
            self.tree.selection_set(first_id)
            self.tree.focus(first_id)
            
    def load_channel_icon(self, channel_id, url):
        """Load channel icon in background thread"""
        if not IMAGE_PROCESSING_AVAILABLE:
            return
            
        try:
            response = requests.get(url)
            if response.status_code == 200:
                # Process image
                img = Image.open(BytesIO(response.content))
                img = img.resize((24, 24))  # Size for icon
                
                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(img)
                
                # Store in the icons dict
                self.channel_icons[channel_id] = photo
                
                # Update UI in main thread
                self.root.after(0, partial(self.update_channel_icon, channel_id))
            else:
                logger.error(f"Error loading icon for {channel_id}: HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Error loading icon for {channel_id}: {e}")
            
    def update_channel_icon(self, channel_id):
        """Update channel icon in the UI (must be called in main thread)"""
        try:
            # For Tkinter, we would need to customize the treeview to show icons
            # This is more complex and not implemented in this basic version
            pass
        except Exception as e:
            logger.error(f"Error updating icon for {channel_id}: {e}")
    
    def on_item_activated(self, event):
        """Handle item selection/activation"""
        selection = self.tree.selection()
        if selection:
            item_id = selection[0]
            channel = next((c for c in self.filtered_channels if c["broadcaster_id"] == item_id), None)
            if channel:
                channel_name = channel["broadcaster_name"]
                self.copy_to_clipboard(channel_name)
                # Show feedback and exit
                messagebox.showinfo("Success", f"Copied @{channel_name} to clipboard!")
                self.root.destroy()  # Close the app
    
    def on_search_activated(self, event):
        """Handle Enter key in search box"""
        if self.filtered_channels:
            channel_name = self.filtered_channels[0]["broadcaster_name"]
            self.copy_to_clipboard(channel_name)
            # Show feedback and exit
            messagebox.showinfo("Success", f"Copied @{channel_name} to clipboard!")
            self.root.destroy()  # Close the app
    
    def copy_to_clipboard(self, channel_name):
        """Copy channel name to clipboard with @ prefix"""
        # Make sure we start with a clean text
        text = "@" + channel_name.strip()
        logger.info(f"Attempting to copy to clipboard: {text}")
        
        # First try pyperclip (most reliable)
        if CLIPBOARD_AVAILABLE:
            try:
                pyperclip.copy(text)
                logger.info(f"Successfully copied using pyperclip: {text}")
                self.status_var.set(f"Copied to clipboard: {text}")
                return True
            except Exception as e:
                logger.error(f"Error using pyperclip: {e}")
        
        # Fallback to tkinter clipboard
        try:
            # Clear clipboard first
            self.root.clipboard_clear()
            # Small delay to make sure clear completes
            self.root.after(50)
            # Set new content
            self.root.clipboard_append(text)
            # Make sure content stays after app closes
            self.root.update()
            logger.info(f"Successfully copied using tkinter clipboard: {text}")
            self.status_var.set(f"Copied to clipboard: {text}")
            return True
        except Exception as e:
            logger.error(f"Error using tkinter clipboard: {e}")
            
        # Last resort - show manual copy dialog
        result = messagebox.askyesno("Clipboard Error", 
                               f"Could not copy automatically. Please copy manually:\n\n{text}\n\nDid you copy the text?")
        return result

# Simple test function to verify clipboard works
def test_clipboard():
    """Test if clipboard functionality works"""
    test_text = "@TestChannel"
    
    print("Testing clipboard...")
    
    # Test pyperclip
    try:
        import pyperclip
        pyperclip.copy(test_text)
        result = pyperclip.paste()
        if result == test_text:
            print("Pyperclip test: SUCCESS")
        else:
            print(f"Pyperclip test: FAIL (got '{result}' instead of '{test_text}')")
    except Exception as e:
        print(f"Pyperclip test: ERROR - {e}")
    
    # Test tkinter
    try:
        root = tk.Tk()
        root.withdraw()  # Hide window
        
        # Clear and set
        root.clipboard_clear()
        root.clipboard_append(test_text)
        root.update()  # Need to update to apply clipboard changes
        
        # Try to get content back
        result = root.clipboard_get()
        if result == test_text:
            print("Tkinter clipboard test: SUCCESS")
        else:
            print(f"Tkinter clipboard test: FAIL (got '{result}' instead of '{test_text}')")
        
        root.destroy()
    except Exception as e:
        print(f"Tkinter clipboard test: ERROR - {e}")

def main():
    # Run clipboard test if requested
    if len(sys.argv) > 1 and sys.argv[1] == "--test-clipboard":
        test_clipboard()
        return
        
    # Create and run the app
    root = tk.Tk()
    app = TwitchChannelSearchApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
