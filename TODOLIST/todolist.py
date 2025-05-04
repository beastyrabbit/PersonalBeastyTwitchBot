import json
import redis
import logging
from flask import Flask, render_template, Response, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Redis connection with error handling
try:
    redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
    redis_client.ping()  # Test connection
    logger.info("Connected to Redis successfully")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None

def get_todos():
    groups = {}
    try:
        if redis_client is None:
            logger.error("Redis client is not available")
            return []

        for todo_json in redis_client.lrange('todos', 0, -1):
            try:
                todo = json.loads(todo_json)
                group = todo.get('group', 'default')
                if group not in groups:
                    groups[group] = []
                groups[group].append(todo)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse todo JSON: {e}, data: {todo_json}")
                continue

        # Sort groups: default first, then alphabetical
        sorted_groups = []
        if 'default' in groups:
            sorted_groups.append(('default', groups.pop('default')))
        sorted_groups += sorted(groups.items())

        return sorted_groups
    except redis.RedisError as e:
        logger.error(f"Redis error in get_todos: {e}")
        return []
"""
API Documentation:

1. GET /
   - Description: Renders the main todo list page
   - Response: HTML page with all todos grouped by their group property
   - Error Handling: Returns an empty todo list with an error message if something goes wrong

2. GET /stream
   - Description: Server-sent events endpoint for real-time updates
   - Response: Text/event-stream with messages when todos are updated
   - Usage: Connect with EventSource in JavaScript to receive real-time updates
   - Error Handling: Sends error messages as events if something goes wrong

3. Redis Pub/Sub Channel: 'todo_updates'
   - Description: Channel for publishing updates to the todo list
   - Usage: Publish 'refresh' to this channel to notify clients to refresh their todo lists
   - Example: redis_client.publish('todo_updates', 'refresh')
"""

@app.route('/')
def index():
    """
    Render the main todo list page.

    Returns:
        HTML page with all todos grouped by their group property.
        If an error occurs, returns an empty todo list with an error message.
    """
    try:
        todos = get_todos()
        logger.info(f"Retrieved {sum(len(group[1]) for group in todos)} todos in {len(todos)} groups")
        return render_template('index.html', todos=todos)
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        return render_template('index.html', todos=[], error="Failed to load todos")

@app.route('/stream')
def stream():
    """
    Server-sent events endpoint for real-time updates.

    Returns:
        Text/event-stream with messages when todos are updated.
        Connect with EventSource in JavaScript to receive real-time updates.
    """
    def event_stream():
        """
        Generator function that yields server-sent events.

        Yields:
            Events when todos are updated.
            Error messages as events if something goes wrong.
        """
        try:
            if redis_client is None:
                logger.error("Redis client is not available for event stream")
                yield f"data: Error: Redis connection failed\n\n"
                return

            pubsub = redis_client.pubsub()
            pubsub.subscribe('todo_updates')
            logger.info("Subscribed to todo_updates channel")

            try:
                for message in pubsub.listen():
                    if message['type'] == 'message':
                        try:
                            data = message['data'].decode()
                            yield f"data: {data}\n\n"
                            logger.debug(f"Sent event: {data}")
                        except Exception as e:
                            logger.error(f"Error processing message: {e}")
                            continue
            except Exception as e:
                logger.error(f"Error in pubsub listen loop: {e}")
                yield f"data: Error: Stream interrupted\n\n"
            finally:
                try:
                    pubsub.unsubscribe()
                    logger.info("Unsubscribed from todo_updates channel")
                except:
                    pass
        except Exception as e:
            logger.error(f"Error in event_stream: {e}")
            yield f"data: Error: {str(e)}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
