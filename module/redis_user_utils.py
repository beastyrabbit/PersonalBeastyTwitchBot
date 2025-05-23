"""Redis user utility functions for the TwitchBotV2 project.

This module provides functions for interacting with Redis to manage user data.
"""
import json
from module.shared_redis import redis_client
from module.message_utils import log_debug, log_info, log_error
from module.user_utils import normalize_username, user_exists

def get_user_data(username):
    """Retrieves user data from the Redis database.

    @param username: Username to get data for
    @return: User data dict if exists, None otherwise
    """
    normalized_username = normalize_username(username)
    user_key = f"user:{normalized_username}"

    try:
        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            return json.loads(user_json)
        return None
    except Exception as e:
        error_msg = f"Error getting user data: {e}"
        log_error(error_msg, "redis_user_utils", {"error": str(e), "username": normalized_username})
        return None

def create_default_user(username, display_name=None):
    """Creates a new user with default values in the Redis database.

    @param username: Username to create
    @param display_name: Display name (optional)
    @return: Created user data dict
    """
    normalized_username = normalize_username(username)

    if display_name is None:
        display_name = username.replace("@", "")

    user_data = {
        "name": normalized_username,
        "display_name": display_name,
        "chat": {"count": 0},
        "command": {"count": 0},
        "admin": {"count": 0},
        "dustbunnies": {"collected_dustbunnies": 0},
        "banking": {}
    }

    try:
        user_key = f"user:{normalized_username}"
        redis_client.set(user_key, json.dumps(user_data))
        log_info(f"Created new user: {normalized_username}", "redis_user_utils")
        return user_data
    except Exception as e:
        error_msg = f"Error creating user: {e}"
        log_error(error_msg, "redis_user_utils", {"error": str(e), "username": normalized_username})
        return None

def get_or_create_user(username, display_name=None):
    """Gets existing user or creates a new one if not found.

    @param username: Username to get or create
    @param display_name: Display name if creating new user (optional)
    @return: User data dict
    """
    # First check if user exists on Twitch
    if not user_exists(username):
        log_info(f"User {username} does not exist on Twitch", "redis_user_utils")
        return None
    
    # If user exists on Twitch, get or create in Redis
    user_data = get_user_data(username)
    
    if user_data is None:
        user_data = create_default_user(username, display_name)
    
    return user_data

def update_user_data(username, user_data):
    """Updates user data in the Redis database.

    @param username: Username to update
    @param user_data: Updated user data dict
    @return: True if successful, False otherwise
    """
    normalized_username = normalize_username(username)
    user_key = f"user:{normalized_username}"

    try:
        redis_client.set(user_key, json.dumps(user_data))
        log_debug(f"Updated user data for {normalized_username}", "redis_user_utils")
        return True
    except Exception as e:
        error_msg = f"Error updating user data: {e}"
        log_error(error_msg, "redis_user_utils", {"error": str(e), "username": normalized_username})
        return False