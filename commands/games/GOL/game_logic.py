import random
import numpy as np
import json
from commands.games.GOL.models import game_state, logger

def initialize_grid(width, height, seed=None):
    """Initialize a random grid for Game of Life."""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    # Calculate grid dimensions based on pixel size
    grid_width = width // game_state['config']['pixel_size']
    grid_height = height // game_state['config']['pixel_size']

    # Create a random grid with ~25% live cells
    # Using the new pixel value system:
    # 0 = off
    # 1 = in_creation (not used in initialization)
    # 2 = normal
    # 3 = dying (not used in initialization)
    return np.random.choice([0, 2], size=(grid_height, grid_width), p=[0.75, 0.25])

def calculate_neighbors(grid):
    """Calculate the number of neighbors for each cell."""
    # Create a binary grid where 1 represents a live cell (value 2)
    binary_grid = (grid == 2).astype(np.int8)

    neighbors = np.zeros_like(grid)
    for i in range(-1, 2):
        for j in range(-1, 2):
            if i == 0 and j == 0:
                continue
            neighbors += np.roll(np.roll(binary_grid, i, axis=0), j, axis=1)
    return neighbors

def mark_cells_to_be_created(grid, neighbors):
    """Mark cells that will be created in the next step."""
    # Find cells that are off (0) and have exactly 3 neighbors
    will_be_created = (grid == 0) & (neighbors == 3)

    # Update the grid to mark these cells as in_creation (1)
    new_grid = grid.copy()
    new_grid[will_be_created] = 1  # Set to in_creation

    return new_grid, will_be_created

def mark_cells_to_be_destroyed(grid, neighbors):
    """Mark cells that will be destroyed in the next step."""
    # Find cells that are normal (2) and don't have 2 or 3 neighbors
    will_be_destroyed = (grid == 2) & ~((neighbors == 2) | (neighbors == 3))

    # Update the grid to mark these cells as dying (3)
    new_grid = grid.copy()
    new_grid[will_be_destroyed] = 3  # Set to dying

    return new_grid, will_be_destroyed

def remove_dying_cells(grid, will_be_destroyed=None):
    """Remove cells that are marked for destruction."""
    temp_grid = grid.copy()

    # Remove cells that are marked as dying (3)
    temp_grid[temp_grid == 3] = 0

    # For backward compatibility
    if will_be_destroyed is not None:
        temp_grid[will_be_destroyed == 1] = 0

    return temp_grid

def add_new_cells(grid, will_be_created=None):
    """Add cells that are marked for creation."""
    temp_grid = grid.copy()

    # Convert cells that are marked as in_creation (1) to normal (2)
    temp_grid[temp_grid == 1] = 2

    # For backward compatibility
    if will_be_created is not None:
        temp_grid[will_be_created == 1] = 2

    return temp_grid

def calculate_next_state(grid):
    """Calculate the next state of the grid without applying changes."""
    neighbors = calculate_neighbors(grid)

    # Find cells that will be created or destroyed
    will_be_created = (grid == 0) & (neighbors == 3)
    will_be_destroyed = (grid == 2) & ~((neighbors == 2) | (neighbors == 3))

    # Create a new grid with the updated cell states
    new_grid = grid.copy()
    new_grid[will_be_created] = 1  # Mark cells to be created as in_creation
    new_grid[will_be_destroyed] = 3  # Mark cells to be destroyed as dying

    return new_grid, will_be_created, will_be_destroyed, neighbors

def update_grid(grid):
    """Update the grid according to Game of Life rules."""
    # Calculate the next state
    new_grid, will_be_created, will_be_destroyed, neighbors = calculate_next_state(grid)

    # Apply Game of Life rules to get the final grid
    final_grid = np.zeros_like(grid)

    # Cells that survive (normal cells with 2-3 neighbors)
    final_grid[(grid == 2) & ((neighbors == 2) | (neighbors == 3))] = 2

    # Cells that are born (off cells with exactly 3 neighbors)
    final_grid[(grid == 0) & (neighbors == 3)] = 2

    return final_grid, will_be_created, will_be_destroyed

def is_stable(grid, history, max_history=20):
    """Check if the grid is stable (repeating pattern or all dead).

    A grid is considered stable if:
    1. All cells are dead, or
    2. The current grid matches a grid that was at least 2 full steps ago in the history.

    With 6 substeps per full step, this means we need to check if the current grid
    matches a grid that was at least 12 substeps ago.

    Returns:
        tuple: (is_stable, reason) where is_stable is a boolean and reason is a string
    """
    # Check if all cells are dead (no cells with value 1, 2, or 3)
    if np.sum((grid > 0).astype(np.int8)) == 0:
        return True, 'dead'

    # Check for repeating patterns
    # We only consider it a loop if the pattern repeats after at least 2 full steps (12 substeps)
    # This means we need to check if the current grid matches a grid that was at least 12 positions back in the history
    min_steps_for_loop = 1  # Minimum number of full steps to consider a loop

    # Each full step consists of 6 substeps, and we add to history at the end of each full step
    # So we need to check if the current grid matches a grid that was at least 2 positions back in the history
    if len(history) >= min_steps_for_loop + 1:  # +1 because we need at least one more step to compare with
        for i in range(len(history) - min_steps_for_loop):
            if np.array_equal(grid, history[i]):
                return True, 'loop'

    return False, None

def grid_to_json(grid):
    """Convert a numpy grid to a JSON-serializable format."""
    return grid.tolist() if grid is not None else None

def get_simulation_parameters():
    """Get the parameters needed for a simulation."""
    return {
        'config': game_state['config'],
        'seed': game_state['seed'],
        'test_mode': game_state['test_mode']
    }

def process_simulation_results(results):
    """Process the simulation results from the frontend."""
    # Update the game state with the results
    game_state['steps'] = results.get('steps', 0)
    game_state['dustbunnies_awarded'] = results.get('dustbunnies_awarded', 0)
    game_state['end_reason'] = results.get('end_reason')

    # Log the results
    logger.info(f"Simulation completed with {game_state['steps']} steps")
    logger.info(f"Dustbunnies awarded: {game_state['dustbunnies_awarded']}")
    logger.info(f"End reason: {game_state['end_reason']}")

    return {
        'status': 'success',
        'steps': game_state['steps'],
        'dustbunnies_awarded': game_state['dustbunnies_awarded'],
        'end_reason': game_state['end_reason']
    }
