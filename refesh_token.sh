#!/bin/bash

# Script to check token expiry and refresh only if needed
# Run this every 10 minutes via cron
# Will refresh tokens only if they expire in less than 30 minutes

# Configuration
REDIS_HOST="192.168.50.115"
REDIS_PORT="6379"
REDIS_DB="1"
REDIS_TOKEN_KEY="twitch_token"
REDIS_TOKEN_MAIN_KEY="twitch_token_main"
EXPIRY_THRESHOLD_MINUTES=30  # Refresh if less than this many minutes until expiry

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

# Function to check if token needs refresh
needs_refresh() {
  local token_key=$1

  # Get current token data
  local token_data=$(get_token_from_redis $token_key)
  if [ -z "$token_data" ]; then
    echo "No token data found for $token_key"
    return 1
  fi

  # Extract expiration time
  local expires_at=$(echo $token_data | jq -r '.expires_at')
  if [ -z "$expires_at" ] || [ "$expires_at" == "null" ]; then
    echo "No expiration time found for $token_key, will refresh"
    return 0
  fi

  # Calculate time until expiry in seconds
  local expires_timestamp=$(date -d "$expires_at" +%s)
  local now=$(date +%s)
  local seconds_until_expiry=$((expires_timestamp - now))
  local minutes_until_expiry=$((seconds_until_expiry / 60))

  # Log expiry info
  echo "Token $token_key expires in $minutes_until_expiry minutes"

  # Check if expiry is less than threshold
  if [ $minutes_until_expiry -lt $EXPIRY_THRESHOLD_MINUTES ]; then
    echo "Token $token_key will expire soon (less than $EXPIRY_THRESHOLD_MINUTES minutes), needs refresh"
    return 0
  else
    echo "Token $token_key is still valid, no refresh needed"
    return 1
  fi
}

# Function to refresh token using the refresh token
refresh_token() {
  local token_key=$1
  echo "Refreshing token for $token_key..."

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
    echo "Successfully refreshed token for $token_key: $token_preview"
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

# Main script execution
echo "$(date): Checking token expiry..."


# Check and refresh each token if needed
for token_key in $REDIS_TOKEN_KEY $REDIS_TOKEN_MAIN_KEY; do
  if get_token_from_redis $token_key > /dev/null; then
    if needs_refresh $token_key; then
      refresh_token $token_key || echo "Warning: Failed to refresh $token_key"
    fi
  else
    echo "Note: $token_key not found in Redis, skipping"
  fi
done


echo "$(date): Token check completed"