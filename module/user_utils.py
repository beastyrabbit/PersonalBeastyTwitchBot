"""Utility functions for user validation and handling in the TwitchBotV2 project."""
import json
import requests
from datetime import datetime
from module.shared_redis import redis_client_env
from module.message_utils import log_debug, log_info, log_error, log_warning

# Twitch API constants
TWITCH_CLIENT_ID = redis_client_env.get("TWITCH_CLIENT_ID").decode('utf-8') if redis_client_env.exists("TWITCH_CLIENT_ID") else None

def normalize_username(username):
    """Converts username to lowercase and removes @ symbol.

    @param username: The username to normalize
    @return: Normalized username (lowercase, no @ symbol)
    """
    if username is None:
        return None
    return username.lower().replace("@", "")

def load_token():
    """Load token from Redis database.

    @return: Token data dictionary or None if not found
    """
    token_data = redis_client_env.get("twitch_token_main")
    if token_data:
        return json.loads(token_data)
    return None

def get_valid_token():
    """Ensure a valid token is available.

    @return: Valid access token or None if not available
    """
    token_data = load_token()
    if token_data:
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        # Make sure we're comparing datetimes with the same timezone awareness
        if expires_at.tzinfo is not None:
            # expires_at is timezone-aware, so make now timezone-aware too
            now = datetime.now().astimezone()
        else:
            # expires_at is naive, so use naive now
            now = datetime.now()

        if now < expires_at:
            return token_data['access_token']  # Token is valid
        log_warning('Twitch token expired, please refresh it', "user_utils")
    return None  # Token expired or missing

def check_twitch_user_exists(username):
    """Checks if a user exists on Twitch.

    @param username: Username to check
    @return: True if user exists on Twitch, False otherwise
    """
    normalized_username = normalize_username(username)

    # Get valid token
    access_token = get_valid_token()
    if not access_token or not TWITCH_CLIENT_ID:
        log_error("Missing Twitch access token or client ID", "user_utils")
        return False

    # Set up headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Client-Id": TWITCH_CLIENT_ID
    }

    # Make API request to check if user exists
    url = "https://api.twitch.tv/helix/users"
    params = {"login": normalized_username}

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            # If data array is not empty, user exists
            return len(data.get("data", [])) > 0
        else:
            log_error(f"Twitch API error: {response.status_code}", "user_utils", 
                     {"response": response.text})
            return False
    except Exception as e:
        error_msg = f"Error checking if Twitch user exists: {e}"
        log_error(error_msg, "user_utils", {"error": str(e), "username": normalized_username})
        return False

def user_exists(username):
    """Checks if a user exists on Twitch.

    @param username: Username to check
    @return: True if user exists, False otherwise
    """
    # First check if user exists on Twitch
    return check_twitch_user_exists(username)
