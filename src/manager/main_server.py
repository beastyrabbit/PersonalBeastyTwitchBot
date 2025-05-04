import atexit
import json
import signal
import subprocess
import sys
from git import Repo
import os
import redis

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
redis_client_env = redis.Redis(host='192.168.50.115', port=6379, db=1)
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.system')
pubsub.subscribe('twitch.command.sys')
services_managed = ["brb","unbrb","discord","shoutout","todolist","collect","invest","give","roomba","steal","lurk","points","suika","timer","timezone","unlurk","blackjack","gamble","slots","accept","fight","translate","hug",]
services_managed += ["move_fishing","admin_logger","chat_logger","command_logger"]
manager_service_name = "twitch-manager.service"
running_processes = {}


##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels bofore exiting")
    pubsub.unsubscribe()
    cleanup_subprocesses()
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register signal handlers
signal.signal(signal.SIGINT, handle_exit)   # Handle Ctrl+C
signal.signal(signal.SIGTERM, handle_exit)  # Handle termination

##########################
# Default Message Methods
##########################
def send_admin_message_to_redis(message):
    # Create unified message object
    admin_message_obj = {
        "type": "admin",
        "source": "system",
        "content": message,
    }
    redis_client.publish('admin.brb.send', json.dumps(admin_message_obj))


def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)


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
send_admin_message_to_redis('Bunux is online')
atexit.register(cleanup_subprocesses)
for service in services_managed:
    execute_command(command_name=service, action="start")

for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        if not message_obj["author"]["broadcaster"]:
            send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
            continue
            # sub commands: git pull, start a service, stop a service, restart a service / manager
        if "status" in message_obj["content"]:
            # send a message to the OS to pull the latest code from the git repository
            msg = "git status"
            current_directory = os.getcwd()
            repo = Repo(current_directory)
            status = repo.git.status()
            send_message_to_redis(f"Git Status: {status}")
            # running subprocesses
            running_processes_list = "\n".join([f"{name}: {proc.pid}" for name, proc in running_processes.items()])
            send_message_to_redis(f"Running processes: {running_processes_list}")

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
            restart_manager_service()
        if any(cmd in message_obj["content"] for cmd in ["start", "stop", "restart"]):
            # send a message to the OS to start, stop or restart a service
            action = message_obj["content"].split()[1] if len(message_obj["content"].split()) > 1 else None
            service = message_obj["content"].split()[2] if len(message_obj["content"].split()) > 2 else None
            if service in services_managed:
                execute_command(command_name=service, action=action)
                continue
            if service == "manager":
                restart_manager_service()
                continue
            if service == "all":
                for service in services_managed:
                    execute_command(command_name=service, action=action)
                continue























