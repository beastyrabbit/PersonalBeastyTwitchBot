#!/bin/bash
# Simple script to delete both Twitch tokens from Redis

REDIS_HOST="192.168.50.115"
REDIS_PORT="6379"
REDIS_DB="1"

# Delete both tokens
redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB DEL twitch_token
redis-cli -h $REDIS_HOST -p $REDIS_PORT -n $REDIS_DB DEL twitch_token_main

echo "Both Twitch tokens have been deleted from Redis"