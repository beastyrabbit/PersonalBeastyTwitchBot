#!/bin/bash

# Standalone script to refresh Twitch tokens every hour
# This script ONLY refreshes existing tokens and does not create new ones

# Configuration
REDIS_HOST="192.168.50.115"
REDIS_PORT="6379"
REDIS_DB="1"
REDIS_TOKEN_KEY="twitch_token"
REDIS_TOKEN_MAIN_KEY="twitch_token_main"

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

    # Extract partial token for logging
    local access_token=$(echo $response | jq -r '.access_token')
    local token_preview="${access_token:0:3}...${access_token: -3}"

    # Save the updated token
    save_token_to_redis $token_key "$updated_token_data"
    echo "$(date): Successfully refreshed token for $token_key: $token_preview"
    return 0
  else
    echo "Error refreshing token: $(echo $response | jq -r '.message // .error')"
    return 1
  fi
}

# Ensure dependencies
command -v jq >/dev/null 2>&1 || { echo "Error: jq is required but not installed. Please install jq."; exit 1; }
command -v redis-cli >/dev/null 2>&1 || { echo "Error: redis-cli is required but not installed. Please install redis-tools."; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "Error: curl is required but not installed. Please install curl."; exit 1; }

# Main refresh loop
echo "Starting token refresh service"
echo "$(date): Initial run"

# First refresh twitch_token_main if it exists
if get_token_from_redis $REDIS_TOKEN_MAIN_KEY > /dev/null; then
  echo "Refreshing $REDIS_TOKEN_MAIN_KEY"
  refresh_token $REDIS_TOKEN_MAIN_KEY || echo "Warning: Failed to refresh $REDIS_TOKEN_MAIN_KEY"
else
  echo "Note: $REDIS_TOKEN_MAIN_KEY not found in Redis, skipping"
fi

# Then refresh the regular token if it exists
if get_token_from_redis $REDIS_TOKEN_KEY > /dev/null; then
  echo "Refreshing $REDIS_TOKEN_KEY"
  refresh_token $REDIS_TOKEN_KEY || echo "Warning: Failed to refresh $REDIS_TOKEN_KEY"
else
  echo "Note: $REDIS_TOKEN_KEY not found in Redis, skipping"
fi