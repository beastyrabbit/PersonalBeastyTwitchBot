#!/usr/bin/env python3
"""
Game of Life Benchmark Script

This script benchmarks the Game of Life simulation with different parameter configurations.
It measures performance metrics such as calculation time, number of steps, memory usage, and CPU usage.
The results can be used to fine-tune the parameters, especially speed scaling.

Usage:
    python benchmark.py [--grid-sizes] [--speed-multipliers] [--speed-up-intervals] [--max-durations]

Example:
    python benchmark.py --grid-sizes 10,20,30 --speed-multipliers 1,1.5,2 --speed-up-intervals 5,10,15 --max-durations 60,120,180
"""

import time
import argparse
import numpy as np
import matplotlib.pyplot as plt
import psutil
import os
import pandas as pd
from datetime import datetime, timedelta

# Import Game of Life modules
from commands.games.GOL.models import DEFAULT_CONFIG, create_game_state
from commands.games.GOL.game_logic import initialize_grid, update_grid, is_stable

def run_simulation(config, seed=None):
    """
    Run a Game of Life simulation with the given configuration.
    
    Args:
        config: A dictionary containing the simulation configuration.
        seed: A random seed for reproducibility.
        
    Returns:
        A dictionary containing the simulation results.
    """
    # Create a game state
    game_state = create_game_state()
    game_state['config'] = config.copy()
    game_state['seed'] = seed
    
    # Initialize the grid
    grid = initialize_grid(
        game_state['config']['width'],
        game_state['config']['height'],
        seed
    )
    game_state['grid'] = grid
    
    # Set up the game state
    game_state['running'] = True
    game_state['ending'] = False
    game_state['end_reason'] = None
    game_state['end_time'] = None
    game_state['start_time'] = datetime.now()
    game_state['last_speed_up'] = datetime.now()
    game_state['speed_multiplier'] = 1
    game_state['history'] = [game_state['grid'].copy()]
    game_state['dustbunnies_awarded'] = 0
    game_state['steps'] = 0
    game_state['game_phase'] = 0
    
    # Start measuring performance
    start_time = time.time()
    process = psutil.Process(os.getpid())
    start_memory = process.memory_info().rss / 1024 / 1024  # Memory in MB
    
    # Calculate all steps until the game ends
    now = datetime.now()
    game_over = False
    all_grid_states = []
    
    # Store initial state
    all_grid_states.append({
        'grid': grid.tolist(),
        'game_phase': game_state['game_phase'],
        'timestamp': now.timestamp(),
        'speed_multiplier': game_state['speed_multiplier'],
        'steps': game_state['steps'],
        'elapsed_time': 0
    })
    
    # Calculate all steps until the game ends
    while not game_over:
        # Check if we should speed up
        if game_state['start_time'] is not None:
            elapsed = (now - game_state['start_time']).total_seconds()
            since_last_speedup = (now - game_state['last_speed_up']).total_seconds()
            
            # Speed up if needed
            if since_last_speedup >= game_state['config']['speed_up_interval']:
                game_state['speed_multiplier'] *= 1.5
                game_state['last_speed_up'] = now
        
        # Process a normal Game of Life step
        final_grid, _, _ = update_grid(game_state['grid'])
        game_state['grid'] = final_grid
        game_state['steps'] += 1
        
        # Add to history and check for stability
        game_state['history'].append(game_state['grid'].copy())
        if len(game_state['history']) > 20:
            game_state['history'].pop(0)
        
        # Check for stability or timeout
        elapsed = (now - game_state['start_time']).total_seconds()
        is_stable_result, stability_reason = is_stable(game_state['grid'], game_state['history'])
        
        if is_stable_result or elapsed >= game_state['config']['max_duration']:
            # Game is entering ending state
            game_state['ending'] = True
            game_state['end_time'] = now
            
            # Set the end reason
            if is_stable_result:
                game_state['end_reason'] = stability_reason
            else:
                game_state['end_reason'] = 'timeout'
            
            # Mark that we'll need to add the ending state
            game_over = True
        
        # Add the current state to the grid states array
        now = now + timedelta(milliseconds=1000 / game_state['speed_multiplier'])
        elapsed = (now - game_state['start_time']).total_seconds()
        
        all_grid_states.append({
            'grid': game_state['grid'].tolist(),
            'game_phase': game_state['game_phase'],
            'timestamp': now.timestamp(),
            'speed_multiplier': game_state['speed_multiplier'],
            'steps': game_state['steps'],
            'elapsed_time': elapsed,
            'ending': game_state['ending'],
            'end_reason': game_state['end_reason']
        })
    
    # End measuring performance
    end_time = time.time()
    end_memory = process.memory_info().rss / 1024 / 1024  # Memory in MB
    
    # Calculate performance metrics
    calculation_time = end_time - start_time
    memory_usage = end_memory - start_memory
    
    return {
        'config': config,
        'seed': seed,
        'steps': game_state['steps'],
        'end_reason': game_state['end_reason'],
        'calculation_time': calculation_time,
        'memory_usage': memory_usage,
        'grid_states_count': len(all_grid_states),
        'final_speed_multiplier': game_state['speed_multiplier']
    }

def benchmark_grid_sizes(sizes, config=None, seed=None):
    """
    Benchmark different grid sizes.
    
    Args:
        sizes: A list of pixel sizes to benchmark.
        config: A base configuration to use (default: DEFAULT_CONFIG).
        seed: A random seed for reproducibility.
        
    Returns:
        A list of benchmark results.
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()
    
    results = []
    
    for size in sizes:
        print(f"Benchmarking grid size: {size}")
        test_config = config.copy()
        test_config['pixel_size'] = size
        
        # Calculate grid dimensions
        grid_width = test_config['width'] // size
        grid_height = test_config['height'] // size
        print(f"  Grid dimensions: {grid_width}x{grid_height}")
        
        result = run_simulation(test_config, seed)
        results.append(result)
        
        print(f"  Steps: {result['steps']}")
        print(f"  Calculation time: {result['calculation_time']:.2f} seconds")
        print(f"  Memory usage: {result['memory_usage']:.2f} MB")
        print(f"  End reason: {result['end_reason']}")
        print()
    
    return results

def benchmark_speed_multipliers(multipliers, config=None, seed=None):
    """
    Benchmark different initial speed multipliers.
    
    Args:
        multipliers: A list of speed multipliers to benchmark.
        config: A base configuration to use (default: DEFAULT_CONFIG).
        seed: A random seed for reproducibility.
        
    Returns:
        A list of benchmark results.
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()
    
    results = []
    
    for multiplier in multipliers:
        print(f"Benchmarking speed multiplier: {multiplier}")
        test_config = config.copy()
        
        # Create a game state with the specified speed multiplier
        game_state = create_game_state()
        game_state['config'] = test_config
        game_state['speed_multiplier'] = multiplier
        
        result = run_simulation(test_config, seed)
        result['initial_speed_multiplier'] = multiplier
        results.append(result)
        
        print(f"  Steps: {result['steps']}")
        print(f"  Calculation time: {result['calculation_time']:.2f} seconds")
        print(f"  Memory usage: {result['memory_usage']:.2f} MB")
        print(f"  Final speed multiplier: {result['final_speed_multiplier']:.2f}")
        print(f"  End reason: {result['end_reason']}")
        print()
    
    return results

def benchmark_speed_up_intervals(intervals, config=None, seed=None):
    """
    Benchmark different speed-up intervals.
    
    Args:
        intervals: A list of speed-up intervals to benchmark.
        config: A base configuration to use (default: DEFAULT_CONFIG).
        seed: A random seed for reproducibility.
        
    Returns:
        A list of benchmark results.
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()
    
    results = []
    
    for interval in intervals:
        print(f"Benchmarking speed-up interval: {interval}")
        test_config = config.copy()
        test_config['speed_up_interval'] = interval
        
        result = run_simulation(test_config, seed)
        results.append(result)
        
        print(f"  Steps: {result['steps']}")
        print(f"  Calculation time: {result['calculation_time']:.2f} seconds")
        print(f"  Memory usage: {result['memory_usage']:.2f} MB")
        print(f"  Final speed multiplier: {result['final_speed_multiplier']:.2f}")
        print(f"  End reason: {result['end_reason']}")
        print()
    
    return results

def benchmark_max_durations(durations, config=None, seed=None):
    """
    Benchmark different maximum durations.
    
    Args:
        durations: A list of maximum durations to benchmark.
        config: A base configuration to use (default: DEFAULT_CONFIG).
        seed: A random seed for reproducibility.
        
    Returns:
        A list of benchmark results.
    """
    if config is None:
        config = DEFAULT_CONFIG.copy()
    
    results = []
    
    for duration in durations:
        print(f"Benchmarking max duration: {duration}")
        test_config = config.copy()
        test_config['max_duration'] = duration
        
        result = run_simulation(test_config, seed)
        results.append(result)
        
        print(f"  Steps: {result['steps']}")
        print(f"  Calculation time: {result['calculation_time']:.2f} seconds")
        print(f"  Memory usage: {result['memory_usage']:.2f} MB")
        print(f"  Final speed multiplier: {result['final_speed_multiplier']:.2f}")
        print(f"  End reason: {result['end_reason']}")
        print()
    
    return results

def plot_results(results, x_key, y_key, title, xlabel, ylabel):
    """
    Plot benchmark results.
    
    Args:
        results: A list of benchmark results.
        x_key: The key to use for the x-axis.
        y_key: The key to use for the y-axis.
        title: The plot title.
        xlabel: The x-axis label.
        ylabel: The y-axis label.
    """
    x = [result['config'][x_key] if x_key in result['config'] else result[x_key] for result in results]
    y = [result[y_key] for result in results]
    
    plt.figure(figsize=(10, 6))
    plt.plot(x, y, 'o-')
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.grid(True)
    plt.savefig(f"{title.replace(' ', '_').lower()}.png")
    plt.close()

def save_results_to_csv(results, filename):
    """
    Save benchmark results to a CSV file.
    
    Args:
        results: A list of benchmark results.
        filename: The name of the CSV file.
    """
    # Flatten the results for CSV export
    flat_results = []
    for result in results:
        flat_result = result.copy()
        for key, value in result['config'].items():
            flat_result[f"config_{key}"] = value
        del flat_result['config']
        flat_results.append(flat_result)
    
    # Convert to DataFrame and save to CSV
    df = pd.DataFrame(flat_results)
    df.to_csv(filename, index=False)
    print(f"Results saved to {filename}")

def main():
    """Main function to run the benchmark."""
    parser = argparse.ArgumentParser(description='Benchmark Game of Life simulation.')
    parser.add_argument('--grid-sizes', type=str, default='5,10,15,20,25',
                        help='Comma-separated list of pixel sizes to benchmark')
    parser.add_argument('--speed-multipliers', type=str, default='1,1.5,2,2.5,3',
                        help='Comma-separated list of speed multipliers to benchmark')
    parser.add_argument('--speed-up-intervals', type=str, default='5,10,15,20,25',
                        help='Comma-separated list of speed-up intervals to benchmark')
    parser.add_argument('--max-durations', type=str, default='60,120,180,240,300',
                        help='Comma-separated list of maximum durations to benchmark')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility')
    
    args = parser.parse_args()
    
    # Parse command-line arguments
    grid_sizes = [int(size) for size in args.grid_sizes.split(',')]
    speed_multipliers = [float(multiplier) for multiplier in args.speed_multipliers.split(',')]
    speed_up_intervals = [int(interval) for interval in args.speed_up_intervals.split(',')]
    max_durations = [int(duration) for duration in args.max_durations.split(',')]
    seed = args.seed
    
    # Create results directory
    os.makedirs('benchmark_results', exist_ok=True)
    
    # Benchmark grid sizes
    print("Benchmarking grid sizes...")
    grid_size_results = benchmark_grid_sizes(grid_sizes, seed=seed)
    plot_results(grid_size_results, 'pixel_size', 'calculation_time', 
                 'Grid Size vs Calculation Time', 'Pixel Size', 'Calculation Time (s)')
    plot_results(grid_size_results, 'pixel_size', 'memory_usage', 
                 'Grid Size vs Memory Usage', 'Pixel Size', 'Memory Usage (MB)')
    plot_results(grid_size_results, 'pixel_size', 'steps', 
                 'Grid Size vs Steps', 'Pixel Size', 'Steps')
    save_results_to_csv(grid_size_results, 'benchmark_results/grid_size_results.csv')
    
    # Benchmark speed multipliers
    print("\nBenchmarking speed multipliers...")
    speed_multiplier_results = benchmark_speed_multipliers(speed_multipliers, seed=seed)
    plot_results(speed_multiplier_results, 'initial_speed_multiplier', 'calculation_time', 
                 'Speed Multiplier vs Calculation Time', 'Initial Speed Multiplier', 'Calculation Time (s)')
    plot_results(speed_multiplier_results, 'initial_speed_multiplier', 'steps', 
                 'Speed Multiplier vs Steps', 'Initial Speed Multiplier', 'Steps')
    save_results_to_csv(speed_multiplier_results, 'benchmark_results/speed_multiplier_results.csv')
    
    # Benchmark speed-up intervals
    print("\nBenchmarking speed-up intervals...")
    speed_up_interval_results = benchmark_speed_up_intervals(speed_up_intervals, seed=seed)
    plot_results(speed_up_interval_results, 'speed_up_interval', 'calculation_time', 
                 'Speed-up Interval vs Calculation Time', 'Speed-up Interval (s)', 'Calculation Time (s)')
    plot_results(speed_up_interval_results, 'speed_up_interval', 'final_speed_multiplier', 
                 'Speed-up Interval vs Final Speed Multiplier', 'Speed-up Interval (s)', 'Final Speed Multiplier')
    save_results_to_csv(speed_up_interval_results, 'benchmark_results/speed_up_interval_results.csv')
    
    # Benchmark maximum durations
    print("\nBenchmarking maximum durations...")
    max_duration_results = benchmark_max_durations(max_durations, seed=seed)
    plot_results(max_duration_results, 'max_duration', 'calculation_time', 
                 'Max Duration vs Calculation Time', 'Max Duration (s)', 'Calculation Time (s)')
    plot_results(max_duration_results, 'max_duration', 'steps', 
                 'Max Duration vs Steps', 'Max Duration (s)', 'Steps')
    save_results_to_csv(max_duration_results, 'benchmark_results/max_duration_results.csv')
    
    print("\nBenchmarking complete. Results saved to benchmark_results directory.")

if __name__ == '__main__':
    main()