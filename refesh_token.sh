#!/bin/bash

# Standalone script to refresh Twitch tokens every hour
# This script directly interacts with Redis and the Twitch API

# Configuration - Update these values
REDIS_HOST="192.168.50.115"
REDIS_PORT="6379"
REDIS_DB="1"
REDIS_TOKEN_KEY="twitch_token"
REDIS_TOKEN_MAIN_KEY="twitch_token_main"
REDIRECT_URI="https://twitch_recall.beasty.cloud/callback"
SCOPES="chat:read user:read:chat chat:edit user:write:chat moderator:manage:announcements moderator:manage:chat_messages moderator:manage:shoutouts whispers:read user:manage:whispers moderator:read:chatters channel:read:redemptions channel:manage:redemptions channel:manage:polls channel:manage:predictions moderator:manage:chat_settings channel:moderate channel:manage:moderators channel:manage:vips channel:manage:raids channel:manage:broadcast channel:read:hype_train channel:edit:commercial channel:read:subscriptions user:read:emotes user:read:follows moderator:read:followers user:read:moderated_channels user:read:blocked_users user:manage:blocked_users user:edit:broadcast moderator:manage:banned_users moderator:manage:automod moderator:manage:shield_mode moderator:manage:unban_requests clips:edit channel:read:ads channel:manage:ads moderator:manage:blocked_terms moderator:manage:warnings moderator:read:moderators moderator:read:vips moderator:read:suspicious_users bits:read"

# Function to get environment variables from Redis
get_env_from_redis() {
  local key=$1
  redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB GET $key
}

# Get client credentials from Redis
CLIENT_ID=$(get_env_from_redis "TWITCH_CLIENT_ID")
CLIENT_SECRET=$(get_env_from_redis "TWITCH_CLIENT_SECRET")

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
  echo "Error: Could not retrieve TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET from Redis"
  exit 1
fi

# Function to get token data from Redis
get_token_from_redis() {
  local token_key=$1
  redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB GET $token_key
}

# Function to save token data to Redis
save_token_to_redis() {
  local token_key=$1
  local token_data=$2
  redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB SET $token_key "$token_data"
}

# Function to delete token from Redis
delete_token_from_redis() {
  local token_key=$1
  redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB DEL $token_key
}

# Function to refresh token using the refresh token
refresh_token() {
  local token_key=$1
  echo "$(date): Refreshing token for $token_key..."

  # Get current token data
  local token_data=$(get_token_from_redis $token_key)
  if [ -z "$token_data" ]; then
    echo "Error: No token data found for $token_key"
    return 1
  fi

  # Extract refresh token
  local refresh_token=$(echo $token_data | jq -r '.refresh_token')
  if [ -z "$refresh_token" ] || [ "$refresh_token" == "null" ]; then
    echo "Error: No refresh token found in token data"
    return 1
  fi

  # Refresh the token using the Twitch API
  local response=$(curl -s -X POST "https://id.twitch.tv/oauth2/token" \
    -d "client_id=$CLIENT_ID" \
    -d "client_secret=$CLIENT_SECRET" \
    -d "grant_type=refresh_token" \
    -d "refresh_token=$refresh_token")

  # Check if refresh was successful
  if [ $(echo $response | jq -r 'has("access_token")') == "true" ]; then
    # Calculate expiration time
    local expires_in=$(echo $response | jq -r '.expires_in')
    local expires_at=$(date -d "+$expires_in seconds" -Iseconds)

    # Add expires_at to the response
    local updated_token_data=$(echo $response | jq --arg expires_at "$expires_at" '. + {expires_at: $expires_at}')

    # Save the updated token
    save_token_to_redis $token_key "$updated_token_data"
    echo "$(date): Successfully refreshed token for $token_key"
    return 0
  else
    echo "Error refreshing token: $(echo $response | jq -r '.message // .error')"
    return 1
  fi
}

# Function for initial token setup if needed
check_and_guide_for_new_token() {
  local token_key=$1

  # Check if token exists
  local token_data=$(get_token_from_redis $token_key)
  if [ -z "$token_data" ]; then
    echo "No token found for $token_key. Please follow these steps to set up a new token:"
    echo "1. Visit the following URL in your browser:"
    echo "https://id.twitch.tv/oauth2/authorize?client_id=$CLIENT_ID&redirect_uri=$REDIRECT_URI&response_type=code&scope=$(echo $SCOPES | tr ' ' '+')"
    echo "2. After authorization, you'll be redirected to your callback URL with a code parameter"
    echo "3. Extract that code and run:"
    echo "curl -X POST 'https://id.twitch.tv/oauth2/token' \\"
    echo "  -d 'client_id=$CLIENT_ID' \\"
    echo "  -d 'client_secret=$CLIENT_SECRET' \\"
    echo "  -d 'code=YOUR_CODE_HERE' \\"
    echo "  -d 'grant_type=authorization_code' \\"
    echo "  -d 'redirect_uri=$REDIRECT_URI'"
    echo "4. Save the response to Redis with:"
    echo "redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB SET $token_key 'RESPONSE_JSON'"

    return 1
  fi

  return 0
}

# Ensure dependencies
command -v jq >/dev/null 2>&1 || { echo "Error: jq is required but not installed. Please install jq."; exit 1; }
command -v redis-cli >/dev/null 2>&1 || { echo "Error: redis-cli is required but not installed. Please install redis-tools."; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "Error: curl is required but not installed. Please install curl."; exit 1; }

# First, refresh twitch_token_main
echo "First refreshing $REDIS_TOKEN_MAIN_KEY..."
delete_token_from_redis $REDIS_TOKEN_MAIN_KEY
check_and_guide_for_new_token $REDIS_TOKEN_MAIN_KEY || { echo "Please set up $REDIS_TOKEN_MAIN_KEY first and then rerun this script."; exit 1; }
refresh_token $REDIS_TOKEN_MAIN_KEY || { echo "Error refreshing $REDIS_TOKEN_MAIN_KEY. Please check the logs."; exit 1; }

# Then start the hourly refresh loop for the regular token
echo "Starting hourly refresh loop for $REDIS_TOKEN_KEY"
while true; do
  check_and_guide_for_new_token $REDIS_TOKEN_KEY || { echo "Please set up $REDIS_TOKEN_KEY first and then rerun this script."; exit 1; }
  refresh_token $REDIS_TOKEN_KEY || echo "Error refreshing $REDIS_TOKEN_KEY. Will try again in one hour."

  # Wait for 1 hour
  echo "Waiting for 1 hour before next refresh..."
  sleep 3600
done