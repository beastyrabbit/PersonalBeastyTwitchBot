import json
import logging
import os
import threading
import time
import uuid

import gi
import pyperclip
import requests
from io import BytesIO
from PIL import Image
from thefuzz import process

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio
from module.message_utils import send_admin_message_to_redis, send_message_to_redis
from module.shared_redis import redis_client

# Constants
TWITCH_BUTTON_CSS = """
    .twitch-button {
        color: #6441a5;
        font-weight: bold;
        border-radius: 6px;
        padding: 4px 8px;
        border: none;
    }
    .twitch-button:hover {
        background-color: #a970ff;
    }
"""
DEFAULT_WINDOW_WIDTH = 400
DEFAULT_WINDOW_HEIGHT = 600
REDIS_CHANNEL_ANNOUNCEMENT = 'twitch.chat.announcement'
REDIS_CHANNEL_SHOUTOUT = 'twitch.chat.shoutout'
REDIS_CHANNEL_SHOUTOUT_COMMAND = 'twitch.command.shoutout'
REDIS_REQUEST_STREAM = 'request_stream'
REDIS_RESPONSE_STREAM_PREFIX = 'response_stream:'

# Configure logger - use INFO level for better debugging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TwitchChannelSearchApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.example.twitchsearch")
        self.connect("activate", self.on_activate)
        self.channels = []
        self.filtered_channels = []
        self.channel_icons = {}
        self.search_index = {}  # For faster searching
        self.debounce_timer = None
        self.icon_lock = threading.Lock()  # Lock for icons

        # Create CSS provider for Twitch-style buttons
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data(TWITCH_BUTTON_CSS.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_activate(self, app):
        # Activate Dark Mode
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        # Create window
        self.win = Gtk.ApplicationWindow(application=app, title="Twitch Channel Search")
        self.win.set_default_size(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Main layout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.win.set_child(box)

        # Search entry expands to fill available space
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search channels...")
        self.search_entry.set_hexpand(True)  # Expand horizontally
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_search_activated)
        box.append(self.search_entry)

        # Remaining UI elements
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        box.append(scrolled)

        self.model = Gio.ListStore(item_type=Gtk.StringObject)
        self.list_view = Gtk.ListView.new(Gtk.NoSelection(), self.create_list_factory())
        self.list_view.set_model(Gtk.SingleSelection.new(self.model))
        self.list_view.connect("activate", self.on_item_activated)
        scrolled.set_child(self.list_view)

        self.load_channels()
        self.win.present()

    def create_list_factory(self):
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup)
        factory.connect("bind", self._on_factory_bind)
        factory.connect("unbind", self._on_factory_unbind)
        return factory

    def _on_factory_setup(self, factory, list_item):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_start(10)
        box.set_margin_end(10)
        box.set_margin_top(5)
        box.set_margin_bottom(5)

        image = Gtk.Image()
        image.set_size_request(40, 40)
        image.set_from_icon_name("user-info-symbolic")  # Default icon
        box.append(image)

        label = Gtk.Label()
        label.set_xalign(0)
        label.set_hexpand(True)
        box.append(label)

        # Add a shoutout button for each item
        button = Gtk.Button(label="SO", css_classes=["twitch-button"])
        button.set_margin_start(5)
        box.append(button)

        list_item.set_child(box)
        # Store the loading state to prevent multiple loads
        list_item.loading_icon = False

    def _on_factory_unbind(self, factory, list_item):
        # Reset loading state when item is unbound
        list_item.loading_icon = False

    def _on_factory_bind(self, factory, list_item):
        box = list_item.get_child()
        image = box.get_first_child()
        label = image.get_next_sibling()
        button = label.get_next_sibling()

        channel_id = list_item.get_item().get_string()
        channel = next((c for c in self.filtered_channels if c["broadcaster_id"] == channel_id), None)

        if channel:
            label.set_text(channel["broadcaster_name"])

            # Connect button to shoutout handler
            button.connect("clicked", self.on_shoutout_button_clicked, channel["broadcaster_name"])

            # Set default icon first
            image.set_from_icon_name("user-info-symbolic")

            # Check if we already have the icon cached (using lock)
            with self.icon_lock:
                if channel_id in self.channel_icons:
                    image.set_from_paintable(self.channel_icons[channel_id])
                    return

            # Only start loading if we haven't already started for this item
            is_loading = getattr(list_item, "loading_icon", False)
            if not is_loading:
                list_item.loading_icon = True
                profile_url = channel.get("profile_image_url")
                if profile_url:
                    logger.info("Loading icon for channel %s from %s", channel_id, profile_url)
                    # Load icon in a separate thread
                    threading.Thread(
                        target=self.load_channel_icon_threaded,
                        args=(channel_id, profile_url),
                        daemon=True
                    ).start()

    def load_channel_icon_threaded(self, channel_id, url):
        try:
            response = requests.get(url)
            if response.status_code == 200:
                # Process image
                img = Image.open(BytesIO(response.content))
                img = img.resize((40, 40))

                # Convert PIL Image to bytes
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                bytes_data = buffer.getvalue()

                # Update UI in the main thread
                GLib.idle_add(self.update_channel_icon, channel_id, bytes_data)
            else:
                logger.error("Error loading icon for %s: HTTP %s", channel_id, response.status_code)
        except Exception as e:
            logger.error("Exception loading icon for %s: %s", channel_id, e)

    def update_channel_icon(self, channel_id, bytes_data):
        try:
            # Create a Gdk texture
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(bytes_data))
            with self.icon_lock:
                self.channel_icons[channel_id] = texture
            logger.info("Icon for channel %s updated", channel_id)
            # Update visible items
            self.refresh_visible_items()
        except Exception as e:
            logger.error("Error updating icon for %s: %s", channel_id, e)
        return False

    def refresh_visible_items(self):
        """
        Refresh the visible items in the list view.
        This is needed after updating icons to ensure they are displayed correctly.
        """
        model = self.list_view.get_model()
        self.list_view.set_model(None)
        self.list_view.set_model(model)

    def load_channels(self):
        """
        Load channel data from the JSON file.

        This method:
        1. Loads the channel data from the JSON file
        2. Builds the search index
        3. Shows the initial channels in the list view
        """
        try:
            # Get the full path to the JSON file
            json_path = os.path.join(os.path.dirname(__file__), "followed_channels.json")

            # Check if the file exists
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    self.channels = json.load(f)
                logger.info("Loaded channels: %d from %s", len(self.channels), json_path)
                logger.debug("JSON file content: %s", self.channels)

                # Build search index for faster matching
                self.build_search_index()

                # Show initial channels (first 10 items)
                self.filtered_channels = self.channels[:10]
                self.update_list_view()
            else:
                logger.warning("No channel data found. File %s does not exist.", json_path)
                logger.info("Please ensure that the 'followed_channels.json' file exists in the same directory as the script.")
                logger.info("Run the fetch script if necessary to collect the data.")
        except json.JSONDecodeError as e:
            logger.error("Error parsing JSON file: %s", e)
        except Exception as e:
            logger.error("General error loading channels: %s", e)

    def build_search_index(self):
        """
        Build a search index for faster matching.

        Creates a simple list with just the broadcaster names in lowercase
        for efficient fuzzy searching.
        """
        self.search_index = []
        for channel in self.channels:
            name = channel["broadcaster_name"].lower()
            self.search_index.append(name)


    def on_search_changed(self, entry):
        """
        Handle search entry text changes.

        Uses a debounce timer to avoid performing searches on every keystroke.

        Args:
            entry: The search entry widget
        """
        # Cancel previous timer if it exists
        if self.debounce_timer:
            GLib.source_remove(self.debounce_timer)

        # Set a new timer to delay the search (150ms)
        self.debounce_timer = GLib.timeout_add(150, self.perform_search)

    def perform_search(self):
        """
        Perform the actual search operation.

        Uses fuzzy matching to find channels that match the search query.

        Returns:
            bool: Always False to stop the GLib timeout callback
        """
        query = self.search_entry.get_text().lower()
        self.debounce_timer = None

        if not query:
            # Show first 10 channels if no query
            self.filtered_channels = self.channels[:10]
        else:
            # Use fuzzy matching to find channels
            proc_result = process.extract(query, self.search_index, limit=10)
            self.filtered_channels = []
            for result_name in proc_result:
                # Find the channel with the matching name
                channel = next((c for c in self.channels if c["broadcaster_name"].lower() == result_name[0]), None)
                if channel:
                    self.filtered_channels.append(channel)

        self.update_list_view()
        return False

    def update_list_view(self):
        """
        Update the list view with the filtered channels.

        Clears the current list and adds the filtered channels.
        """
        self.model.remove_all()
        for channel in self.filtered_channels:
            self.model.append(Gtk.StringObject.new(channel["broadcaster_id"]))

    def on_item_activated(self, list_view, position):
        """Handle list item activation (selection)."""
        channel = self.filtered_channels[position]
        self.copy_to_clipboard(channel["broadcaster_name"])
        logger.info("Copied to clipboard: %s", channel['broadcaster_name'])
        self.quit()

    def on_search_activated(self, entry):
        """Handle search entry activation (Enter key)."""
        if self.filtered_channels:
            self.copy_to_clipboard(self.filtered_channels[0]["broadcaster_name"])
            logger.info("Copied to clipboard: %s", self.filtered_channels[0]['broadcaster_name'])
            self.quit()

    def copy_to_clipboard(self, text):
        """Copy text to clipboard with @ prefix."""
        text = "@" + text
        pyperclip.copy(text)


    def send_shoutout_command_to_redis(self, username):
        """Send a shoutout command to Redis in the format expected by shoutout.py."""
        message_obj = {
            "command": "so",
            "content": f"!so @{username}",
            "author": {
                "broadcaster": True,
                "mention": "@broadcaster"
            }
        }
        redis_client.publish(REDIS_CHANNEL_SHOUTOUT_COMMAND, json.dumps(message_obj))
        logger.info("Shoutout command sent for username: %s", username)


    def on_shoutout_button_clicked(self, button, channel_name):

        logger.info("Initiating shoutout for channel: %s", channel_name)

        # First copy the name to clipboard for convenience
        self.copy_to_clipboard(channel_name)

        # Send the shoutout command to Redis
        self.send_shoutout_command_to_redis(channel_name)

        # Close the application
        self.quit()

if __name__ == "__main__":
    app = TwitchChannelSearchApp()
    app.run(None)
