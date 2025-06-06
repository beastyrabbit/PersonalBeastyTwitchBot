import atexit
import json
import signal
import subprocess
import sys
from git import Repo
import os
import redis
from module.message_utils import send_admin_message_to_redis, send_message_to_redis
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "WARNING"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client_env = redis.Redis(host='192.168.50.115', port=6379, db=1)
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.system')
pubsub.subscribe('twitch.command.sys')
# Subscribe to user live/offline status channels
pubsub.subscribe('system.user.live')
pubsub.subscribe('system.user.offline')
services_managed =  ["brb","unbrb","discord","shoutout","todolist","collect","invest","give","roomba","steal","lurk","points"]
services_managed += ["suika","timer","timezone","unlurk","blackjack","gamble","slots","accept","fight"]
#services_managed += ["","","gameoflife"]
services_managed += ["translate","hug"]
services_managed += ["move_fishing","system_logger","chat_logger","command_logger"]
manager_service_name = "twitch-manager.service"
running_processes = {}
# Track the live status
is_live = True  # Assume live on startup


##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels before exiting")
    try:
        # Try to unsubscribe gracefully, but don't fail if it doesn't work
        pubsub.unsubscribe()
        print("Successfully unsubscribed from Redis channels")
    except Exception as e:
        print(f"Error unsubscribing from Redis channels: {e}")
    
    # Always clean up subprocesses
    cleanup_subprocesses()
    
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)   # Handle Ctrl+C
signal.signal(signal.SIGTERM, handle_exit)  # Handle termination


##########################
# Helper Functions
##########################
def restart_manager_service():
    """Restart the specified systemd service."""
    try:
        # Spawn a detached process to run the restart command
        subprocess.Popen(
            ['systemctl', 'restart', manager_service_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )
        print(f"Restart command issued for service '{manager_service_name}'.")
    except Exception as e:
        print(f"Failed to issue restart command for service '{manager_service_name}'. Error: {e}")


def cleanup_subprocesses():
    """
    Terminates all running subprocesses.
    This function is called automatically when the main script exits.
    """
    print("Cleaning up subprocesses...")
    global running_processes
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
        else:
            print(f"Subprocess '{command_name}' is already terminated")

        # Remove from running processes dictionary regardless of termination success
        # This ensures we don't keep references to terminated processes
        if command_name in running_processes:
            del running_processes[command_name]

    # Log the cleanup completion
    log_info(f"Cleaned up all processes. Running processes count: {len(running_processes)}", command="system")

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
    global running_processes
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
        # Check if the process is already running when action is "start"
        if action == "start" and command_name in running_processes:
            process = running_processes[command_name]
            if process.poll() is None:  # Process is still running
                log_info(f"Process '{command_name}' is already running with PID {process.pid}, not starting a new instance", command="system")
                return True
            else:
                # Process has terminated, remove it from running_processes
                del running_processes[command_name]
                log_info(f"Removed terminated process '{command_name}' from tracking", command="system")

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



##########################
# Main
##########################
# Send startup messages
log_startup('Bunux is online', command="system")
# Send a message indicating that the system is initially assumed to be live
log_info('System is initially assumed to be LIVE', command="system")
atexit.register(cleanup_subprocesses)
# Start all services since we're assuming the system is live on startup
log_info('Starting all services on startup', command="system")
for service in services_managed:
    execute_command(command_name=service, action="start")

# Main loop with error handling for Redis operations
try:
    log_info('Starting main Redis pubsub listen loop', command="system")
    for message in pubsub.listen():
        if message["type"] == "message":
            # Handle system.user.live and system.user.offline messages
            if message["channel"].decode('utf-8') == 'system.user.live':
                print("Received system.user.live message - Starting all services")
                is_live = True
                # Start all services if they're not already running
                log_info('Starting all services due to system.user.live message', command="system")
                for service in services_managed:
                    execute_command(command_name=service, action="start")
                log_info('System is now LIVE - All services started', command="system")
                continue

            if message["channel"].decode('utf-8') == 'system.user.offline':
                print("Received system.user.offline message - Shutting down all services")
                is_live = False
                # Stop all services
                for service in services_managed:
                    execute_command(command_name=service, action="stop")
                log_info('System is now OFFLINE - All services stopped', command="system")
                continue

            # Handle regular command messages
            message_obj = json.loads(message['data'].decode('utf-8'))
            print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            if not message_obj["author"]["broadcaster"]:
                send_message_to_redis('🚨 Only the broadcaster can use this command 🚨', command="main_server")
                continue
                # sub commands: git pull, start a service, stop a service, restart a service / manager
            if "status" in message_obj["content"]:
                # send a message to the OS to pull the latest code from the git repository
                msg = "git status"
                current_directory = os.getcwd()
                repo = Repo(current_directory)
                status = repo.git.status()
                send_message_to_redis(f"Git Status: {status}", command="main_server")
                # running subprocesses
                running_processes_list = "\n".join([f"{name}: {proc.pid}" for name, proc in running_processes.items()])
                send_message_to_redis(f"Running processes: {running_processes_list}", command="main_server")

            if "git pull" in message_obj["content"]:
                # send a message to the OS to pull the latest code from the git repository
                msg = "git pull origin/master"
                current_directory = os.getcwd()
                repo = Repo(current_directory)
                repo.remotes.origin.pull('master')
                # we need to update the venv that is running under uv
                # Sync environment with uv
                try:
                    subprocess.run(["uv", "sync"], check=True)
                except subprocess.CalledProcessError as e:
                    print(f"uv sync failed: {e}")

                # Clean up all running processes before restarting the manager service
                log_info('Cleaning up all processes before restart due to git pull', command="system")
                cleanup_subprocesses()

                # Now restart the manager service
                restart_manager_service()
            if any(cmd in message_obj["content"] for cmd in ["start", "stop", "restart"]):
                # send a message to the OS to start, stop or restart a service
                action = message_obj["content"].split()[1] if len(message_obj["content"].split()) > 1 else None
                service = message_obj["content"].split()[2] if len(message_obj["content"].split()) > 2 else None
                if service in services_managed:
                    execute_command(command_name=service, action=action)
                    continue
                if service == "manager":
                    # Clean up all running processes before restarting the manager service
                    log_info('Cleaning up all processes before restart due to manager restart command', command="system")
                    cleanup_subprocesses()

                    # Now restart the manager service
                    restart_manager_service()
                    continue
                if service == "all":
                    for service in services_managed:
                        execute_command(command_name=service, action=action)
                    continue

            # Handle manual live/offline setting
            if "set live" in message_obj["content"]:
                print("Manual override: Setting system to LIVE")
                is_live = True
                # Start all services
                log_info('Starting all services due to manual "set live" command', command="system")
                for service in services_managed:
                    execute_command(command_name=service, action="start")
                log_info('Manual override: System is now LIVE - All services started', command="system")
                continue

            if "set offline" in message_obj["content"]:
                print("Manual override: Setting system to OFFLINE")
                is_live = False
                # Stop all services
                for service in services_managed:
                    execute_command(command_name=service, action="stop")
                log_info('Manual override: System is now OFFLINE - All services stopped', command="system")
                continue
except Exception as e:
    log_error(f"Error in Redis pubsub listen loop: {e}", command="system")
    # Clean up before exiting
    cleanup_subprocesses()
    # Try to exit gracefully
    sys.exit(1)