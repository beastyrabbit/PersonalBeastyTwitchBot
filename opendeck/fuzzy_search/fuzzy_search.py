import json
from datetime import datetime

import redis
import requests

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client_env = redis.Redis(host='192.168.50.115', port=6379, db=1)
CLIENT_ID = redis_client_env.get("TWITCH_CLIENT_ID").decode('utf-8')
##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    return



##########################
# Default Message Methods
##########################
def send_admin_message_to_redis(message, command="brb"):
    # Create unified message object
    admin_message_obj = {
        "type": "admin",
        "source": "system",
        "content": message,
    }
    redis_client.publish(f'admin.{command}.send', json.dumps(admin_message_obj))


def send_message_to_redis(send_message, command="fuzzy_search"):
    redis_client.publish('twitch.chat.send', send_message)

# Token management functions (unchanged)
def load_token():
    """Load token from Redis database."""
    token_data = redis_client_env.get("twitch_token_main")
    if token_data:
        return json.loads(token_data)
    return None


def get_valid_token():
    """Ensure a valid token is available, refreshing if needed."""
    token_data = load_token()
    if token_data:
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if datetime.now() < expires_at:
            return token_data['access_token']  # Token is valid
        print('Token expired, re-authorizing...')
    return None  # Token expired or missing

##########################
# Helper Functions
##########################

def get_followed_channels():
    global CLIENT_ID

    # --- Step 1: Load token ---
    access_token = get_valid_token()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": CLIENT_ID
    }

    # --- Step 2: Get followed channels ---
    followed_channels = []
    url = "https://api.twitch.tv/helix/channels/followed"
    params = {"user_id": 29319793, "first": 100}

    while True:
        resp = requests.get(url, headers=headers, params=params)
        data = resp.json()
        followed_channels.extend(data["data"])
        cursor = data.get("pagination", {}).get("cursor")
        if not cursor:
            break
        params["after"] = cursor

    # --- Step 3: Fetch profile image for each followed channel ---
    for entry in followed_channels:
        broadcaster_id = entry["broadcaster_id"]
        user_info_url = f"https://api.twitch.tv/helix/users?id={broadcaster_id}"
        user_resp = requests.get(user_info_url, headers=headers)
        user_data = user_resp.json()
        if user_data["data"]:
            entry["profile_image_url"] = user_data["data"][0]["profile_image_url"]

    # --- Step 4: Save to JSON ---
    with open("followed_channels.json", "w", encoding="utf-8") as f:
        json.dump(followed_channels, f, ensure_ascii=False, indent=2)


##########################
# Main
##########################
get_followed_channels()
