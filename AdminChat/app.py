import json
import signal
import sys
import time
import traceback
import uuid
from datetime import datetime

import base64
import requests
from io import BytesIO

import subprocess
import redis
import requests
from flask import Flask, render_template, Response, jsonify, request, make_response

app = Flask(__name__)

##########################
# Redis Configuration
##########################
REDIS_HOST = '192.168.50.115'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_EXPIRY = 60 * 60 * 48  # 48 hours in seconds
ALL_MESSAGES_KEY = 'twitch:messages:all'  # Main sorted set for all messages
CHAT_MESSAGES_KEY = 'twitch:messages:chat'  # Chat-specific messages
COMMANDS_KEY = 'twitch:messages:commands'  # Command-specific messages
ADMIN_COMMANDS_KEY = 'twitch:messages:admin'  # Admin-specific messages
MAX_MESSAGES = 10000  # Limit to prevent unbounded growth
# Add these near the top of your app with other config
class config:
    debug = True  # Set to False in production
    enableBTTV = True
    enable7TV = True


##########################
# Redis Initialization
##########################
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
pubsub = redis_client.pubsub()

# Subscribe to all message channels
pubsub.subscribe('twitch.chat.recieved')  # For normal chat
pubsub.psubscribe('twitch.command.*')  # For chat commands
pubsub.psubscribe('admin.*')  # For admin commands

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels before exiting")
    pubsub.unsubscribe()
    pubsub.punsubscribe('twitch.command.*')
    pubsub.punsubscribe('admin.*')
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Message Storage Functions
##########################
def get_recent_messages(key, count=100, start=0):
    """Get recent messages from Redis sorted set (newest first)"""
    try:
        messages = redis_client.zrevrange(key, start, start + count - 1)
        # Parse JSON strings back to dictionaries
        return [json.loads(msg.decode('utf-8')) for msg in messages]
    except Exception as e:
        print(f"Error fetching messages from {key}: {e}")
        return []

def get_messages_by_type(message_type, count=100, start=0):
    """Get messages of a specific type"""
    if isinstance(message_type, str):
        if "," in message_type:
            # Multiple types requested
            type_keys = [f"twitch:messages:{t}" for t in message_type.split(",")]
            # Create a temporary union of all requested sets
            temp_key = f"temp:union:{uuid.uuid4()}"
            try:
                # ZUNIONSTORE combines multiple sorted sets
                redis_client.zunionstore(temp_key, type_keys)
                # Get messages from the union
                messages = get_recent_messages(temp_key, count, start)
                # Clean up temporary key
                redis_client.delete(temp_key)
                return messages
            except Exception as e:
                print(f"Error creating union of message types: {e}")
                return []
        else:
            # Single type
            type_key = f"twitch:messages:{message_type}"
            return get_recent_messages(type_key, count, start)
    else:
        # For when a list is passed directly
        type_keys = [f"twitch:messages:{t}" for t in message_type]
        temp_key = f"temp:union:{uuid.uuid4()}"
        try:
            redis_client.zunionstore(temp_key, type_keys)
            messages = get_recent_messages(temp_key, count, start)
            redis_client.delete(temp_key)
            return messages
        except Exception as e:
            print(f"Error creating union of message types: {e}")
            return []

##########################
# API Endpoints
##########################
@app.route('/api/messages/recent', methods=['GET'])
def api_get_recent_messages():
    """API endpoint to get recent messages of any type"""
    count = int(request.args.get('count', 100, type=int))
    start = int(request.args.get('start', 0, type=int))
    message_type = request.args.get('type', None)

    if message_type:
        messages = get_messages_by_type(message_type, count, start)
    else:
        messages = get_recent_messages(ALL_MESSAGES_KEY, count, start)

    return jsonify(messages)


@app.route('/api/messages/delete', methods=['POST'])
def api_delete_old_messages():
    """API endpoint to delete old messages"""
    days = int(request.args.get('days', 30))

    # Calculate cutoff timestamp (current time - days in seconds)
    cutoff = time.time() - (days * 24 * 60 * 60)

    try:
        # Remove messages older than the cutoff from all sets
        count_all = redis_client.zremrangebyscore(ALL_MESSAGES_KEY, 0, cutoff)
        count_chat = redis_client.zremrangebyscore(CHAT_MESSAGES_KEY, 0, cutoff)
        count_commands = redis_client.zremrangebyscore(COMMANDS_KEY, 0, cutoff)
        count_admin = redis_client.zremrangebyscore(ADMIN_COMMANDS_KEY, 0, cutoff)

        return jsonify({
            "success": True,
            "deleted_counts": {
                "all": count_all,
                "chat": count_chat,
                "commands": count_commands,
                "admin": count_admin
            }
        })
    except Exception as e:
        print(f"Error deleting old messages: {e}")
        return jsonify({"error": str(e)}), 500

##########################
# EventSource Stream (Simplified)
##########################
@app.route('/stream')
def stream():
    """EventSource endpoint that notifies the client about new messages"""
    def event_stream():
        # Create a new pubsub connection for this request
        stream_pubsub = redis_client.pubsub()
        stream_pubsub.subscribe('twitch.chat.recieved')
        stream_pubsub.psubscribe('twitch.command.*')
        stream_pubsub.psubscribe('admin.*')

        try:
            # Send notification about initial data availability
            initial_notification = {
                "action": "init",
                "message": "Ready to stream events",
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(initial_notification)}\n\n"

            # Then stream notifications about new messages
            for message in stream_pubsub.listen():
                try:
                    print(message)
                    if message['type'] == 'message':
                        # Regular channel message
                        channel = message['channel'].decode('utf-8')
                        data = json.loads(message['data'])

                        # Create a notification with just enough info for filtering
                        notification = {
                            "action": "new_message",
                            "message_type": data.get('type', 'chat') if channel == 'twitch.chat.recieved' else 'unknown',
                            "source": data.get('source', 'twitch') if channel == 'twitch.chat.recieved' else 'system',
                            "timestamp": datetime.now().isoformat()
                        }

                        # Send notification to client
                        yield f"data: {json.dumps(notification)}\n\n"

                    elif message['type'] == 'pmessage':
                        # Pattern-matched message
                        channel = message['channel'].decode('utf-8')
                        pattern = message['pattern'].decode('utf-8')

                        # Determine message type based on channel
                        if 'twitch.command.' in channel:
                            message_type = 'command'
                            source = 'twitch'
                        elif 'admin.' in channel:
                            message_type = 'admin'
                            source = 'system'
                        else:
                            message_type = 'unknown'
                            source = 'unknown'

                        # Create a notification with just enough info for filtering
                        notification = {
                            "action": "new_message",
                            "message_type": message_type,
                            "source": source,
                            "channel": channel,  # Include the channel for more specific filtering
                            "timestamp": datetime.now().isoformat()
                        }

                        # Send notification to client
                        yield f"data: {json.dumps(notification)}\n\n"

                except Exception as e:
                    print(f"Error processing message in stream: {e}")
                    error_notification = {
                        "action": "error",
                        "message": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
                    yield f"data: {json.dumps(error_notification)}\n\n"

        except GeneratorExit:
            # Client disconnected
            stream_pubsub.unsubscribe()
            stream_pubsub.punsubscribe('twitch.command.*')
            stream_pubsub.punsubscribe('admin.*')
            print("[STREAM] Client disconnected, unsubscribed from channels")

    return Response(event_stream(), mimetype="text/event-stream")

##########################
# Main Routes
##########################
@app.route('/')
def index():
    return render_template('admin_panel.html')

@app.route('/chat/send-message', methods=['POST'])
def send_message():
    # Message is in json request body
    data = request.json
    message = data['message'] if data and 'message' in data else None
    if not message:
        return jsonify({"error": "Message is required"}), 400

    # Publish the message to the Redis channel
    redis_client.publish('twitch.chat.main.send', message)
    return jsonify({"success": True, "message": message})

##########################
# Redis Utility Routes
##########################
@app.route('/redis/get', methods=['GET'])
def get_redis_value():
    key = request.args.get('key')
    if not key:
        return jsonify({"error": "Key is required"}), 400

    value = redis_client.get(key)
    if value is None:
        return jsonify({"error": "Key not found"}), 404
    print(f"Value from redis: {value}")
    return jsonify({"value": value.decode('utf-8')})

@app.route('/redis/set', methods=['POST'])
def set_redis_value():
    data = request.json
    print(f"Data to store on redis: {data}")

    if not data or 'key' not in data or 'value' not in data:
        return jsonify({"error": "Key and value are required"}), 400

    key = data['key']
    value = data['value']
    expiry = data.get('expiry', REDIS_EXPIRY)  # Default 48 hours

    redis_client.setex(key, expiry, value)

    return jsonify({"success": True})

##########################
# Utility API Routes
##########################
@app.route('/api/nickname/<username>', methods=['GET'])
def get_nickname(username):
    print(f"Getting nickname for {username}")
    redis_key = f"nickname:{username}"
    cached_nickname = redis_client.get(redis_key)

    if cached_nickname:
        nickname = cached_nickname.decode('utf-8')
        print(f"[CACHE HIT] Nickname for {username} found in Redis: {nickname}")
        if nickname:  # Skip empty strings
            return jsonify({"nickname": nickname})
    else:
        print(f"[CACHE MISS] Nickname for {username} not found in Redis")

    # If not in cache, implement your nickname lookup logic here
    print(f"[EXTERNAL] Fetching nickname for {username} from external source")
    nickname = "Bob"  # Example placeholder

    # Store in Redis
    redis_client.setex(redis_key, REDIS_EXPIRY, nickname)
    print(f"[CACHE STORE] Stored nickname for {username} in Redis: {nickname}")

    return jsonify({"nickname": nickname})

@app.route('/api/clear_cache', methods=['GET'])
def clear_cache():
    """
    Clear all emote and command caches to force re-fetching from remote sources
    and immediately reload emotes from their respective sources
    """
    try:
        # Track counts of deleted keys
        cleared_counts = {
            'twitch_emotes': 0,
            'bttv_emotes': 0,
            'seventv_emotes': 0,
            'commands': 0,
            'emote_metadata': 0,
            'total': 0
        }

        reload_counts = {
            'bttv_global': 0,
            'bttv_channel': 0,
            'seventv_global': 0,
            'seventv_channel': 0,
            'seventv_unlisted': 0,
            'total': 0
        }

        # Clear Twitch emote caches
        twitch_keys = redis_client.keys('twitch:emote:*')
        if twitch_keys:
            cleared_counts['twitch_emotes'] = len(twitch_keys)
            cleared_counts['total'] += len(twitch_keys)
            redis_client.delete(*twitch_keys)
            app.logger.info(f"Cleared {len(twitch_keys)} Twitch emote cache entries")

        # Clear BTTV emote caches (global and channel)
        bttv_keys = redis_client.keys('bttv:*')
        if bttv_keys:
            cleared_counts['bttv_emotes'] = len(bttv_keys)
            cleared_counts['total'] += len(bttv_keys)
            redis_client.delete(*bttv_keys)
            app.logger.info(f"Cleared {len(bttv_keys)} BTTV emote cache entries (global and channel)")

        # Clear 7TV emote caches (global, channel, unlisted)
        seventv_keys = redis_client.keys('7tv:*')
        if seventv_keys:
            cleared_counts['seventv_emotes'] = len(seventv_keys)
            cleared_counts['total'] += len(seventv_keys)
            redis_client.delete(*seventv_keys)
            app.logger.info(f"Cleared {len(seventv_keys)} 7TV emote cache entries (global, channel, unlisted)")

        # Clear command caches
        command_keys = redis_client.keys('command:*')
        if command_keys:
            cleared_counts['commands'] = len(command_keys)
            cleared_counts['total'] += len(command_keys)
            redis_client.delete(*command_keys)
            app.logger.info(f"Cleared {len(command_keys)} command cache entries")

        # Clear generic emote metadata
        emote_keys = redis_client.keys('emote:*')
        if emote_keys:
            cleared_counts['emote_metadata'] = len(emote_keys)
            cleared_counts['total'] += len(emote_keys)
            redis_client.delete(*emote_keys)
            app.logger.info(f"Cleared {len(emote_keys)} emote metadata cache entries")

        # Now reload emotes from their respective sources
        channel_id = get_channel_id()
        channel_name = get_channel_name()

        # Reload BTTV global emotes
        if config.enableBTTV:
            try:
                bttv_global_url = "https://api.betterttv.net/3/cached/emotes/global"
                response = requests.get(bttv_global_url, timeout=5)
                if response.status_code == 200:
                    bttv_global_emotes = response.json()
                    if bttv_global_emotes:
                        redis_client.setex("bttv:global:emotes", REDIS_EXPIRY, json.dumps(bttv_global_emotes))
                        reload_counts['bttv_global'] = len(bttv_global_emotes)
                        reload_counts['total'] += len(bttv_global_emotes)
                        app.logger.info(f"Reloaded {len(bttv_global_emotes)} BTTV global emotes")
                else:
                    app.logger.error(f"Failed to reload BTTV global emotes: HTTP {response.status_code}")
            except Exception as e:
                app.logger.error(f"Error reloading BTTV global emotes: {e}")
                traceback.print_exc()

            # Reload BTTV channel emotes
            if channel_id:
                try:
                    bttv_channel_url = f"https://api.betterttv.net/3/cached/users/twitch/{channel_id}"
                    response = requests.get(bttv_channel_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        channel_emotes = data.get('channelEmotes', [])
                        shared_emotes = data.get('sharedEmotes', [])
                        all_channel_emotes = channel_emotes + shared_emotes

                        if all_channel_emotes:
                            redis_client.setex(f"bttv:channel:{channel_id}:emotes", REDIS_EXPIRY, json.dumps(all_channel_emotes))
                            reload_counts['bttv_channel'] = len(all_channel_emotes)
                            reload_counts['total'] += len(all_channel_emotes)
                            app.logger.info(f"Reloaded {len(all_channel_emotes)} BTTV channel emotes")
                    else:
                        app.logger.error(f"Failed to reload BTTV channel emotes: HTTP {response.status_code}")
                except Exception as e:
                    app.logger.error(f"Error reloading BTTV channel emotes: {e}")
                    traceback.print_exc()

        # Reload 7TV emotes if enabled
        if config.enable7TV:
            # Reload 7TV global emotes
            try:
                seventv_global_url = "https://7tv.io/v3/emote-sets/global"
                response = requests.get(seventv_global_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    emotes = data.get('emotes', [])
                    if emotes:
                        redis_client.setex("7tv:global:emotes:v3", REDIS_EXPIRY, json.dumps(emotes))
                        reload_counts['seventv_global'] = len(emotes)
                        reload_counts['total'] += len(emotes)
                        app.logger.info(f"Reloaded {len(emotes)} 7TV global emotes")
                else:
                    app.logger.error(f"Failed to reload 7TV global emotes: HTTP {response.status_code}")
            except Exception as e:
                app.logger.error(f"Error reloading 7TV global emotes: {e}")
                traceback.print_exc()

            # Reload 7TV channel emotes
            if channel_id or channel_name:
                try:
                    # Try with channel ID first
                    identifier = channel_id if channel_id else channel_name
                    seventv_channel_url = f"https://7tv.io/v3/users/twitch/{identifier}"
                    response = requests.get(seventv_channel_url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        # Extract the emote set ID
                        emote_set_id = data.get('emote_set', {}).get('id')

                        if emote_set_id:
                            # Now fetch the actual emotes
                            emote_set_url = f"https://7tv.io/v3/emote-sets/{emote_set_id}"
                            set_response = requests.get(emote_set_url, timeout=5)
                            if set_response.status_code == 200:
                                set_data = set_response.json()
                                channel_emotes = set_data.get('emotes', [])

                                if channel_emotes:
                                    redis_client.setex(f"7tv:channel:{identifier}:emotes:v3", REDIS_EXPIRY, json.dumps(channel_emotes))
                                    reload_counts['seventv_channel'] = len(channel_emotes)
                                    reload_counts['total'] += len(channel_emotes)
                                    app.logger.info(f"Reloaded {len(channel_emotes)} 7TV channel emotes")
                    else:
                        app.logger.error(f"Failed to reload 7TV channel emotes: HTTP {response.status_code}")
                except Exception as e:
                    app.logger.error(f"Error reloading 7TV channel emotes: {e}")
                    traceback.print_exc()

                # Reload 7TV unlisted emotes
                # This part depends on how your unlisted emotes are implemented
                # This is a placeholder - you'll need to adapt to your actual implementation
                try:
                    # This is assuming unlisted emotes are stored in a specific format
                    # You'll need to replace this with your actual logic for fetching unlisted emotes
                    unlisted_emotes = {}
                    # Example of populating unlisted_emotes dictionary...

                    if unlisted_emotes:
                        redis_client.setex(f"7tv:unlisted:{identifier}:emotes:v3", REDIS_EXPIRY, json.dumps(unlisted_emotes))
                        reload_counts['seventv_unlisted'] = len(unlisted_emotes)
                        reload_counts['total'] += len(unlisted_emotes)
                        app.logger.info(f"Reloaded {len(unlisted_emotes)} 7TV unlisted emotes")
                except Exception as e:
                    app.logger.error(f"Error reloading 7TV unlisted emotes: {e}")
                    traceback.print_exc()

        # Set cache refresh flags
        redis_client.set('cache:need_refresh:emotes', 'false', ex=3600)  # Set to false since we just refreshed
        redis_client.set('cache:last_cleared', datetime.now().isoformat())

        return jsonify({
            'success': True,
            'message': f"Successfully cleared {cleared_counts['total']} cache entries and reloaded {reload_counts['total']} emotes",
            'cleared_counts': cleared_counts,
            'reload_counts': reload_counts,
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        app.logger.error(f"Error clearing cache: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/twitch-emotes', methods=['POST'])
def process_twitch_emotes():
    """Process Twitch native emotes and fetch their image data"""
    try:
        data = request.json
        twitchEmotes = data.get('twitchEmotes', '')
        message = data.get('message', '')

        if config.debug:
            print(f"[TWITCH EMOTES] Processing Twitch emotes: {twitchEmotes}")

        if not twitchEmotes or not message:
            return jsonify({"emotes": []})

        emotePositions = []

        try:
            # Format: "emoteID:start-end,start-end/emoteID:start-end"
            emoteParts = twitchEmotes.split('/')

            for emotePart in emoteParts:
                if not emotePart or ':' not in emotePart:
                    continue

                emoteId, positions = emotePart.split(':')

                if not positions:
                    continue

                for position in positions.split(','):
                    if '-' not in position:
                        continue

                    start, end = map(int, position.split('-'))

                    # Get the actual emote text from the message
                    emote_text = message[start:end+1]

                    # Try to use cached emote data from Redis
                    cache_key = f"twitch:emote:{emoteId}:image"
                    mime_key = f"twitch:emote:{emoteId}:mime"
                    cached_image = redis_client.get(cache_key)

                    if cached_image:
                        # We already have the image data cached in Redis
                        if config.debug:
                            print(f"[CACHE HIT] Image data for Twitch emote {emoteId} found in Redis")
                        image_data_b64 = base64.b64encode(cached_image).decode('utf-8')

                        # Get the mime type from another key or default to png
                        mime_type = redis_client.get(mime_key)
                        mime_type = mime_type.decode('utf-8') if mime_type else 'image/png'
                    else:
                        # Determine URL based on emote ID
                        if config.debug:
                            print(f"[CACHE MISS] Fetching Twitch emote {emoteId} from CDN")

                        if emoteId.startswith('emotesv2_'):
                            url = f"https://static-cdn.jtvnw.net/emoticons/v2/{emoteId}/default/dark/3.0"
                        else:
                            url = f"https://static-cdn.jtvnw.net/emoticons/v1/{emoteId}/3.0"

                        # Fetch the image from URL
                        try:
                            response = requests.get(url, timeout=5)
                            if response.status_code == 200:
                                # Store raw binary data in Redis
                                image_data = response.content
                                mime_type = response.headers.get('Content-Type', 'image/png')

                                # Cache the raw binary data with expiry
                                redis_client.setex(cache_key, REDIS_EXPIRY, image_data)
                                redis_client.setex(mime_key, REDIS_EXPIRY, mime_type)

                                # Convert to base64 for JSON response
                                image_data_b64 = base64.b64encode(image_data).decode('utf-8')
                            else:
                                print(f"[ERROR] Failed to fetch Twitch emote {emoteId}: HTTP {response.status_code}")
                                continue
                        except Exception as e:
                            print(f"[ERROR] Exception fetching Twitch emote {emoteId}: {e}")
                            continue

                    # Add to emote positions with base64 data
                    emotePositions.append({
                        "id": emoteId,
                        "code": emote_text,
                        "start": start,
                        "end": end,
                        "type": "twitch",
                        "image_data_b64": image_data_b64,
                        "mime_type": mime_type
                    })

                    if config.debug:
                        print(f"[TWITCH EMOTE] Added: {emote_text} at {start}-{end}")

        except Exception as e:
            print(f"[ERROR] Error processing Twitch emotes: {e}")
            traceback.print_exc()

        return jsonify({"emotes": emotePositions})

    except Exception as e:
        print(f"[ERROR] Unexpected error in process_twitch_emotes: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e), "emotes": []}), 500


@app.route('/api/parse-message', methods=['POST'])
def parse_message():
    """Process a message for third-party emotes and commands"""
    try:
        data = request.json
        words = data.get('words', [])
        message = data.get('message', '')

        if config.debug:
            print(f"[PARSE MESSAGE] Processing message: '{message}'")
            print(f"[PARSE MESSAGE] Words to check: {words}")

        if not words or not message:
            return jsonify({"emotes": []})

        emotePositions = []
        wordPos = 0

        for i, word in enumerate(words):
            # Calculate the position in the original message
            start = message.find(word, wordPos)
            if start == -1:
                if config.debug:
                    print(f"[WARNING] Could not find word '{word}' in message")
                continue

            end = start + len(word) - 1
            wordPos = end + 1

            if config.debug:
                print(f"[WORD] Processing '{word}' at position {start}-{end}")

            # Check if this is a command pattern (starts with !)
            if word.startswith('!'):
                command_data = check_command(word)
                if command_data.get('found'):
                    # Check if we have cached image data for this command
                    command_image_key = f"command:{word}:image"
                    command_mime_key = f"command:{word}:mime"

                    cached_image = redis_client.get(command_image_key)

                    if cached_image:
                        # Use cached image data
                        if config.debug:
                            print(f"[CACHE HIT] Image data for command {word} found in Redis")
                        image_data_b64 = base64.b64encode(cached_image).decode('utf-8')
                        mime_type = redis_client.get(command_mime_key)
                        mime_type = mime_type.decode('utf-8') if mime_type else 'image/png'
                    else:
                        # Fetch command image
                        if config.debug:
                            print(f"[CACHE MISS] Fetching command {word} image from URL")

                        try:
                            # Get URL from command data
                            command_url = command_data.get('url')
                            if not command_url:
                                continue

                            # Fetch image
                            response = requests.get(command_url, timeout=5)
                            if response.status_code == 200:
                                # Store raw binary data in Redis
                                image_data = response.content
                                mime_type = response.headers.get('Content-Type', 'image/png')

                                # Cache with expiry
                                redis_client.setex(command_image_key, REDIS_EXPIRY, image_data)
                                redis_client.setex(command_mime_key, REDIS_EXPIRY, mime_type)

                                # Convert to base64 for JSON
                                image_data_b64 = base64.b64encode(image_data).decode('utf-8')
                            else:
                                print(f"[ERROR] Failed to fetch command image {word}: HTTP {response.status_code}")
                                continue
                        except Exception as e:
                            print(f"[ERROR] Exception fetching command image {word}: {e}")
                            continue

                    # Add to positions
                    emotePositions.append({
                        "id": command_data.get('id'),
                        "code": word,
                        "start": start,
                        "end": end,
                        "type": "command",
                        "animated": command_data.get('animated', False),
                        "image_data_b64": image_data_b64,
                        "mime_type": mime_type,
                        "extraClasses": ["command-icon"]
                    })

                    if config.debug:
                        print(f"[COMMAND] Added command: {word}")
                    continue

            # Check if this word is a BTTV or 7TV emote
            if config.enableBTTV or config.enable7TV:
                emote_data = check_emote(word)
                if emote_data.get('found'):
                    if config.debug:
                        print(f"[EMOTE] Found emote: {word} of type {emote_data.get('type')}")

                    # Check Redis for cached image data
                    emote_image_key = f"emote:{emote_data.get('type')}:{emote_data.get('id')}:image"
                    emote_mime_key = f"emote:{emote_data.get('type')}:{emote_data.get('id')}:mime"

                    cached_image = redis_client.get(emote_image_key)

                    if cached_image:
                        # Use cached image data
                        if config.debug:
                            print(f"[CACHE HIT] Image data for emote {word} found in Redis")
                        image_data_b64 = base64.b64encode(cached_image).decode('utf-8')
                        mime_type = redis_client.get(emote_mime_key)
                        mime_type = mime_type.decode('utf-8') if mime_type else 'image/png'
                    else:
                        # Determine URL based on emote type
                        if config.debug:
                            print(f"[CACHE MISS] Fetching emote {word} image from CDN")

                        emote_url = None

                        if emote_data.get('type') == 'bttv':
                            emote_url = f"https://cdn.betterttv.net/emote/{emote_data.get('id')}/3x"
                        elif emote_data.get('type') in ['7tv', '7tv-unlisted']:
                            if emote_data.get('files') and len(emote_data.get('files')) > 0:
                                emote_url = get_7tv_emote_url(emote_data.get('files'), '4x')
                            if not emote_url:
                                emote_url = f"https://cdn.7tv.app/emote/{emote_data.get('id')}/4x.webp"

                        if not emote_url:
                            continue

                        try:
                            # Fetch image
                            response = requests.get(emote_url, timeout=5)
                            if response.status_code == 200:
                                # Store raw binary data in Redis
                                image_data = response.content
                                mime_type = response.headers.get('Content-Type', 'image/webp' if '.webp' in emote_url else 'image/png')

                                # Cache with expiry
                                redis_client.setex(emote_image_key, REDIS_EXPIRY, image_data)
                                redis_client.setex(emote_mime_key, REDIS_EXPIRY, mime_type)

                                # Convert to base64 for JSON
                                image_data_b64 = base64.b64encode(image_data).decode('utf-8')
                            else:
                                print(f"[ERROR] Failed to fetch emote image {word}: HTTP {response.status_code}")
                                continue
                        except Exception as e:
                            print(f"[ERROR] Exception fetching emote image {word}: {e}")
                            continue

                    # Add to positions
                    emotePositions.append({
                        "id": emote_data.get('id'),
                        "code": word,
                        "start": start,
                        "end": end,
                        "type": emote_data.get('type'),
                        "animated": emote_data.get('animated', False),
                        "image_data_b64": image_data_b64,
                        "mime_type": mime_type
                    })

        if config.debug:
            print(f"[PARSE RESULT] Found {len(emotePositions)} emotes/commands in message")

        return jsonify({"emotes": emotePositions})

    except Exception as e:
        print(f"[ERROR] Unexpected error in parse_message: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e), "emotes": []}), 500

def get_7tv_emote_url(files, size):
    """Extract the appropriate URL from the 7TV files array based on size"""
    try:
        if not files or not isinstance(files, list):
            return None

        # Find the file with the requested size
        for file in files:
            if not isinstance(file, dict):
                continue

            if file.get('name') == size:
                file_id = file.get('id')
                if not file_id:
                    continue

                mime_type = file.get('mime', 'image/webp')
                file_extension = mime_type.split('/')[-1]
                return f"https://cdn.7tv.app/emote/{file_id}/{size}.{file_extension}"

        # If exact size not found, try a fallback
        fallback_sizes = ['4x', '3x', '2x', '1x']
        for fallback in fallback_sizes:
            if fallback == size:
                continue  # Skip the size we already checked

            for file in files:
                if not isinstance(file, dict):
                    continue

                if file.get('name') == fallback:
                    file_id = file.get('id')
                    if not file_id:
                        continue

                    mime_type = file.get('mime', 'image/webp')
                    file_extension = mime_type.split('/')[-1]
                    return f"https://cdn.7tv.app/emote/{file_id}/{fallback}.{file_extension}"

        # Last resort fallback - try to find any file
        if len(files) > 0 and isinstance(files[0], dict):
            file = files[0]
            file_id = file.get('id')
            file_name = file.get('name', '4x')
            mime_type = file.get('mime', 'image/webp')
            file_extension = mime_type.split('/')[-1]

            if file_id:
                return f"https://cdn.7tv.app/emote/{file_id}/{file_name}.{file_extension}"

        return None
    except Exception as e:
        print(f"[ERROR] Error in get_7tv_emote_url: {e}")
        traceback.print_exc()
        return None
def check_command(word):
    """Check if a word is a valid command and return its data"""
    try:
        if not word or not word.startswith('!'):
            return {"found": False}

        if config.debug:
            print(f"[COMMAND CHECK] Checking if '{word}' is a command")

        # First check if command data is cached
        command_key = f"command:{word}:data"
        cached_command = redis_client.get(command_key)

        if cached_command:
            if config.debug:
                print(f"[CACHE HIT] Command data for '{word}' found in Redis")
            return json.loads(cached_command)

        # If not in cache, check if we have a local API endpoint for commands
        try:
            # Start with an internal request to avoid HTTP overhead
            # This internal request format will depend on your application structure
            # For example, you might have a database lookup function

            # Here I'll use a direct HTTP request to your existing API as a fallback
            api_url = f"{request.host_url.rstrip('/')}/api/command/{word}"

            if config.debug:
                print(f"[API REQUEST] Requesting command data from {api_url}")

            response = requests.get(api_url, timeout=2)

            if response.status_code == 200:
                command_data = response.json()

                if command_data.get('found'):
                    # Cache the result with expiry
                    redis_client.setex(command_key, REDIS_EXPIRY, json.dumps(command_data))

                    if config.debug:
                        print(f"[COMMAND FOUND] Command '{word}' found and cached")

                    return command_data
                else:
                    if config.debug:
                        print(f"[COMMAND NOT FOUND] Command '{word}' returned not found from API")

                    # Cache negative result to avoid repeated requests
                    redis_client.setex(command_key, 60 * 5, json.dumps({"found": False}))  # 5 min for negative cache
                    return {"found": False}
            else:
                print(f"[API ERROR] Command request failed with status {response.status_code}")
                return {"found": False}
        except Exception as e:
            print(f"[ERROR] Error requesting command data for '{word}': {e}")
            traceback.print_exc()
            return {"found": False}
    except Exception as e:
        print(f"[ERROR] Unexpected error in check_command: {e}")
        traceback.print_exc()
        return {"found": False}

def check_emote(word):
    """Check if a word is a valid emote and return its data"""
    try:
        if not word or len(word) < 2:  # Basic validation
            return {"found": False}

        if config.debug:
            print(f"[EMOTE CHECK] Checking if '{word}' is an emote")

        # First check if it's already cached
        emote_key = f"emote:{word}:data"
        cached_emote = redis_client.get(emote_key)

        if cached_emote:
            if config.debug:
                print(f"[CACHE HIT] Emote data for '{word}' found in Redis")
            return json.loads(cached_emote)

        # If not cached, check all emote sources
        channel_id = get_channel_id()

        # 1. Check BTTV global emotes
        if config.enableBTTV:
            bttv_global_key = "bttv:global:emotes"
            bttv_global_emotes = redis_client.get(bttv_global_key)

            if bttv_global_emotes:
                try:
                    emotes = json.loads(bttv_global_emotes)
                    for emote in emotes:
                        if emote.get('code') == word:
                            emote_data = {
                                "found": True,
                                "id": emote.get('id'),
                                "type": "bttv",
                                "animated": emote.get('animated', False),
                                "imageType": emote.get('imageType'),
                                "source": "bttv:global:cache"
                            }
                            # Cache for future use
                            redis_client.setex(emote_key, REDIS_EXPIRY, json.dumps(emote_data))

                            if config.debug:
                                print(f"[EMOTE FOUND] '{word}' found in BTTV global emotes")

                            return emote_data
                except Exception as e:
                    print(f"[ERROR] Error parsing BTTV global emotes: {e}")

            # 2. Check BTTV channel emotes
            if channel_id:
                bttv_channel_key = f"bttv:channel:{channel_id}:emotes"
                bttv_channel_emotes = redis_client.get(bttv_channel_key)

                if bttv_channel_emotes:
                    try:
                        emotes = json.loads(bttv_channel_emotes)
                        for emote in emotes:
                            if emote.get('code') == word:
                                emote_data = {
                                    "found": True,
                                    "id": emote.get('id'),
                                    "type": "bttv",
                                    "animated": emote.get('animated', False),
                                    "imageType": emote.get('imageType'),
                                    "source": "bttv:channel:cache"
                                }
                                # Cache for future use
                                redis_client.setex(emote_key, REDIS_EXPIRY, json.dumps(emote_data))

                                if config.debug:
                                    print(f"[EMOTE FOUND] '{word}' found in BTTV channel emotes")

                                return emote_data
                    except Exception as e:
                        print(f"[ERROR] Error parsing BTTV channel emotes: {e}")

        # 3. Check 7TV global emotes
        if config.enable7TV:
            seventv_global_key = "7tv:global:emotes:v3"
            seventv_global_emotes = redis_client.get(seventv_global_key)

            if seventv_global_emotes:
                try:
                    emotes = json.loads(seventv_global_emotes)
                    for emote in emotes:
                        if emote.get('code') == word or emote.get('name') == word:
                            emote_data = {
                                "found": True,
                                "id": emote.get('id'),
                                "type": "7tv",
                                "animated": emote.get('animated', False),
                                "files": emote.get('files', []),
                                "source": "7tv:global:cache"
                            }
                            # Cache for future use
                            redis_client.setex(emote_key, REDIS_EXPIRY, json.dumps(emote_data))

                            if config.debug:
                                print(f"[EMOTE FOUND] '{word}' found in 7TV global emotes")

                            return emote_data
                except Exception as e:
                    print(f"[ERROR] Error parsing 7TV global emotes: {e}")

            # 4. Check 7TV channel emotes
            if channel_id:
                seventv_channel_key = f"7tv:channel:{channel_id}:emotes:v3"
                seventv_channel_emotes = redis_client.get(seventv_channel_key)

                if seventv_channel_emotes:
                    try:
                        emotes = json.loads(seventv_channel_emotes)
                        for emote in emotes:
                            if emote.get('code') == word or emote.get('name') == word:
                                emote_data = {
                                    "found": True,
                                    "id": emote.get('id'),
                                    "type": "7tv",
                                    "animated": emote.get('animated', False),
                                    "files": emote.get('files', []),
                                    "source": "7tv:channel:cache"
                                }
                                # Cache for future use
                                redis_client.setex(emote_key, REDIS_EXPIRY, json.dumps(emote_data))

                                if config.debug:
                                    print(f"[EMOTE FOUND] '{word}' found in 7TV channel emotes")

                                return emote_data
                    except Exception as e:
                        print(f"[ERROR] Error parsing 7TV channel emotes: {e}")

            # 5. Check 7TV unlisted emotes
            if channel_id:
                seventv_unlisted_key = f"7tv:unlisted:{channel_id}:emotes:v3"
                seventv_unlisted_emotes = redis_client.get(seventv_unlisted_key)

                if seventv_unlisted_emotes:
                    try:
                        emotes = json.loads(seventv_unlisted_emotes)
                        if word in emotes:
                            emote = emotes[word]
                            emote_data = {
                                "found": True,
                                "id": emote.get('id'),
                                "type": "7tv-unlisted",
                                "animated": emote.get('animated', False),
                                "files": emote.get('files', []),
                                "source": "7tv:unlisted:cache"
                            }
                            # Cache for future use
                            redis_client.setex(emote_key, REDIS_EXPIRY, json.dumps(emote_data))

                            if config.debug:
                                print(f"[EMOTE FOUND] '{word}' found in 7TV unlisted emotes")

                            return emote_data
                    except Exception as e:
                        print(f"[ERROR] Error parsing 7TV unlisted emotes: {e}")

        # If emote not found in any source, try to reload emote data
        if config.debug:
            print(f"[EMOTE NOT FOUND] '{word}' not found in any emote source")

        # Cache negative result briefly to prevent constant checking
        redis_client.setex(emote_key, 60 * 5, json.dumps({"found": False}))  # 5 min for negative cache

        return {"found": False}
    except Exception as e:
        print(f"[ERROR] Unexpected error in check_emote: {e}")
        traceback.print_exc()
        return {"found": False}


# Helper Functions for Emote Loading
def get_channel_id():
    # Here you would get the channel ID from wherever you're storing it
    # This is just a placeholder
    return "29319793"


def get_channel_name():
    # Here you would get the channel name from wherever you're storing it
    # This is just a placeholder
    return "beastyrabbit"

if __name__ == '__main__':
    # Load emotes on startup
    print("Loading emotes on startup...")
    url = "http://localhost:5001"
    chrome_path = "chromium"  # or "google-chrome" / full path to binary
    # Minimal app mode (no browser UI)
    #subprocess.Popen([chrome_path, "--app=" + url])

    app.run(debug=False, host="0.0.0.0", port=5001)
