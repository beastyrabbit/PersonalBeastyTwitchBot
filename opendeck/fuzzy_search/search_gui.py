import json
import logging
import os
import threading
import time
import uuid

import gi
import pyperclip

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio
from module.message_utils import send_admin_message_to_redis, send_message_to_redis
from module.shared_redis import redis_client
import requests
from io import BytesIO
from PIL import Image
from thefuzz import process

# Logger konfigurieren - use INFO level for better debugging
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
        self.icon_lock = threading.Lock()  # Lock für Icons
        
        # Create CSS provider for Twitch-style buttons
        self.css_provider = Gtk.CssProvider()
        self.css_provider.load_from_data("""
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
        """.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            self.css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_activate(self, app):
        # Dark Mode aktivieren
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)

        # Fenster erstellen
        self.win = Gtk.ApplicationWindow(application=app, title="Twitch Channel Search")
        self.win.set_default_size(400, 600)

        # Hauptlayout
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.win.set_child(box)

        # Search entry expands to fill available space
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search channels...")
        self.search_entry.set_hexpand(True)  # Expand horizontally
        self.search_entry.connect("search-changed", self.on_search_changed)
        self.search_entry.connect("activate", self.on_search_activated)
        box.append(self.search_entry)
        
        # Restliche UI-Elemente
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

        # Add a copy button for each item
        button = Gtk.Button(label="", css_classes=["twitch-button"])
        button.set_margin_start(5)
        box.append(button)
    
        list_item.set_child(box)
        # Store the loading state to prevent multiple loads
        list_item.loading_icon = False

    def _on_factory_unbind(self, factory, list_item):
        # Reset loading state when item is unbind
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
            
            # Connect button to copy handler
            button.connect("clicked", self.on_copy_button_clicked, channel["broadcaster_name"])

            # Set default icon first
            image.set_from_icon_name("user-info-symbolic")

            # Check if we already have the icon cached (Lock verwenden)
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
                    logger.info("Lade Icon für Channel %s von %s", channel_id, profile_url)
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
                logger.error("Fehler beim Laden des Icons für %s: HTTP %s", channel_id, response.status_code)
        except Exception as e:
            logger.error("Exception beim Laden des Icons für %s: %s", channel_id, e)

    def update_channel_icon(self, channel_id, bytes_data):
        try:
            # Create a Gdk texture
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(bytes_data))
            with self.icon_lock:
                self.channel_icons[channel_id] = texture
            logger.info("Icon für Channel %s aktualisiert", channel_id)
            # Update visible items
            self.refresh_visible_items()
        except Exception as e:
            logger.error("Fehler beim Aktualisieren des Icons für %s: %s", channel_id, e)
        return False

    def refresh_visible_items(self):
        model = self.list_view.get_model()
        self.list_view.set_model(None)
        self.list_view.set_model(model)


    def load_channels(self):
        try:
            # Get the full path to the JSON file
            json_path = os.path.join(os.path.dirname(__file__), "followed_channels.json")

            # Check if the file exists
            if os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    self.channels = json.load(f)
                logger.info(f"Geladene Channels: {len(self.channels)} von {json_path}")
                logger.debug(f"Inhalt der JSON-Datei: {self.channels}")

                # Build search index for faster matching
                self.build_search_index()

                # Show initial channels (first 10 items)
                self.filtered_channels = self.channels[:10]
                self.update_list_view()
            else:
                logger.warning(f"Keine Channels-Daten gefunden. Datei {json_path} nicht vorhanden.")
                logger.info("Bitte stellen Sie sicher, dass die Datei 'followed_channels.json' im gleichen Verzeichnis wie das Script existiert.")
                logger.info("Führen Sie gegebenenfalls das Fetch-Script aus, um die Daten zu sammeln.")
        except json.JSONDecodeError as e:
            logger.error(f"Fehler beim Parsen der JSON-Datei: {e}")
        except Exception as e:
            logger.error(f"Allg. Fehler beim Laden der Channels: {e}")


    def build_search_index(self):
        # Create a simple list only with the broadcaster names
        self.search_index = []
        for channel in self.channels:
            name = channel["broadcaster_name"].lower()
            self.search_index.append(name)


    def on_search_changed(self, entry):
        # Cancel previous timer if it exists
        if self.debounce_timer:
            GLib.source_remove(self.debounce_timer)

        # Set a new timer to delay the search
        self.debounce_timer = GLib.timeout_add(150, self.perform_search)

    def perform_search(self):
        query = self.search_entry.get_text().lower()
        self.debounce_timer = None

        if not query:
            self.filtered_channels = self.channels[:10]
        else:
            proc_result = process.extract(query, self.search_index, limit=10)
            self.filtered_channels = []
            for result_name in proc_result:
                # We need to find the correct entry in self.channels that has the same name
                # add it to the filtered_channels
                channel = next((c for c in self.channels if c["broadcaster_name"].lower() == result_name[0]), None)
                # Append the corresponding channel to filtered_channels
                self.filtered_channels.append(channel)
        self.update_list_view()
        return False

    def update_list_view(self):
        self.model.remove_all()
        for channel in self.filtered_channels:
            self.model.append(Gtk.StringObject.new(channel["broadcaster_id"]))

    def on_item_activated(self, list_view, position):
        channel = self.filtered_channels[position]
        self.copy_to_clipboard(channel["broadcaster_name"])
        logger.info("In die Zwischenablage kopiert: %s", channel['broadcaster_name'])
        self.quit()

    def on_search_activated(self, entry):
        if self.filtered_channels:
            self.copy_to_clipboard(self.filtered_channels[0]["broadcaster_name"])
            logger.info("In die Zwischenablage kopiert: %s", self.filtered_channels[0]['broadcaster_name'])
            self.quit()

    def copy_to_clipboard(self, text):
        text = "@"+text
        pyperclip.copy(text)
        #clipboard = Gdk.Display.get_default().get_clipboard()
        #clipboard.set_text(text)

    def send_announcement_to_redis(self, send_message):
        # Convert to JSON string if message is not already a string
        if not isinstance(send_message, str):
            send_message = json.dumps(send_message)
        redis_client.publish('twitch.chat.announcement', send_message)
        logger.info(f"Announcement sent: {send_message}")

    def send_shoutout_to_redis(self, send_message):
        redis_client.publish('twitch.chat.shoutout', send_message)
        logger.info(f"Shoutout sent: {send_message}")

    def fetch_user_stream_data(self, username):
        """Fetch user and stream data from Redis using the same logic as in shoutout.py"""
        username = username.lower()

        # Get user data from Redis
        request_id = str(uuid.uuid4())
        response_stream = f"response_stream:{request_id}"
        redis_client.xadd("request_stream", {"request_id": request_id, "username": username, "type": "fetch_user"})
        response = redis_client.xread({response_stream: "$"}, count=1, block=5000)  # 5s timeout

        if not response:
            logger.error("No user data response received for user: %s", username)
            return None, None

        user_data = response[0][1][0][1][b'user_data'].decode()
        user_data = json.loads(user_data)
        logger.info("Got user data response for: %s", username)

        if not user_data:
            logger.error("User not found: %s", username)
            return None, None

        user_id = user_data["data"]["user_id"]

        # Get stream data from Redis
        request_id = str(uuid.uuid4())
        response_stream = f"response_stream:{request_id}"
        redis_client.xadd("request_stream", {"request_id": request_id, "user_id": user_id, "type": "fetch_channels"})
        response = redis_client.xread({response_stream: "$"}, count=1, block=5000)  # 5s timeout

        if not response:
            logger.error("No stream data response received for user: %s", username)
            return user_id, None

        streams = response[0][1][0][1][b'channel_data'].decode()
        streams = json.loads(streams)

        return user_id, streams

    def send_announcement_to_redis(self, send_message):
        redis_client.publish('twitch.chat.announcement', send_message)
        logger.info(f"Announcement sent: {send_message}")
    
    def send_shoutout_to_redis(self, user_id):
        # Send just the user_id for shoutout
        redis_client.publish('twitch.chat.shoutout', user_id)
        logger.info(f"Shoutout sent for user ID: {user_id}")
        
    def fetch_user_stream_data(self, username):
        """Fetch user and stream data from Redis using the same logic as in shoutout.py"""
        try:
            username = username.lower().strip()
            logger.info("Fetching data for user: %s", username)
            
            # Get user data from Redis
            request_id = str(uuid.uuid4())
            response_stream = f"response_stream:{request_id}"
            
            # Add logging to track the request
            logger.info("Sending fetch_user request: ID=%s, username=%s", request_id, username)
            
            # Send request to Redis stream
            redis_client.xadd("request_stream", {"request_id": request_id, "username": username, "type": "fetch_user"})
            
            # Wait for response with timeout
            response = redis_client.xread({response_stream: "$"}, count=1, block=8000)  # 8s timeout for better reliability
            
            if not response or len(response) == 0 or len(response[0][1]) == 0:
                logger.error("No user data response received for user: %s (empty response)", username)
                # Try direct API fallback or clipboard-only mode
                return None, None
                
            # Debug response format
            logger.info("Response structure: %s", str(response[0][1][0][1].keys()))
            
            if b'user_data' not in response[0][1][0][1]:
                logger.error("Invalid user data response format for user: %s", username)
                return None, None
                
            user_data = response[0][1][0][1][b'user_data'].decode('utf-8')
            user_data = json.loads(user_data)
            
            if not user_data or "data" not in user_data or "user_id" not in user_data["data"]:
                logger.error("Invalid user data content for user: %s - %s", username, str(user_data))
                return None, None
                
            user_id = user_data["data"]["user_id"]
            logger.info("Got user_id=%s for username=%s", user_id, username)
            
            # Get stream data from Redis
            request_id = str(uuid.uuid4())
            response_stream = f"response_stream:{request_id}"
            
            logger.info("Sending fetch_channels request: ID=%s, user_id=%s", request_id, user_id)
            redis_client.xadd("request_stream", {"request_id": request_id, "user_id": user_id, "type": "fetch_channels"})
            response = redis_client.xread({response_stream: "$"}, count=1, block=5000)  # 5s timeout
            
            if not response or len(response) == 0 or len(response[0][1]) == 0:
                logger.warning("No stream data response for user_id: %s", user_id)
                return user_id, None
                
            if b'channel_data' not in response[0][1][0][1]:
                logger.warning("Invalid channel data format for user_id: %s", user_id)
                return user_id, None
                
            streams = response[0][1][0][1][b'channel_data'].decode('utf-8')
            streams = json.loads(streams)
            
            return user_id, streams
            
        except Exception as e:
            logger.exception("Error in fetch_user_stream_data: %s", str(e))
            return None, None
    
    def on_shoutout_button_clicked(self, button):
        logger.info("Shoutout button clicked, closing application")
        self.quit()
    
    def on_copy_button_clicked(self, button, channel_name):
        logger.info("Initiating shoutout for channel: %s", channel_name)

        # First copy the name to clipboard for convenience
        self.copy_to_clipboard(channel_name)

        # Get user and stream data
        user_id, streams = self.fetch_user_stream_data(channel_name)

        if not user_id:
            logger.error("Could not get user_id for %s", channel_name)
            self.quit()
            return

        # If we have stream data, create a proper shoutout message
        if streams and "data" in streams:
            stream = streams["data"]
            game_name = stream.get("game_name", "Unknown Game")
            title = stream.get("title", "No Title")

            # Build twitch URL for the user
            twitch_url = f'https://www.twitch.tv/{channel_name}'

            # Create shoutout message with the same format as in shoutout.py
            shoutout_message = f'You should check out {channel_name} was last playing =>{game_name}<= with the title: {title}! 🐰🐻 at {twitch_url}'

            # Send to Redis
            self.send_announcement_to_redis(shoutout_message)
            self.send_shoutout_to_redis(user_id)

            # Send additional info with slight delay
            time.sleep(0.2)
            send_admin_message_to_redis(f"Game: {game_name}", command="shoutout")
            time.sleep(0.2)
            send_admin_message_to_redis(f"Title: {title}", command="shoutout")

            logger.info("Shoutout completed for: %s", channel_name)
        else:
            logger.warning("No stream data found for: %s, sending basic shoutout", channel_name)
            # Send a simpler shoutout if we don't have stream data
            twitch_url = f'https://www.twitch.tv/{channel_name}'
            shoutout_message = f'You should check out {channel_name}! 🐰🐻 at {twitch_url}'
            self.send_announcement_to_redis(shoutout_message)
            if user_id:
                self.send_shoutout_to_redis(user_id)

        # Close the application
        self.quit()

if __name__ == "__main__":
    app = TwitchChannelSearchApp()
    app.run(None)
