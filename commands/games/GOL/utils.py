import os
import signal
import sys
from pathlib import Path
from module.message_utils import send_message_to_redis
from module.shared_redis import redis_client
from commands.games.GOL.models import game_state, logger

def award_dustbunnies(username, amount):
    """Award dustbunnies to a user."""
    # Increment the total awarded
    game_state['dustbunnies_awarded'] += amount

    # In a real implementation, you'd update the user's balance in Redis
    # This is a placeholder
    logger.info(f"Awarded {amount} dustbunnies to {username}")
    return amount

def handle_exit(signum, frame):
    """Handle exit signals."""
    print("Unsubscribing from all channels before exiting")
    from module.shared_redis import pubsub
    pubsub.unsubscribe()

    # Stop the Flask server if it's running
    if hasattr(handle_exit, 'flask_thread') and handle_exit.flask_thread.is_alive():
        # This is a simple way to stop the Flask server, but it's not ideal
        # In a production environment, you'd want a more graceful shutdown
        os._exit(0)
    sys.exit(0)  # Exit gracefully

def ensure_directories():
    """Ensure that the necessary directories exist."""
    # Get the path to the templates and static directories
    base_dir = Path(__file__).resolve().parent
    templates_dir = base_dir / 'templates'
    static_dir = base_dir / 'static'

    # Create the directories if they don't exist
    templates_dir.mkdir(exist_ok=True)
    static_dir.mkdir(exist_ok=True)

    return templates_dir, static_dir

def send_game_message(message, command="gameoflife"):
    """Send a message to chat about the game."""
    # Only send message if not in test mode
    if not game_state.get('test_mode', False):
        send_message_to_redis(message, command=command)
