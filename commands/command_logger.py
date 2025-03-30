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
COMMANDS_KEY = 'twitch:messages:commands'  # Sorted set for all commands
MAX_STORED_COMMANDS = 5000  # Limit to prevent unbounded growth

##########################
# Initialize Redis
##########################
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
pubsub = redis_client.pubsub()
pubsub.psubscribe('twitch.command.*')

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels before exiting")
    pubsub.punsubscribe()
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "pmessage":
        try:
            # Parse the message
            message_obj = json.loads(message['data'].decode('utf-8'))
            channel = message['channel'].decode('utf-8')

            # Extract command name from channel (twitch.command.commandname)
            command_name = channel.split('.')[-1]

            # Ensure message follows our unified structure
            if 'type' not in message_obj:
                message_obj['type'] = 'command'

            if 'source' not in message_obj:
                message_obj['source'] = 'twitch'

            if 'timestamp' not in message_obj:
                message_obj['timestamp'] = datetime.now().isoformat()

            if 'metadata' not in message_obj:
                message_obj['metadata'] = {}

            if 'event_data' not in message_obj:
                message_obj['event_data'] = {}

            # Make sure command is in event_data
            if 'command' in message_obj:
                message_obj['event_data']['command'] = message_obj.pop('command')
            else:
                message_obj['event_data']['command'] = command_name

            # Add a numeric timestamp for Redis sorting
            current_time = time.time()
            message_obj['_score'] = current_time

            # Convert to JSON for storage
            message_json = json.dumps(message_obj)

            # Store in commands sorted set
            redis_client.zadd(COMMANDS_KEY, {message_json: current_time})

            # Store in all messages set too
            redis_client.zadd('twitch:messages:all', {message_json: current_time})

            # Store in command-specific set for easy retrieval
            command_key = f"twitch:commands:{command_name}"
            redis_client.zadd(command_key, {message_json: current_time})

            # Prune if exceeding max count
            current_count = redis_client.zcard(COMMANDS_KEY)
            if current_count > MAX_STORED_COMMANDS:
                # Remove oldest commands (lowest scores)
                redis_client.zremrangebyrank(COMMANDS_KEY,
                                             0,
                                             current_count - MAX_STORED_COMMANDS - 1)

            author_name = message_obj.get('author', {}).get('display_name', 'Unknown')
            print(f"Stored command: !{command_name} from {author_name} - {message_obj.get('content')}")

        except Exception as e:
            print(f"Error processing command: {e}")
            print(f"Message data: {message.get('data', 'N/A')}")
