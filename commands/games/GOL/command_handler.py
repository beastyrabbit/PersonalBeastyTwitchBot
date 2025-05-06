import json
import threading
from datetime import datetime

from module.message_utils import send_admin_message_to_redis
from module.shared_redis import redis_client, pubsub
from commands.games.GOL.models import game_state, DEFAULT_CONFIG
from commands.games.GOL.utils import send_game_message
from commands.games.GOL.server import start_web_server

def handle_command(message_obj):
    """Handle the gameoflife command."""
    try:
        # Parse command arguments
        content = message_obj.get('content', '')
        parts = content.split()

        # Default configuration
        config = DEFAULT_CONFIG.copy()
        seed = None

        # Parse arguments
        for i, part in enumerate(parts[1:], 1):
            if part.startswith('seed='):
                try:
                    seed = int(part.split('=')[1])
                except ValueError:
                    # If not a valid integer, use the string as a seed
                    seed = hash(part.split('=')[1]) % 1000000
            elif part.startswith('pixel='):
                try:
                    config['pixel_size'] = int(part.split('=')[1])
                except ValueError:
                    pass
            elif part.startswith('duration='):
                try:
                    config['max_duration'] = int(part.split('=')[1])
                except ValueError:
                    pass
            elif part.startswith('speedup='):
                try:
                    config['speed_up_interval'] = int(part.split('=')[1])
                except ValueError:
                    pass
            elif part.startswith('dustbunnies='):
                try:
                    config['dustbunnies_per_second'] = int(part.split('=')[1])
                except ValueError:
                    pass
            elif part.startswith('update='):
                try:
                    config['update_interval'] = float(part.split('=')[1])
                except ValueError:
                    pass
            elif part.startswith('endtime='):
                try:
                    config['ending_display_time'] = int(part.split('=')[1])
                except ValueError:
                    pass

        # Update game state with new configuration
        game_state['config'] = config
        game_state['seed'] = seed

        # Check for test mode parameter
        test_mode = False
        for part in parts[1:]:
            if part.lower() == 'test' or part.lower() == 'testmode':
                test_mode = True
                break

        # Set test mode in game state
        game_state['test_mode'] = test_mode

        # Use the server's hostname or IP instead of localhost
        test_param = "?test=true" if test_mode else ""

        # Send a message to chat with the URL
        url = f"http://192.168.10.243:5001{test_param}"
        seed_msg = f" with seed {seed}" if seed is not None else ""

        if not game_state['running']:
            # Game is not running, send a start message
            send_game_message(f"Starting Game of Life{seed_msg}! Watch at {url}")
        else:
            # Game is already running, just send the URL
            send_game_message(f"Game of Life is already running! Watch at {url}")

    except Exception as e:
        print(f"Error in handle_command: {e}")
        send_admin_message_to_redis(f"Error in gameoflife command: {str(e)}", command="gameoflife")

def start_command_handler():
    """Start the command handler."""
    # Subscribe to the command channel
    pubsub.subscribe('twitch.command.gameoflife')
    pubsub.subscribe('twitch.command.gol')
    pubsub.subscribe('twitch.command.gl')

    # Start the web server in a separate thread
    flask_thread = threading.Thread(target=start_web_server)
    flask_thread.daemon = True
    flask_thread.start()

    # Store the thread for clean exit
    from commands.games.GOL.utils import handle_exit
    handle_exit.flask_thread = flask_thread

    # Send a message to the admin channel
    send_admin_message_to_redis("Game of Life command is ready to be used", command="gameoflife")

    # Main message loop
    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                message_obj = json.loads(message['data'].decode('utf-8'))
                print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
                handle_command(message_obj)
            except Exception as e:
                print(f"Error processing command: {e}")
                send_admin_message_to_redis(f"Error in gameoflife command: {str(e)}", command="gameoflife")
