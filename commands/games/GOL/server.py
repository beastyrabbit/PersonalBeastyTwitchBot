import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from pathlib import Path
import uuid

from commands.games.GOL.models import game_state, DEFAULT_CONFIG, games, get_game_state, update_game_state, reset_game_state
from commands.games.GOL.game_logic import (
    initialize_grid, update_grid, is_stable, grid_to_json, get_simulation_parameters, process_simulation_results,
    calculate_next_state, mark_cells_to_be_created, mark_cells_to_be_destroyed, remove_dying_cells, add_new_cells
)
from commands.games.GOL.utils import ensure_directories, send_game_message, award_dustbunnies

# Create Flask app
app = Flask(__name__, 
            template_folder=str(Path(__file__).resolve().parent / 'templates'),
            static_folder=str(Path(__file__).resolve().parent / 'static'))

@app.route('/')
def index():
    """Render the main page."""
    # Get game ID from query parameter, or use default
    game_id = request.args.get('id', game_state['id'])

    # Get the game state
    current_game = get_game_state(game_id)
    if current_game is None:
        # If game not found, use default
        current_game = game_state
        game_id = game_state['id']

    # Check for test mode parameter
    test_mode = request.args.get('test', 'false').lower() in ('true', '1', 't')
    if test_mode:
        current_game['test_mode'] = True
        update_game_state(current_game, game_id)

    return render_template('gameoflife.html',
                          config=current_game['config'],
                          seed=current_game['seed'],
                          test_mode=current_game.get('test_mode', False),
                          game_id=game_id)

# The /get_next_game_step endpoint has been removed.
# All game states are now provided upfront by the /start endpoint.

@app.route('/grid')
def get_grid():
    """Get the current grid state without advancing the game (for backward compatibility)."""
    # Get game ID from query parameter, or use default
    game_id = request.args.get('id', game_state['id'])

    # Get the game state
    current_game = get_game_state(game_id)
    if current_game is None or current_game['grid'] is None:
        return jsonify({'error': 'Game not started'})

    now = datetime.now()

    # Calculate when the client should call back (1 second)
    base_update_interval = 1.0  # Fixed 1 second interval
    effective_interval = base_update_interval / current_game['speed_multiplier']
    current_game['next_update'] = now + timedelta(seconds=effective_interval)

    # Update the game state
    update_game_state(current_game, game_id)

    # Return the current game state
    return jsonify({
        'id': current_game['id'],
        'grid': grid_to_json(current_game['grid']),  # Grid now contains all cell states (0=off, 1=in_creation, 2=normal, 3=dying)
        'config': current_game['config'],
        'running': current_game['running'],
        'ending': current_game['ending'],
        'end_reason': current_game['end_reason'],
        'elapsed_time': (now - current_game['start_time']).total_seconds() if current_game['start_time'] else 0,
        'steps': current_game['steps'],
        'speed_multiplier': current_game['speed_multiplier'],
        'dustbunnies_awarded': current_game['dustbunnies_awarded'],
        'update_interval': effective_interval,
        'timestamp': now.timestamp(),
        'game_phase': current_game['game_phase'],
        'next_update': current_game['next_update'].timestamp() if current_game['next_update'] else None
    })

@app.route('/start', methods=['POST'])
def start_game():
    """Start a new Game of Life and calculate all game states upfront."""
    data = request.json or {}
    seed = data.get('seed', game_state['seed'])
    game_id = data.get('id')

    # Create a new game or reset an existing one
    if game_id and game_id in games:
        current_game = reset_game_state(game_id)
    else:
        current_game = reset_game_state()
        game_id = current_game['id']

    # Initialize the grid
    current_game['grid'] = initialize_grid(
        current_game['config']['width'],
        current_game['config']['height'],
        seed
    )

    # Set up the game state
    current_game['running'] = True
    current_game['ending'] = False
    current_game['end_reason'] = None
    current_game['end_time'] = None
    current_game['seed'] = seed
    current_game['start_time'] = datetime.now()
    current_game['last_speed_up'] = datetime.now()
    current_game['speed_multiplier'] = 1
    current_game['history'] = [current_game['grid'].copy()]
    current_game['dustbunnies_awarded'] = 0
    current_game['steps'] = 0
    current_game['will_be_created'] = None
    current_game['will_be_destroyed'] = None
    current_game['game_phase'] = 0  # We still use game_phase for compatibility, but only use value 0
    current_game['next_update'] = datetime.now() + timedelta(seconds=current_game['config']['update_interval'])

    # Update the game state
    update_game_state(current_game, game_id)

    # Calculate all game states upfront
    now = datetime.now()
    all_grid_states = []

    # Store initial state
    all_grid_states.append({
        'grid': grid_to_json(current_game['grid']),
        'game_phase': current_game['game_phase'],
        'timestamp': now.timestamp(),
        'speed_multiplier': current_game['speed_multiplier'],
        'steps': current_game['steps'],
        'dustbunnies_awarded': current_game['dustbunnies_awarded'],
        'elapsed_time': 0
    })

    # Calculate all steps until the game ends
    game_over = False
    while not game_over:
        # Check if we should speed up
        if current_game['start_time'] is not None:
            elapsed = (now - current_game['start_time']).total_seconds()
            since_last_speedup = (now - current_game['last_speed_up']).total_seconds()

            # Speed up if needed
            if since_last_speedup >= current_game['config']['speed_up_interval']:
                current_game['speed_multiplier'] *= 1.5
                current_game['last_speed_up'] = now

        # Process a normal Game of Life step (no intermediate phases)
        # Update the grid according to Game of Life rules
        final_grid, _, _ = update_grid(current_game['grid'])
        current_game['grid'] = final_grid
        current_game['steps'] += 1

        # Add to history and check for stability
        current_game['history'].append(current_game['grid'].copy())
        if len(current_game['history']) > 20:
            current_game['history'].pop(0)

        # Check for stability or timeout
        elapsed = (now - current_game['start_time']).total_seconds()
        is_stable_result, stability_reason = is_stable(current_game['grid'], current_game['history'])

        if is_stable_result or elapsed >= current_game['config']['max_duration']:
            # Game is entering ending state
            current_game['ending'] = True
            current_game['end_time'] = now

            # Set the end reason
            if is_stable_result:
                current_game['end_reason'] = stability_reason
            else:
                current_game['end_reason'] = 'timeout'

            # Mark that we'll need to add the ending state
            game_over = True

        # Award dustbunnies
        current_game['dustbunnies_awarded'] += current_game['config']['dustbunnies_per_second']

        # Add the current state to the grid states array
        now = now + timedelta(milliseconds=1000 / current_game['speed_multiplier'])
        elapsed = (now - current_game['start_time']).total_seconds()

        all_grid_states.append({
            'grid': grid_to_json(current_game['grid']),
            'game_phase': current_game['game_phase'],
            'timestamp': now.timestamp(),
            'speed_multiplier': current_game['speed_multiplier'],
            'steps': current_game['steps'],
            'dustbunnies_awarded': current_game['dustbunnies_awarded'],
            'elapsed_time': elapsed,
            'ending': current_game['ending'],
            'end_reason': current_game['end_reason']
        })

        # If the game is over, add one more state with game_over flag
        if game_over:
            # Add a final state with game_over flag
            now = now + timedelta(seconds=current_game['config']['ending_display_time'])
            elapsed = (now - current_game['start_time']).total_seconds()

            all_grid_states.append({
                'grid': grid_to_json(current_game['grid']),
                'game_phase': current_game['game_phase'],
                'timestamp': now.timestamp(),
                'speed_multiplier': current_game['speed_multiplier'],
                'steps': current_game['steps'],
                'dustbunnies_awarded': current_game['dustbunnies_awarded'],
                'elapsed_time': elapsed,
                'ending': False,  # No longer in ending state
                'running': False,  # Game is over
                'game_over': True,  # Explicit game over flag
                'end_reason': current_game['end_reason']
            })

    # Update the game state
    update_game_state(current_game, game_id)

    # Calculate time intervals between states for the frontend
    for i in range(len(all_grid_states) - 1):
        all_grid_states[i]['display_time'] = (all_grid_states[i+1]['timestamp'] - all_grid_states[i]['timestamp']) * 1000  # in milliseconds

    # Set a default display time for the last state
    if all_grid_states:
        all_grid_states[-1]['display_time'] = 1000  # 1 second for the last state

    return jsonify({
        'status': 'started',
        'id': game_id,
        'seed': seed,
        'config': current_game['config'],
        'grid_states': all_grid_states,
        'total_states': len(all_grid_states)
    })

@app.route('/stop')
def stop_game():
    """Stop the current Game of Life."""
    game_id = request.args.get('id', game_state['id'])

    # Get the game state
    current_game = get_game_state(game_id)
    if current_game is None:
        return jsonify({'error': 'Game not found'})

    # Stop the game
    current_game['running'] = False
    update_game_state(current_game, game_id)

    return jsonify({'status': 'stopped', 'id': game_id})

@app.route('/simulate', methods=['GET'])
def get_simulation():
    """Get the parameters for a simulation."""
    game_id = request.args.get('id', game_state['id'])

    # Get the game state
    current_game = get_game_state(game_id)
    if current_game is None:
        return jsonify({'error': 'Game not found'})

    return jsonify({
        'config': current_game['config'],
        'seed': current_game['seed'],
        'test_mode': current_game['test_mode'],
        'id': game_id
    })

@app.route('/simulate', methods=['POST'])
def submit_simulation():
    """Submit the results of a simulation."""
    data = request.json or {}
    game_id = data.get('id', game_state['id'])

    # Get the game state
    current_game = get_game_state(game_id)
    if current_game is None:
        return jsonify({'error': 'Game not found'})

    # Update the game state with the results
    current_game['steps'] = data.get('steps', 0)
    current_game['dustbunnies_awarded'] = data.get('dustbunnies_awarded', 0)
    current_game['end_reason'] = data.get('end_reason')

    # Update the game state
    update_game_state(current_game, game_id)

    return jsonify({
        'status': 'success',
        'id': game_id,
        'steps': current_game['steps'],
        'dustbunnies_awarded': current_game['dustbunnies_awarded'],
        'end_reason': current_game['end_reason']
    })

@app.route('/playback_complete', methods=['POST'])
def playback_complete():
    """Handle notification that the client has finished playing back all pre-calculated steps."""
    data = request.json or {}
    game_id = data.get('id', game_state['id'])

    # Get the game state
    current_game = get_game_state(game_id)
    if current_game is None:
        return jsonify({'error': 'Game not found'})

    # Award dustbunnies to the user
    if not current_game.get('test_mode', False):
        award_amount = 10  # Fixed amount of dustbunnies to award
        award_dustbunnies("chat", award_amount)
        logger.info(f"Awarded {award_amount} dustbunnies to chat")

    # Return success response with next batch of pre-calculated steps
    return jsonify({
        'status': 'success',
        'id': game_id,
        'message': 'Playback complete acknowledged'
    })

@app.route('/test', methods=['POST'])
def test_simulation():
    """Start a test simulation."""
    data = request.json or {}
    seed = data.get('seed')
    game_id = data.get('id')

    # Create a new game or reset an existing one
    if game_id and game_id in games:
        current_game = reset_game_state(game_id)
    else:
        current_game = reset_game_state()
        game_id = current_game['id']

    # Set up the game state for testing
    current_game['seed'] = seed
    current_game['test_mode'] = True

    # Update the game state
    update_game_state(current_game, game_id)

    return jsonify({
        'status': 'test_started',
        'id': game_id,
        'seed': seed,
        'config': current_game['config']
    })

def ensure_template_files():
    """Ensure that the template and static files exist."""
    templates_dir, static_dir = ensure_directories()

    # Check if the template file exists
    template_file = templates_dir / 'gameoflife.html'
    if not template_file.exists():
        raise FileNotFoundError(f"Template file {template_file} not found. Please create it first.")

    # Check if the CSS file exists
    css_file = static_dir / 'gameoflife.css'
    if not css_file.exists():
        raise FileNotFoundError(f"CSS file {css_file} not found. Please create it first.")

    # Check if the JS file exists
    js_file = static_dir / 'gameoflife.js'
    if not js_file.exists():
        raise FileNotFoundError(f"JavaScript file {js_file} not found. Please create it first.")

def start_web_server():
    """Start the Flask web server."""
    # Ensure the template and static files exist
    ensure_template_files()

    # Start the Flask server
    app.run(host='0.0.0.0', port=5001, debug=False, threaded=True)
