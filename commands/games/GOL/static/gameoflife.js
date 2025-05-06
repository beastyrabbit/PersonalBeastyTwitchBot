// Game state variables
let gameId = null;
let config = {};
let seed = null;
let isTestMode = false;
let grid = [];
let isRunning = false;
let gameEnded = false;
let simulationInProgress = false;
let nextUpdateTime = null;
let cellElements = []; // Array to store references to cell DOM elements

// DOM element references
let gameGrid;
let seedDisplay;
let speedDisplay;
let timeDisplay;
let stepsDisplay;
let dustbunniesDisplay;
let statusIndicator;
let statusDisplay;
let gameOverDisplay;
let startButton;
let newSeedButton;

// Initialize DOM references
function initDOMReferences() {
    // Get DOM elements
    gameGrid = document.getElementById('gameGrid');
    seedDisplay = document.getElementById('seed');
    speedDisplay = document.getElementById('speed');
    timeDisplay = document.getElementById('time');
    stepsDisplay = document.getElementById('steps');
    dustbunniesDisplay = document.getElementById('dustbunnies');
    statusIndicator = document.getElementById('status-indicator');
    statusDisplay = document.getElementById('status');
    gameOverDisplay = document.getElementById('game-over');
    startButton = document.getElementById('start-button');

    // Get test mode button if in test mode
    newSeedButton = document.getElementById('new-seed-button');

    // Add event listeners to buttons
    if (startButton) {
        startButton.addEventListener('click', () => {
            console.log('Start button clicked');
            init();
        });
    }

    if (newSeedButton) {
        newSeedButton.addEventListener('click', () => {
            console.log('New seed button clicked');
            const newSeed = Math.floor(Math.random() * 1000000);
            init(newSeed);
        });
    }
}

// Fetch configuration from server
function fetchConfig() {
    // Try to get game ID from the HTML
    const gameIdElement = document.getElementById('game-id');
    if (gameIdElement && gameIdElement.textContent) {
        gameId = gameIdElement.textContent;
    }

    // If not found in HTML, try URL parameters
    if (!gameId) {
        const urlParams = new URLSearchParams(window.location.search);
        gameId = urlParams.get('id');
    }

    // Check if test mode is enabled
    const urlParams = new URLSearchParams(window.location.search);
    isTestMode = urlParams.get('test') === 'true';

    console.log('Test mode:', isTestMode);

    // If no game ID is provided, create a new game
    if (!gameId) {
        // Start a new game
        fetch('/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                seed: Math.floor(Math.random() * 1000000),
                test_mode: isTestMode
            })
        })
        .then(response => response.json())
        .then(data => {
            gameId = data.id;
            seed = data.seed;

            // Update the game ID display
            if (gameIdElement) {
                gameIdElement.textContent = gameId;
            }

            // Initialize the game with the received data
            console.log('Game created, initializing with ID:', gameId);
            init();
        })
        .catch(error => {
            console.error('Error starting game:', error);
        });
    } else {
        // Initialize the game directly
        console.log('Initializing game, test mode:', isTestMode);
        init();
    }
}

// This function has been removed as all game states are now provided upfront by the /start endpoint
// The init() function is called directly when needed

// Initialize when the DOM is fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM fully loaded');
    initDOMReferences();
    fetchConfig();
});

// Initialize the game
function init(customSeed = null) {
    // Clean up previous game state
    cleanupGameState();

    // Clear the grid more efficiently
    gameGrid.innerHTML = '';
    cellElements = [];
    lastGrid = null;

    // Update UI
    statusIndicator.classList.remove('hidden');
    statusDisplay.textContent = 'Starting...';
    statusDisplay.className = '';

    // Set CSS variable for pixel size
    document.documentElement.style.setProperty('--pixel-size', `${config.pixel_size || 10}px`);

    // If in test mode, trigger a test simulation
    if (isTestMode) {
        fetch('/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                seed: customSeed || seed,
                id: gameId
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Update game ID if a new one was created
            if (data.id && data.id !== gameId) {
                gameId = data.id;
                const gameIdElement = document.getElementById('game-id');
                if (gameIdElement) {
                    gameIdElement.textContent = gameId;
                }
            }

            seedDisplay.textContent = data.seed;
            config = data.config;
            startSimulation();
        })
        .catch(error => {
            console.error('Error starting test simulation:', error);
            statusDisplay.textContent = 'Error starting simulation';
            statusDisplay.className = 'error';
        });
    } else {
        // Start the game on the server
        fetch('/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                seed: customSeed || seed,
                id: gameId
            })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            // Update game ID if a new one was created
            if (data.id && data.id !== gameId) {
                gameId = data.id;
                const gameIdElement = document.getElementById('game-id');
                if (gameIdElement) {
                    gameIdElement.textContent = gameId;
                }
            }

            seedDisplay.textContent = data.seed;
            isRunning = true;
            gameEnded = false;
            statusDisplay.textContent = 'Running';
            startButton.textContent = 'Restart Game';

            // Store the configuration
            config = data.config;

            // Process grid states received from the server
            if (data.grid_states && data.grid_states.length > 0) {
                // Clear any existing grid states
                gridStates = [];

                // Efficiently add the grid states
                gridStates = data.grid_states;
                currentGridStateIndex = 0;
                totalGridStates = data.total_states || gridStates.length;

                // Set the time to display the first grid state
                if (gridStates.length > 1) {
                    const now = Date.now();
                    const firstState = gridStates[0];

                    // Update the grid with the first state
                    grid = firstState.grid;
                    drawGrid();

                    // Set the time for the next state based on display_time
                    nextGridStateTime = now + (firstState.display_time || 1000);

                    // Move to the next state
                    currentGridStateIndex = 1;

                    console.log(`Received ${gridStates.length} grid states from server. Starting playback.`);

                    // Start the update loop
                    updateLoop();
                }
            } else {
                console.error('No grid states received from server');
                statusDisplay.textContent = 'Error: No grid states received';
                statusDisplay.className = 'error';
            }
        })
        .catch(error => {
            console.error('Error starting game:', error);
            statusDisplay.textContent = 'Error starting game';
            statusDisplay.className = 'error';
        });
    }
}

// Start a simulation with the given parameters
function startSimulation() {
    if (simulationInProgress) return;

    simulationInProgress = true;
    statusDisplay.textContent = 'Simulating...';

    // Get simulation parameters from the server
    fetch('/simulate?id=' + gameId)
        .then(response => response.json())
        .then(data => {
            // Run the simulation in the browser
            const results = runSimulation(data);

            // Submit the results back to the server
            return fetch('/simulate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    ...results,
                    id: gameId
                })
            });
        })
        .then(response => response.json())
        .then(data => {
            // Update the UI with the results
            simulationInProgress = false;
            stepsDisplay.textContent = data.steps;
            dustbunniesDisplay.textContent = data.dustbunnies_awarded;
            statusDisplay.textContent = 'Completed';

            // Show the end reason
            if (data.end_reason === 'dead') {
                statusDisplay.textContent += ': All Cells Dead';
            } else if (data.end_reason === 'loop') {
                statusDisplay.textContent += ': Pattern Loop Detected';
            } else if (data.end_reason === 'timeout') {
                statusDisplay.textContent += ': Time Limit Reached';
            }
        })
        .catch(error => {
            console.error('Error in simulation:', error);
            simulationInProgress = false;
            statusDisplay.textContent = 'Error';
        });
}

// Run a simulation with the given parameters
function runSimulation(params) {
    console.log("Starting simulation with parameters:", params);

    // Extract parameters
    const config = params.config;
    const seed = params.seed;
    const testMode = params.test_mode;

    // Initialize random number generator with seed if provided
    let rng = function() { return Math.random(); };
    if (seed !== null && seed !== undefined) {
        // Simple seeded random number generator
        let s = seed;
        rng = function() {
            s = Math.sin(s) * 10000;
            return s - Math.floor(s);
        };
    }

    // Calculate grid dimensions
    const gridWidth = Math.floor(config.width / config.pixel_size);
    const gridHeight = Math.floor(config.height / config.pixel_size);

    // Initialize grid with ~25% live cells
    let grid = [];
    for (let y = 0; y < gridHeight; y++) {
        grid[y] = [];
        for (let x = 0; x < gridWidth; x++) {
            grid[y][x] = rng() < 0.25 ? 2 : 0; // Use state 2 for live cells to match server-side implementation
        }
    }

    // Initialize simulation variables
    let steps = 0;
    let history = [];
    history.push(JSON.stringify(grid));
    let startTime = Date.now();
    let lastSpeedUp = Date.now();
    let speedMultiplier = 1;
    let dustbunniesAwarded = 0;
    let endReason = null;

    // Run the simulation
    while (true) {
        // Check if we should speed up
        const now = Date.now();
        const elapsed = (now - startTime) / 1000;
        const sinceLastSpeedup = (now - lastSpeedUp) / 1000;

        // Speed up if needed
        if (sinceLastSpeedup >= config.speed_up_interval) {
            speedMultiplier *= 1.5;
            lastSpeedUp = now;
            console.log(`Speed up! Multiplier now ${speedMultiplier}`);
        }

        // Update the grid
        const [newGrid, willBeCreated, willBeDestroyed] = updateGrid(grid);
        grid = newGrid;
        steps++;

        // Award dustbunnies
        dustbunniesAwarded += config.dustbunnies_per_second;

        // Add to history and check for stability
        const gridString = JSON.stringify(grid);
        history.push(gridString);
        if (history.length > 20) {
            history.shift();
        }

        // Check for stability or timeout
        const [isStable, stabilityReason] = checkStability(grid, history);
        if (isStable || elapsed >= config.max_duration) {
            // Game is ending
            if (isStable) {
                endReason = stabilityReason;
            } else {
                endReason = 'timeout';
            }
            console.log(`Simulation ending after ${elapsed.toFixed(2)} seconds. Reason: ${endReason}`);
            break;
        }
    }

    // Return the results
    return {
        steps: steps,
        dustbunnies_awarded: Math.floor(dustbunniesAwarded),
        end_reason: endReason
    };
}

// Update the grid according to Game of Life rules
function updateGrid(grid) {
    const height = grid.length;
    const width = grid[0].length;

    // Create new grid and arrays for cells that will be created/destroyed
    let newGrid = Array(height).fill().map(() => Array(width).fill(0));
    let willBeCreated = Array(height).fill().map(() => Array(width).fill(0));
    let willBeDestroyed = Array(height).fill().map(() => Array(width).fill(0));

    // Count neighbors for each cell
    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
            let neighbors = 0;

            // Check all 8 neighboring cells
            for (let dy = -1; dy <= 1; dy++) {
                for (let dx = -1; dx <= 1; dx++) {
                    if (dx === 0 && dy === 0) continue;

                    // Handle wrapping around edges
                    const nx = (x + dx + width) % width;
                    const ny = (y + dy + height) % height;

                    // Check for live cells (value 1 or 2)
                    if (grid[ny][nx] === 1 || grid[ny][nx] === 2) {
                        neighbors++;
                    }
                }
            }

            // Apply Game of Life rules
            // Use state 2 for live cells to match server-side implementation
            if (grid[y][x] === 1 || grid[y][x] === 2) {
                // Live cell
                if (neighbors === 2 || neighbors === 3) {
                    // Survival
                    newGrid[y][x] = 2; // Use state 2 for live cells
                } else {
                    // Death
                    willBeDestroyed[y][x] = 1;
                }
            } else {
                // Dead cell
                if (neighbors === 3) {
                    // Birth
                    newGrid[y][x] = 2; // Use state 2 for live cells
                    willBeCreated[y][x] = 1;
                }
            }
        }
    }

    return [newGrid, willBeCreated, willBeDestroyed];
}

// Check if the grid is stable (repeating pattern or all dead)
function checkStability(grid, history) {
    // Check if all cells are dead
    let allDead = true;
    for (let y = 0; y < grid.length; y++) {
        for (let x = 0; x < grid[0].length; x++) {
            // Check for any live cells (state 1 or 2)
            if (grid[y][x] === 1 || grid[y][x] === 2) {
                allDead = false;
                break;
            }
        }
        if (!allDead) break;
    }

    if (allDead) {
        return [true, 'dead'];
    }

    // Check for repeating patterns
    // We only consider it a loop if the pattern repeats after at least 2 full steps
    // Each full step consists of 6 substeps, but in the client-side simulation,
    // we only store the grid state at the end of each full step in the history
    const minStepsForLoop = 2; // Minimum number of full steps to consider a loop
    const currentGridString = JSON.stringify(grid);

    // Only check for loops if we have enough history
    if (history.length >= minStepsForLoop + 1) { // +1 because we need at least one more step to compare with
        for (let i = 0; i < history.length - minStepsForLoop; i++) {
            if (history[i] === currentGridString) {
                return [true, 'loop'];
            }
        }
    }

    return [false, null];
}

// Variables to track timing
let lastTimestamp = 0;
let serverUpdateInterval = 2000; // Default 2 seconds in ms
let lastGridUpdate = Date.now();
let pendingUpdate = false;

// Variables for pre-calculated grid states
let gridStates = []; // Array to store pre-calculated grid states
let currentGridStateIndex = 0; // Index of the current grid state being displayed
let nextGridStateTime = null; // Time to display the next grid state
let totalGridStates = 0; // Total number of grid states to display

// Update loop to play back all grid states
function updateLoop() {
    if (!isRunning) return;

    const now = Date.now();

    // Check if we have pre-calculated grid states to display
    if (gridStates.length > 0 && currentGridStateIndex < gridStates.length) {
        // If it's time to display the next grid state
        if (nextGridStateTime && now >= nextGridStateTime) {
            // Get the next grid state
            const gridState = gridStates[currentGridStateIndex];

            // Update the grid - directly assign the grid state to avoid deep copying
            grid = gridState.grid;

            // Batch DOM updates to reduce layout thrashing
            // Prepare all text content updates
            let speedText = gridState.speed_multiplier ? gridState.speed_multiplier.toFixed(1) + 'x' : speedDisplay.textContent;
            let timeText = gridState.elapsed_time !== undefined ? gridState.elapsed_time.toFixed(1) + 's' : timeDisplay.textContent;
            let stepsText = gridState.steps !== undefined ? gridState.steps.toString() : stepsDisplay.textContent;
            let dustbunniesText = gridState.dustbunnies_awarded !== undefined ? gridState.dustbunnies_awarded.toFixed(0) : dustbunniesDisplay.textContent;
            let statusText = statusDisplay.textContent;
            let statusClass = statusDisplay.className;

            // Check if the game is in ending state
            if (gridState.ending) {
                statusText = 'Ending: ';

                // Show reason for ending
                if (gridState.end_reason === 'dead') {
                    statusText += 'All Cells Dead';
                } else if (gridState.end_reason === 'loop') {
                    statusText += 'Pattern Loop Detected';
                } else if (gridState.end_reason === 'timeout') {
                    statusText += 'Time Limit Reached';
                }

                statusClass = 'ending';
            }

            // Check if the game is over
            if (gridState.game_over || (gridState.running === false && gridState.ending === false)) {
                isRunning = false;
                gameEnded = true;
                statusText = 'Game Over';
                statusClass = 'ended';
            }

            // Apply all DOM updates at once
            speedDisplay.textContent = speedText;
            timeDisplay.textContent = timeText;
            stepsDisplay.textContent = stepsText;
            dustbunniesDisplay.textContent = dustbunniesText;
            statusDisplay.textContent = statusText;
            statusDisplay.className = statusClass;

            // Show/hide game over overlay
            if (gameEnded) {
                gameOverDisplay.classList.remove('hidden');
            } else {
                gameOverDisplay.classList.add('hidden');
            }

            // Draw the grid
            drawGrid();

            // Update steps display in test mode
            if (isTestMode) {
                stepsDisplay.textContent = `${currentGridStateIndex} / ${totalGridStates}`;
            }

            // Memory management: remove processed grid states to free up memory
            // Keep a minimal buffer of recent states
            const bufferSize = 5; // Reduced buffer size to save memory
            if (currentGridStateIndex > bufferSize) {
                // Remove old states that are no longer needed
                gridStates.splice(0, currentGridStateIndex - bufferSize);
                // Adjust the current index to account for the removed states
                currentGridStateIndex = bufferSize;

                // Force garbage collection hint (not guaranteed but can help)
                if (window.gc) {
                    window.gc();
                }
            }

            // Move to the next grid state
            currentGridStateIndex++;

            // If we have more grid states, schedule the next one
            if (currentGridStateIndex < gridStates.length) {
                // Use the display_time property if available, otherwise calculate based on timestamps
                let timeToNextState;
                const currentState = gridStates[currentGridStateIndex - 1];

                if (currentState.display_time !== undefined) {
                    timeToNextState = currentState.display_time;
                } else {
                    const nextState = gridStates[currentGridStateIndex];
                    timeToNextState = (nextState.timestamp - currentState.timestamp) * 1000;
                }

                nextGridStateTime = now + timeToNextState;

                // Use requestAnimationFrame for smoother animation when the time is short
                if (timeToNextState < 50) {
                    requestAnimationFrame(updateLoop);
                } else {
                    // Otherwise use setTimeout with a cap on the delay
                    // Store the timeout ID so it can be canceled if needed
                    window.updateLoopTimeout = setTimeout(updateLoop, Math.min(timeToNextState, 50));
                }
            } else {
                // We've displayed all states, including the game over state
                // Notify the server that playback is complete
                notifyPlaybackComplete();
            }
            return;
        } else if (nextGridStateTime) {
            // Wait until it's time to display the next grid state
            const timeToWait = nextGridStateTime - now;

            // Use requestAnimationFrame for smoother animation when the time is short
            if (timeToWait < 50) {
                requestAnimationFrame(updateLoop);
            } else {
                // Otherwise use setTimeout with a cap on the delay
                // Store the timeout ID so it can be canceled if needed
                window.updateLoopTimeout = setTimeout(updateLoop, Math.min(timeToWait, 50));
            }
            return;
        }
    }

    // If we don't have any grid states, log an error
    console.error('No grid states available for playback');
}

// Function to notify the server that playback is complete
function notifyPlaybackComplete() {
    // Only notify if we're not already waiting for a response and the game has ended
    if (!pendingUpdate && gameEnded) {
        pendingUpdate = true;
        console.log('Notifying server that playback is complete');

        fetch('/playback_complete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                id: gameId
            })
        })
        .then(response => response.json())
        .then(data => {
            pendingUpdate = false;

            if (data.error) {
                console.error(data.error);
                return;
            }

            console.log('Server acknowledged playback completion');
        })
        .catch(error => {
            pendingUpdate = false;
            console.error('Error notifying playback complete:', error);

            // Retry after a delay
            window.notifyPlaybackTimeout = setTimeout(notifyPlaybackComplete, 5000);
        });
    } else if (!gameEnded) {
        console.error('Attempted to notify playback complete before game ended');
    } else {
        // If we're already waiting for a response, check again soon
        window.notifyPlaybackTimeout = setTimeout(notifyPlaybackComplete, 1000);
    }
}

// This function has been removed as all game states are now provided upfront by the /start endpoint

// Variable to track the previous grid state for comparison
let lastGrid = null;

// Function to clean up game state and free memory
function cleanupGameState() {
    // Clear grid states array to free memory
    gridStates = [];
    currentGridStateIndex = 0;

    // Reset game state variables
    grid = [];
    lastGrid = null; // Reset lastGrid to ensure proper initialization with new grid
    isRunning = false;
    gameEnded = false;
    nextGridStateTime = null;

    // Cancel any pending timeouts or animation frames
    // This helps prevent multiple update loops running simultaneously
    if (window.updateLoopTimeout) {
        clearTimeout(window.updateLoopTimeout);
        window.updateLoopTimeout = null;
    }

    // Clear any notification timeouts
    if (window.notifyPlaybackTimeout) {
        clearTimeout(window.notifyPlaybackTimeout);
        window.notifyPlaybackTimeout = null;
    }

    // Reset UI elements
    if (gameOverDisplay) {
        gameOverDisplay.classList.add('hidden');
    }

    // Force garbage collection hint (not guaranteed but can help)
    if (window.gc) {
        window.gc();
    }
}

// Draw the grid using HTML elements
function drawGrid() {
    if (!grid || !grid.length) return;

    const rows = grid.length;
    const cols = grid[0].length;

    // Initialize lastGrid if it's null - use a direct reference for better performance
    if (lastGrid === null) {
        lastGrid = grid;
    }

    // Create cells if they don't exist yet
    if (cellElements.length === 0) {
        // Set the grid dimensions
        gameGrid.style.width = `${cols * config.pixel_size}px`;
        gameGrid.style.height = `${rows * config.pixel_size}px`;

        // Create a cell for each position in the grid
        for (let y = 0; y < rows; y++) {
            cellElements[y] = [];
            for (let x = 0; x < cols; x++) {
                const cell = document.createElement('div');
                cell.className = 'cell';
                cell.style.gridRow = y + 1;
                cell.style.gridColumn = x + 1;
                gameGrid.appendChild(cell);
                cellElements[y][x] = cell;
            }
        }
    }

    // Update only cells that have changed
    for (let y = 0; y < rows; y++) {
        for (let x = 0; x < cols; x++) {
            const cellState = grid[y][x];
            const previousState = lastGrid[y][x];

            // Only update if the state has changed
            if (cellState !== previousState) {
                const cell = cellElements[y][x];

                // Simplified class assignment based only on current state
                let newClass = '';

                if (cellState === 0) {
                    newClass = 'cell-off';
                }
                else if (cellState === 2) {
                    newClass = 'cell-normal';
                }
                // For backward compatibility, handle states 1 and 3 if they appear
                else if (cellState === 1) {
                    newClass = 'cell-normal';
                }
                else if (cellState === 3) {
                    newClass = 'cell-off';
                }

                // Only update the DOM if the class needs to change
                if (newClass && !cell.classList.contains(newClass)) {
                    // Remove only the necessary classes
                    cell.classList.remove('cell-off', 'cell-normal');
                    // Add the new class
                    cell.classList.add(newClass);
                }
            }
        }
    }

    // Update lastGrid with current grid values - use a direct reference for better performance
    lastGrid = grid;

    // Show game over overlay if the game has ended
    if (gameEnded) {
        gameOverDisplay.classList.remove('hidden');
    } else {
        gameOverDisplay.classList.add('hidden');
    }
}

// Test mode initialization is now handled in the DOMContentLoaded event listener
