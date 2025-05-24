#!/usr/bin/env python3
import atexit
import json
import signal
import subprocess
import sys
import os
import time

from git import Repo
import redis
from module.message_utils import send_admin_message_to_redis, send_message_to_redis
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning

# Add the parent directory to sys.path to allow importing service_manager
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.manager.service_manager import setup_services, cleanup_services, manage_service, get_service_status, list_active_services

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
# Track the live status
is_live = True  # Assume live on startup

# Create a dictionary to map command names to their service names
service_map = {}

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


def start_all_services():
    """
    Start all services with system_logger first, then the rest.
    This ensures that logging is available before other services start.
    """
    log_info("Starting system_logger first", command="system")
    # Start system_logger first
    execute_command(command_name="system_logger", action="start")
    time.sleep(1)

    # Then start all other services
    for service in services_managed:
        if service != "system_logger":
            execute_command(command_name=service, action="start")

    log_info("All services started", command="system")


def initialize_services():
    """
    Initialize systemd services for all commands in services_managed.
    This creates service files and builds the service_map dictionary.
    """
    global service_map

    log_info("Initializing systemd services for all commands", command="system")

    # Set up services for all commands in services_managed
    created_services = setup_services(services_managed)

    # Build the service_map dictionary
    for service_name in created_services:
        # Extract command name from service name (e.g., "twitch-command-brb.service" -> "brb")
        command_name = service_name.replace("twitch-command-", "").replace(".service", "")
        service_map[command_name] = service_name

    # Clean up any services that are no longer needed
    cleanup_services(created_services)

    log_info(f"Initialized {len(created_services)} systemd services", command="system")
    return created_services


def execute_command(command_name, action):
    """
    Manages a command by controlling its systemd service.

    Args:
        command_name (str): Name of the command (without .py extension)
        action (str): Action to perform on the service - "start", "stop", or "restart"

    Returns:
        bool: True if successful, False otherwise
    """
    # Validate the action parameter
    if action not in ["start", "stop", "restart"]:
        print(f"Error: Invalid action '{action}'. Must be 'start', 'stop', or 'restart'")
        return False

    # Get the service name for this command
    if command_name not in service_map:
        # If the service is not in the map, try to create it
        log_info(f"Service for '{command_name}' not found in service map, attempting to create it", command="system")
        created_services = setup_services([command_name])
        if not created_services:
            log_error(f"Failed to create service for '{command_name}'", command="system")
            return False

        service_name = created_services[0]
        service_map[command_name] = service_name
    else:
        service_name = service_map[command_name]

    # Check if we need to start a service that's already running
    if action == "start":
        status = get_service_status(service_name)
        if status == "active":
            log_info(f"Service '{service_name}' is already running, not starting a new instance", command="system")
            return True

    # Manage the service
    result = manage_service(service_name, action)

    if result:
        log_info(f"Successfully {action}ed service '{service_name}'", command="system")
    else:
        log_error(f"Failed to {action} service '{service_name}'", command="system")

    return result


##########################
# Main
##########################
# Send startup messages
log_startup('Bunux is online', command="system")
# Send a message indicating that the system is initially assumed to be live
log_info('System is initially assumed to be LIVE', command="system")

# Initialize systemd services for all commands
initialize_services()

# Start all services since we're assuming the system is live on startup
log_info('Starting all services on startup', command="system")
start_all_services()

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
                start_all_services()
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

                # Get active services
                active_services = list_active_services()
                active_services_list = "\n".join(active_services) if active_services else "No active services"
                send_message_to_redis(f"Active services: {active_services_list}", command="main_server")

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

                # Stop all services before restarting the manager service
                log_info('Stopping all services before restart due to git pull', command="system")
                for service in services_managed:
                    execute_command(command_name=service, action="stop")

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
                    # Stop all services before restarting the manager service
                    log_info('Stopping all services before restart due to manager restart command', command="system")
                    for service in services_managed:
                        execute_command(command_name=service, action="stop")

                    # Now restart the manager service
                    restart_manager_service()
                    continue

                if service == "all":
                    if action == "start":
                        # Use the helper function to ensure system_logger starts first
                        start_all_services()
                    else:
                        # For stop and restart, order doesn't matter
                        for service in services_managed:
                            execute_command(command_name=service, action=action)
                    continue

            # Handle manual live/offline setting
            if "set live" in message_obj["content"]:
                print("Manual override: Setting system to LIVE")
                is_live = True
                # Start all services
                log_info('Starting all services due to manual "set live" command', command="system")
                start_all_services()
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

            # Handle service management commands
            if "check services" in message_obj["content"]:
                # Re-initialize services to ensure all are properly set up
                created_services = initialize_services()
                send_message_to_redis(f"Services checked and initialized. {len(created_services)} services set up.", command="main_server")
                continue

except Exception as e:
    log_error(f"Error in Redis pubsub listen loop: {e}", command="system")
    # Try to exit gracefully
    sys.exit(1)
