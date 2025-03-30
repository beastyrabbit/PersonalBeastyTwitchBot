import os
import subprocess
import signal
import sys
import atexit

# Dictionary to keep track of running subprocesses by command name
running_processes = {}

def execute_command(command_name, action):
    """
    Finds and manages a Python file from the 'commands' subfolder (and subfolders).
    
    Args:
        command_name (str): Name of the Python file to execute (without .py extension)
        action (str): Action to perform on the process - "start", "stop", or "restart"
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Validate the action parameter
    if action not in ["start", "stop", "restart"]:
        print(f"Error: Invalid action '{action}'. Must be 'start', 'stop', or 'restart'")
        return False
    
    # Handle stop and restart actions for an already running process
    if action in ["stop", "restart"] and command_name in running_processes:
        process = running_processes[command_name]
        if process.poll() is None:  # Check if process is still running
            try:
                process.terminate()
                # Give it some time to terminate gracefully
                process.wait(timeout=3)
                print(f"Stopped process '{command_name}'")
            except subprocess.TimeoutExpired:
                print(f"Process '{command_name}' did not terminate, forcing kill...")
                process.kill()
            except Exception as e:
                print(f"Error terminating process '{command_name}': {str(e)}")
                return False
        
        # Remove from running processes dictionary
        del running_processes[command_name]
        
        # If we're just stopping (not restarting), we're done
        if action == "stop":
            return True
    
    # If we're starting or restarting, find and execute the command file
    if action in ["start", "restart"]:
        # Get the path to the commands directory
        commands_dir = os.path.join(os.getcwd(), "commands")
        
        # Check if the commands directory exists
        if not os.path.isdir(commands_dir):
            print(f"Error: 'commands' directory not found in {os.getcwd()}")
            return False
        
        # Find the command file by recursively searching directories
        command_file_path = None
        for root, _, files in os.walk(commands_dir):
            for file in files:
                # Check if the filename without extension matches the command_name
                if file.endswith(".py") and file[:-3] == command_name:
                    command_file_path = os.path.join(root, file)
                    break
            if command_file_path:
                break
        
        # Check if the command file was found
        if command_file_path is None:
            print(f"Error: Command file '{command_name}.py' not found in commands directory")
            return False
        
        try:
            # Execute the command file as a subprocess
            process = subprocess.Popen(
                [sys.executable, command_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Add the process to our tracking dictionary
            running_processes[command_name] = process
            
            print(f"Started process '{command_name}'")
            return True
        
        except Exception as e:
            print(f"Error executing '{command_name}.py': {str(e)}")
            return False
    
    return False

def cleanup_subprocesses():
    """
    Terminates all running subprocesses.
    This function is called automatically when the main script exits.
    """
    print("Cleaning up subprocesses...")
    for command_name, process in list(running_processes.items()):
        if process.poll() is None:  # Check if process is still running
            try:
                print(f"Terminating subprocess '{command_name}'...")
                process.terminate()
                # Give it some time to terminate gracefully
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                print(f"Subprocess '{command_name}' did not terminate, forcing kill...")
                process.kill()
            except Exception as e:
                print(f"Error terminating subprocess '{command_name}': {str(e)}")

# Register the cleanup function to run when the script exits
atexit.register(cleanup_subprocesses)

# Set up signal handlers to catch interruptions and termination signals
def signal_handler(sig, frame):
    print(f"Received signal {sig}, cleaning up and exiting")
    cleanup_subprocesses()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Handle Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Handle termination

# Example usage:
# execute_command("my_command", "start")  # Start the process
# execute_command("my_command", "stop")   # Stop the process
# execute_command("my_command", "restart") # Restart the process