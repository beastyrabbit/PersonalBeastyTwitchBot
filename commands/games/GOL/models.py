import json
import logging
import uuid
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    'width': 1920,
    'height': 1080,
    'pixel_size': 10,
    'max_duration': 120,
    'speed_up_interval': 10,
    'dustbunnies_per_second': 10,
    'update_interval': 0.5,
    'ending_display_time': 5
}

# Game states dictionary - key is game UUID, value is game state
games = {}

# Default game state template
def create_game_state():
    return {
        'id': str(uuid.uuid4()),
        'running': False,
        'ending': False,
        'end_reason': None,
        'end_time': None,
        'grid': None,
        'will_be_created': None,  # Cells that will be created in the next step
        'will_be_destroyed': None,  # Cells that will be destroyed in the next step
        'seed': None,
        'config': DEFAULT_CONFIG.copy(),
        'start_time': None,
        'last_speed_up': None,
        'speed_multiplier': 1,
        'history': [],  # For detecting loops
        'dustbunnies_awarded': 0,
        'test_mode': True,  # Flag to indicate if the game is running in test mode
        'steps': 0,  # Counter for game steps
        'game_phase': 0,  # Current phase of the 6-step game loop
        'next_update': None  # When the client should call back
    }

# For backward compatibility
game_state = create_game_state()
games[game_state['id']] = game_state

def reset_game_state(game_id=None):
    """Reset the game state to default values.

    Args:
        game_id: The ID of the game to reset. If None, resets the default game state.

    Returns:
        The reset game state.
    """
    if game_id is None:
        game_id = game_state['id']

    if game_id in games:
        # Reset existing game
        new_state = create_game_state()
        new_state['id'] = game_id  # Keep the same ID
        games[game_id] = new_state

        # If this is the default game state, update that too
        if game_id == game_state['id']:
            for key, value in new_state.items():
                game_state[key] = value
    else:
        # Create a new game
        new_state = create_game_state()
        games[new_state['id']] = new_state

    return games[game_id]

def get_game_state(game_id=None):
    """Get a copy of a game state.

    Args:
        game_id: The ID of the game to get. If None, returns the default game state.

    Returns:
        A copy of the game state.
    """
    if game_id is None:
        return game_state.copy()

    if game_id in games:
        return games[game_id].copy()

    return None

def update_game_state(updates, game_id=None):
    """Update a game state with the provided updates.

    Args:
        updates: A dictionary of updates to apply.
        game_id: The ID of the game to update. If None, updates the default game state.

    Returns:
        The updated game state.
    """
    if game_id is None:
        game_id = game_state['id']

    if game_id in games:
        for key, value in updates.items():
            if key in games[game_id]:
                games[game_id][key] = value

        # If this is the default game state, update that too
        if game_id == game_state['id']:
            for key, value in updates.items():
                if key in game_state:
                    game_state[key] = value

    return games.get(game_id)
