import json
import signal
import sys
import time
from datetime import datetime

import redis

##########################
# Configuration
##########################
REDIS_HOST = '192.168.50.115'
REDIS_PORT = 6379
REDIS_DB = 0
CHAT_MESSAGES_KEY = 'twitch:messages:all'  # Sorted set for time-based storage
MAX_STORED_MESSAGES = 10000  # Limit to prevent unbounded growth

##########################
# Initialize Redis
##########################
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.chat.recieved')

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels before exiting")
    pubsub.unsubscribe()
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            # Parse the message
            message_obj = json.loads(message['data'].decode('utf-8'))

            # Use existing timestamp if available, otherwise add one
            if 'timestamp' not in message_obj:
                message_obj['timestamp'] = datetime.now().isoformat()

            # Add a numeric timestamp for Redis sorting
            current_time = time.time()
            message_obj['_score'] = current_time  # Hidden field just for sorting

            # Convert back to JSON for storage
            message_json = json.dumps(message_obj)

            # Store in sorted set with timestamp as score
            redis_client.zadd(CHAT_MESSAGES_KEY, {message_json: current_time})

            # Store in type-specific set if needed
            if 'type' in message_obj:
                type_key = f"twitch:messages:{message_obj['type']}"
                redis_client.zadd(type_key, {message_json: current_time})

            # Prune if exceeding max count (for main collection)
            current_count = redis_client.zcard(CHAT_MESSAGES_KEY)
            if current_count > MAX_STORED_MESSAGES:
                # Remove oldest messages (lowest scores)
                redis_client.zremrangebyrank(CHAT_MESSAGES_KEY,
                                             0,
                                             current_count - MAX_STORED_MESSAGES - 1)

            message_type = message_obj.get('type', 'unknown')
            print(f"Stored {message_type} message: {message_obj.get('content')}")

        except Exception as e:
            print(f"Error processing message: {e}")
