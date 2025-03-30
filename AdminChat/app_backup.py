import json
import signal
import sys
import time
import traceback
from datetime import datetime

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
def get_recent_messages(key=ALL_MESSAGES_KEY, count=100, start=0):
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
    type_key = f"twitch:messages:{message_type}"
    return get_recent_messages(type_key, count, start)

##########################
# API Endpoints
##########################
@app.route('/api/messages/recent', methods=['GET'])
def api_get_recent_messages():
    """API endpoint to get recent messages of any type"""
    count = int(request.args.get('count', 100))
    start = int(request.args.get('start', 0))
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



@app.route('/api/emote/<emote_code>', methods=['GET'])
def get_emote(emote_code):
    print(f"\n[EMOTE REQUEST] Looking up emote code: '{emote_code}'")
    channel_id = get_channel_id()
    print(f"[INFO] Channel ID for emote lookup: {channel_id}")

    # Check BTTV global emotes first
    print(f"[CACHE CHECK] Checking BTTV global emotes for '{emote_code}'")
    bttv_global_key = "bttv:global:emotes"
    bttv_global_emotes = redis_client.get(bttv_global_key)

    if bttv_global_emotes:
        print(f"[CACHE HIT] BTTV global emotes found in Redis")
        try:
            emotes = json.loads(bttv_global_emotes)
            for emote in emotes:
                if emote.get('code') == emote_code:
                    print(f"[MATCH FOUND] '{emote_code}' found in BTTV global emotes")
                    print(f"[EMOTE DETAILS] {json.dumps(emote, indent=2)}")
                    return jsonify({
                        "found": True,
                        "id": emote.get('id'),
                        "type": "bttv",
                        "animated": emote.get('animated', False),
                        "imageType": emote.get('imageType'),
                        "source": "bttv:global:cache"
                    })
        except Exception as e:
            print(f"[ERROR] Error parsing BTTV global emotes from Redis: {e}")
    else:
        print(f"[CACHE MISS] BTTV global emotes not found in Redis")

    # Check BTTV channel emotes
    if channel_id:
        print(f"[CACHE CHECK] Checking BTTV channel emotes for '{emote_code}'")
        bttv_channel_key = f"bttv:channel:{channel_id}:emotes"
        bttv_channel_emotes = redis_client.get(bttv_channel_key)

        if bttv_channel_emotes:
            print(f"[CACHE HIT] BTTV channel emotes found in Redis")
            try:
                emotes = json.loads(bttv_channel_emotes)
                for emote in emotes:
                    if emote.get('code') == emote_code:
                        print(f"[MATCH FOUND] '{emote_code}' found in BTTV channel emotes")
                        print(f"[EMOTE DETAILS] {json.dumps(emote, indent=2)}")
                        return jsonify({
                            "found": True,
                            "id": emote.get('id'),
                            "type": "bttv",
                            "animated": emote.get('animated', False),
                            "imageType": emote.get('imageType'),
                            "source": "bttv:channel:cache"
                        })
            except Exception as e:
                print(f"[ERROR] Error parsing BTTV channel emotes from Redis: {e}")
        else:
            print(f"[CACHE MISS] BTTV channel emotes not found in Redis")

    # Check 7TV global emotes
    print(f"[CACHE CHECK] Checking 7TV global emotes for '{emote_code}'")
    seventv_global_key = "7tv:global:emotes:v3"
    seventv_global_emotes = redis_client.get(seventv_global_key)

    if seventv_global_emotes:
        print(f"[CACHE HIT] 7TV global emotes found in Redis")
        try:
            emotes = json.loads(seventv_global_emotes)
            for emote in emotes:
                if emote.get('code') == emote_code:
                    print(f"[MATCH FOUND] '{emote_code}' found in 7TV global emotes")
                    print(f"[EMOTE DETAILS] {json.dumps(emote, indent=2)}")
                    return jsonify({
                        "found": True,
                        "id": emote.get('id'),
                        "type": "7tv",
                        "animated": emote.get('animated', False),
                        "files": emote.get('files', []),
                        "source": "7tv:global:cache"
                    })
        except Exception as e:
            print(f"[ERROR] Error parsing 7TV global emotes from Redis: {e}")
    else:
        print(f"[CACHE MISS] 7TV global emotes not found in Redis")

    # Check 7TV channel emotes
    if channel_id:
        print(f"[CACHE CHECK] Checking 7TV channel emotes for '{emote_code}'")
        seventv_channel_key = f"7tv:channel:{channel_id}:emotes:v3"
        seventv_channel_emotes = redis_client.get(seventv_channel_key)

        if seventv_channel_emotes:
            print(f"[CACHE HIT] 7TV channel emotes found in Redis")
            try:
                emotes = json.loads(seventv_channel_emotes)
                for emote in emotes:
                    if emote.get('code') == emote_code:
                        print(f"[MATCH FOUND] '{emote_code}' found in 7TV channel emotes")
                        print(f"[EMOTE DETAILS] {json.dumps(emote, indent=2)}")
                        return jsonify({
                            "found": True,
                            "id": emote.get('id'),
                            "type": "7tv",
                            "animated": emote.get('animated', False),
                            "files": emote.get('files', []),
                            "source": "7tv:channel:cache"
                        })
            except Exception as e:
                print(f"[ERROR] Error parsing 7TV channel emotes from Redis: {e}")
        else:
            print(f"[CACHE MISS] 7TV channel emotes not found in Redis")

    # Check 7TV unlisted emotes
    if channel_id:
        print(f"[CACHE CHECK] Checking 7TV unlisted emotes for '{emote_code}'")
        seventv_unlisted_key = f"7tv:unlisted:{channel_id}:emotes:v3"
        seventv_unlisted_emotes = redis_client.get(seventv_unlisted_key)

        if seventv_unlisted_emotes:
            print(f"[CACHE HIT] 7TV unlisted emotes found in Redis")
            try:
                emotes = json.loads(seventv_unlisted_emotes)
                if emote_code in emotes:
                    emote = emotes[emote_code]
                    print(f"[MATCH FOUND] '{emote_code}' found in 7TV unlisted emotes")
                    print(f"[EMOTE DETAILS] {json.dumps(emote, indent=2)}")
                    return jsonify({
                        "found": True,
                        "id": emote.get('id'),
                        "type": "7tv-unlisted",
                        "animated": emote.get('animated', False),
                        "files": emote.get('files', []),
                        "source": "7tv:unlisted:cache"
                    })
            except Exception as e:
                print(f"[ERROR] Error parsing 7TV unlisted emotes from Redis: {e}")
        else:
            print(f"[CACHE MISS] 7TV unlisted emotes not found in Redis")

    # If not found in any cache, fetch and cache emotes if they don't exist
    print(f"[CACHE UPDATE] Emote '{emote_code}' not found in any cache, fetching fresh emotes")

    if not bttv_global_emotes:
        print("[EXTERNAL] Loading BTTV global emotes from API")
        load_bttv_global_emotes()

    if not seventv_global_emotes:
        print("[EXTERNAL] Loading 7TV global emotes from API")
        load_seventv_global_emotes()

    if channel_id:
        if not redis_client.exists(f"bttv:channel:{channel_id}:emotes"):
            print(f"[EXTERNAL] Loading BTTV channel emotes for {channel_id} from API")
            load_bttv_channel_emotes(channel_id)

        if not redis_client.exists(f"7tv:channel:{channel_id}:emotes:v3"):
            print(f"[EXTERNAL] Loading 7TV channel emotes for {channel_id} from API")
            load_seventv_channel_emotes(channel_id)

        if not redis_client.exists(f"7tv:unlisted:{channel_id}:emotes:v3"):
            print(f"[EXTERNAL] Loading 7TV unlisted emotes for {channel_id} from API")
            load_seventv_unlisted_emotes(channel_id)

    # Try one more lookup after refreshing caches
    print(f"[RETRY] Checking for '{emote_code}' in freshly loaded emotes")

    # Check all caches again after loading (simplified code for brevity)
    all_cache_keys = [
        "bttv:global:emotes",
        f"bttv:channel:{channel_id}:emotes",
        "7tv:global:emotes:v3",
        f"7tv:channel:{channel_id}:emotes:v3",
        f"7tv:unlisted:{channel_id}:emotes:v3"
    ]

    for key in all_cache_keys:
        cache_data = redis_client.get(key)
        if not cache_data:
            continue

        try:
            if "unlisted" in key:
                emotes = json.loads(cache_data)
                if emote_code in emotes:
                    emote = emotes[emote_code]
                    print(f"[MATCH FOUND AFTER REFRESH] '{emote_code}' found in {key}")
                    return jsonify({
                        "found": True,
                        "id": emote.get('id'),
                        "type": "7tv-unlisted" if "7tv:unlisted" in key else "7tv",
                        "animated": emote.get('animated', False),
                        "files": emote.get('files', []),
                        "source": f"{key}:refresh"
                    })
            else:
                emotes = json.loads(cache_data)
                for emote in emotes:
                    if emote.get('code') == emote_code:
                        print(f"[MATCH FOUND AFTER REFRESH] '{emote_code}' found in {key}")
                        emote_type = "bttv" if "bttv" in key else "7tv"
                        response_data = {
                            "found": True,
                            "id": emote.get('id'),
                            "type": emote_type,
                            "animated": emote.get('animated', False),
                            "source": f"{key}:refresh"
                        }
                        if emote_type == "bttv":
                            response_data["imageType"] = emote.get('imageType')
                        else:
                            response_data["files"] = emote.get('files', [])
                        return jsonify(response_data)
        except Exception as e:
            print(f"[ERROR] Error parsing emotes from Redis key {key} after refresh: {e}")

    # If still not found after loading
    print(f"[NOT FOUND] Emote '{emote_code}' not found in any cache or external source")
    return jsonify({"found": False})


# Helper Functions for Emote Loading
def get_channel_id():
    # Here you would get the channel ID from wherever you're storing it
    # This is just a placeholder
    return "29319793"


def get_channel_name():
    # Here you would get the channel name from wherever you're storing it
    # This is just a placeholder
    return "beastyrabbit"


def load_bttv_global_emotes():
    try:
        print("[EXTERNAL API] Fetching BTTV global emotes")
        response = requests.get('https://api.betterttv.net/3/cached/emotes/global')
        if response.status_code == 200:
            emotes = response.json()
            processed_emotes = []
            for emote in emotes:
                processed_emotes.append({
                    'code': emote['code'],
                    'id': emote['id'],
                    'imageType': emote['imageType'],
                    'animated': emote.get('animated', False),
                    'source': 'bttv:global'
                })

            redis_client.setex('bttv:global:emotes', REDIS_EXPIRY, json.dumps(processed_emotes))
            print(f"[CACHE STORE] Cached {len(processed_emotes)} BTTV global emotes")

            # Log a sample emote for debugging
            if processed_emotes:
                print(f"[SAMPLE EMOTE] BTTV global: {json.dumps(processed_emotes[0], indent=2)}")

            return processed_emotes
    except Exception as e:
        print(f"[ERROR] Error loading BTTV global emotes: {str(e)}")
        traceback.print_exc()
    return []


def load_bttv_channel_emotes(channel_id):
    try:
        print(f"[EXTERNAL API] Fetching BTTV emotes for channel {channel_id}")
        response = requests.get(f'https://api.betterttv.net/3/cached/users/twitch/{channel_id}')
        if response.status_code == 200:
            data = response.json()
            channel_emotes = []

            # Channel emotes
            if 'channelEmotes' in data:
                for emote in data['channelEmotes']:
                    channel_emotes.append({
                        'code': emote['code'],
                        'id': emote['id'],
                        'imageType': emote['imageType'],
                        'animated': emote.get('animated', False),
                        'source': 'bttv:channel'
                    })

            # Shared emotes
            if 'sharedEmotes' in data:
                for emote in data['sharedEmotes']:
                    channel_emotes.append({
                        'code': emote['code'],
                        'id': emote['id'],
                        'imageType': emote['imageType'],
                        'animated': emote.get('animated', False),
                        'source': 'bttv:shared'
                    })

            redis_client.setex(f'bttv:channel:{channel_id}:emotes', REDIS_EXPIRY, json.dumps(channel_emotes))
            print(f"[CACHE STORE] Cached {len(channel_emotes)} BTTV channel emotes for {channel_id}")

            # Log a sample emote for debugging
            if channel_emotes:
                print(f"[SAMPLE EMOTE] BTTV channel: {json.dumps(channel_emotes[0], indent=2)}")

            return channel_emotes
        elif response.status_code == 404:
            print(f"[NOT FOUND] No BTTV emotes found for channel {channel_id}")
            redis_client.setex(f'bttv:channel:{channel_id}:emotes', REDIS_EXPIRY, json.dumps([]))
    except Exception as e:
        print(f"[ERROR] Error loading BTTV channel emotes: {str(e)}")
        traceback.print_exc()
    return []


def load_seventv_global_emotes():
    try:
        print("[EXTERNAL API] Fetching 7TV global emotes")
        response = requests.get('https://7tv.io/v3/emote-sets/global')
        if response.status_code == 200:
            data = response.json()

            # Log the structure for debugging
            print(f"[DEBUG] 7TV global response structure: {list(data.keys())}")

            if 'emotes' in data:
                emotes = []
                for emote in data['emotes']:
                    # Print the structure of a sample emote for debugging
                    if len(emotes) == 0:
                        print(f"[DEBUG] Sample 7TV emote structure: {list(emote.keys())}")

                    # Handle case where 'animated' might not be present
                    animated = False
                    if 'animated' in emote:
                        animated = emote['animated']

                    emotes.append({
                        'code': emote['name'],
                        'id': emote['id'],
                        'animated': animated,
                        'source': '7tv:global',
                        'files': emote.get('files', [])
                    })

                redis_client.setex('7tv:global:emotes:v3', REDIS_EXPIRY, json.dumps(emotes))
                print(f"[CACHE STORE] Cached {len(emotes)} 7TV global emotes")

                # Log a sample emote for debugging
                if emotes:
                    print(f"[SAMPLE EMOTE] 7TV global: {json.dumps(emotes[0], indent=2)}")

                return emotes
            else:
                print(f"[ERROR] No 'emotes' field in 7TV global response: {list(data.keys())}")
    except Exception as e:
        print(f"[ERROR] Error loading 7TV global emotes: {str(e)}")
        traceback.print_exc()
    return []


def load_seventv_channel_emotes(channel_id):
    channel_name = get_channel_name()
    if not channel_name:
        print("[ERROR] No channel name available for 7TV emotes")
        return []

    try:
        print(f"[EXTERNAL API] Fetching 7TV user for channel {channel_id} (name: {channel_name})")
        # First get the user to find their emote set
        user_response = requests.get(f'https://7tv.io/v3/users/twitch/{channel_id}')

        if user_response.status_code != 200:
            if user_response.status_code == 404:
                print(f"[NOT FOUND] No 7TV user found for channel {channel_id}")
                redis_client.setex(f'7tv:channel:{channel_id}:emotes:v3', REDIS_EXPIRY, json.dumps([]))
                return []
            print(f"[ERROR] 7TV API error for user lookup: {user_response.status_code}")
            return []

        user_data = user_response.json()
        print(f"[DEBUG] 7TV user data keys: {list(user_data.keys())}")

        # Check for emote_set
        if 'emote_set' not in user_data or not user_data['emote_set'] or not user_data['emote_set'].get('id'):
            print(f"[NOT FOUND] No 7TV emote set found for channel {channel_id}")
            redis_client.setex(f'7tv:channel:{channel_id}:emotes:v3', REDIS_EXPIRY, json.dumps([]))
            return []

        emote_set_id = user_data['emote_set']['id']
        print(f"[INFO] Found 7TV emote set ID: {emote_set_id}")

        # Get the emote set details
        print(f"[EXTERNAL API] Fetching 7TV emote set {emote_set_id}")
        emote_set_response = requests.get(f'https://7tv.io/v3/emote-sets/{emote_set_id}')
        if emote_set_response.status_code != 200:
            print(f"[ERROR] 7TV API error for emote set: {emote_set_response.status_code}")
            return []

        emote_set_data = emote_set_response.json()
        print(f"[DEBUG] 7TV emote set data keys: {list(emote_set_data.keys())}")

        if 'emotes' not in emote_set_data:
            print(f"[ERROR] No 'emotes' field in 7TV emote set response")
            return []

        emotes = []
        for emote in emote_set_data['emotes']:
            # Print the structure of a sample emote for debugging
            if len(emotes) == 0:
                print(f"[DEBUG] Sample 7TV channel emote structure: {list(emote.keys())}")

            # Handle case where 'animated' might not be present
            animated = False
            if 'animated' in emote:
                animated = emote['animated']

            emotes.append({
                'code': emote['name'],
                'id': emote['id'],
                'animated': animated,
                'source': '7tv:channel',
                'files': emote.get('files', [])
            })

        redis_client.setex(f'7tv:channel:{channel_id}:emotes:v3', REDIS_EXPIRY, json.dumps(emotes))
        print(f"[CACHE STORE] Cached {len(emotes)} 7TV channel emotes for {channel_id}")

        # Log a sample emote for debugging
        if emotes:
            print(f"[SAMPLE EMOTE] 7TV channel: {json.dumps(emotes[0], indent=2)}")

        return emotes
    except Exception as e:
        print(f"[ERROR] Error loading 7TV channel emotes: {str(e)}")
        traceback.print_exc()
        return []


def load_seventv_unlisted_emotes(channel_id):
    try:
        print(f"[EXTERNAL API] Fetching 7TV unlisted emotes for channel {channel_id}")
        response = requests.get(f'https://7tv.io/v3/users/twitch/{channel_id}')
        if response.status_code == 200:
            data = response.json()
            unlisted_emotes = {}

            print(f"[DEBUG] 7TV user data keys for unlisted: {list(data.keys())}")

            if 'emote_set' in data and data['emote_set'] and 'emotes' in data['emote_set']:
                for emote in data['emote_set']['emotes']:
                    if not emote.get('listed', True):
                        # Handle case where 'animated' might not be present
                        animated = False
                        if 'animated' in emote:
                            animated = emote['animated']

                        unlisted_emotes[emote['name']] = {
                            'id': emote['id'],
                            'files': emote.get('files', []),
                            'animated': animated
                        }

            redis_client.setex(f'7tv:unlisted:{channel_id}:emotes:v3', REDIS_EXPIRY, json.dumps(unlisted_emotes))
            print(f"[CACHE STORE] Cached {len(unlisted_emotes)} 7TV unlisted emotes for {channel_id}")

            # Log a sample emote for debugging
            if unlisted_emotes:
                sample_key = next(iter(unlisted_emotes))
                print(f"[SAMPLE EMOTE] 7TV unlisted: {sample_key} -> {json.dumps(unlisted_emotes[sample_key], indent=2)}")

            return unlisted_emotes
        elif response.status_code == 404:
            print(f"[NOT FOUND] No 7TV data found for channel {channel_id}")
            redis_client.setex(f'7tv:unlisted:{channel_id}:emotes:v3', REDIS_EXPIRY, json.dumps({}))
    except Exception as e:
        print(f"[ERROR] Error loading 7TV unlisted emotes: {str(e)}")
        traceback.print_exc()
    return {}




if __name__ == '__main__':
    # Load emotes on startup
    print("Loading emotes on startup...")
    try:
        load_bttv_global_emotes()
        load_seventv_global_emotes()

        channel_id = get_channel_id()
        if channel_id:
            load_bttv_channel_emotes(channel_id)
            load_seventv_channel_emotes(channel_id)
            load_seventv_unlisted_emotes(channel_id)
    except Exception as e:
        print(f"Error during startup emote loading: {e}")
        traceback.print_exc()

    app.run(debug=True, host="0.0.0.0", port=5001)
