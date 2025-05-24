#!/usr/bin/env python3
import os
import subprocess
import sys
import glob

def find_command_path(command_name, commands_dir):
    """
    Find the full path to a command file by recursively searching directories.
    
    Args:
        command_name (str): Name of the Python file to find (without .py extension)
        commands_dir (str): Path to the commands directory
        
    Returns:
        str: Full path to the command file, or None if not found
    """
    for root, _, files in os.walk(commands_dir):
        for file in files:
            if file.endswith(".py") and file[:-3] == command_name:
                return os.path.join(root, file)
    return None

def create_service_file(command_name, command_path, project_dir):
    """
    Create a systemd service file for a command.
    
    Args:
        command_name (str): Name of the command (without .py extension)
        command_path (str): Full path to the command file
        project_dir (str): Path to the project directory
        
    Returns:
        str: Path to the created service file
    """
    service_name = f"twitch-command-{command_name}.service"
    service_path = os.path.join("/etc/systemd/system", service_name)
    
    # Get the Python interpreter path
    python_path = sys.executable
    
    # Create service file content
    service_content = f"""[Unit]
Description=Twitch Bot Command - {command_name}
After=network.target
PartOf=twitch-manager.service

[Service]
Type=simple
User=root
WorkingDirectory={project_dir}
ExecStart={python_path} {command_path}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    
    # Write service file
    with open(service_path, 'w') as f:
        f.write(service_content)
    
    print(f"Created service file: {service_path}")
    return service_path

def setup_services(services_list):
    """
    Set up systemd services for all commands in the services list.
    
    Args:
        services_list (list): List of command names to create services for
        
    Returns:
        list: List of created service names
    """
    # Get project directory
    project_dir = os.getcwd()
    commands_dir = os.path.join(project_dir, "commands")
    
    if not os.path.isdir(commands_dir):
        print(f"Error: 'commands' directory not found in {project_dir}")
        return []
    
    created_services = []
    
    for command_name in services_list:
        # Find command path
        command_path = find_command_path(command_name, commands_dir)
        
        if command_path is None:
            print(f"Warning: Command file '{command_name}.py' not found in commands directory")
            continue
        
        # Create service file
        service_path = create_service_file(command_name, command_path, project_dir)
        service_name = os.path.basename(service_path)
        created_services.append(service_name)
        
        # Reload systemd to recognize the new service
        try:
            subprocess.run(["systemctl", "daemon-reload"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error reloading systemd: {e}")
    
    return created_services

def cleanup_services(current_services):
    """
    Remove systemd services that are no longer needed.
    
    Args:
        current_services (list): List of current service names to keep
        
    Returns:
        list: List of removed service names
    """
    # Get all twitch command services
    service_pattern = "/etc/systemd/system/twitch-command-*.service"
    all_services = glob.glob(service_pattern)
    
    removed_services = []
    
    for service_path in all_services:
        service_name = os.path.basename(service_path)
        
        # Skip if this is a current service
        if service_name in current_services:
            continue
        
        # Stop the service if it's running
        try:
            subprocess.run(["systemctl", "stop", service_name], check=True)
        except subprocess.CalledProcessError:
            # Ignore errors if service is already stopped
            pass
        
        # Disable the service
        try:
            subprocess.run(["systemctl", "disable", service_name], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error disabling service {service_name}: {e}")
        
        # Remove the service file
        try:
            os.remove(service_path)
            removed_services.append(service_name)
            print(f"Removed service file: {service_path}")
        except OSError as e:
            print(f"Error removing service file {service_path}: {e}")
    
    # Reload systemd if any services were removed
    if removed_services:
        try:
            subprocess.run(["systemctl", "daemon-reload"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error reloading systemd: {e}")
    
    return removed_services

def manage_service(service_name, action):
    """
    Manage a systemd service.
    
    Args:
        service_name (str): Name of the service
        action (str): Action to perform (start, stop, restart)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if action not in ["start", "stop", "restart"]:
        print(f"Error: Invalid action '{action}'. Must be 'start', 'stop', or 'restart'")
        return False
    
    try:
        subprocess.run(["systemctl", action, service_name], check=True)
        print(f"Service '{service_name}' {action}ed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error {action}ing service '{service_name}': {e}")
        return False

def get_service_status(service_name):
    """
    Get the status of a systemd service.
    
    Args:
        service_name (str): Name of the service
        
    Returns:
        str: Status of the service (active, inactive, failed, etc.)
    """
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            check=False
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Error getting status for service '{service_name}': {e}")
        return "unknown"

def list_active_services():
    """
    List all active twitch command services.
    
    Returns:
        list: List of active service names
    """
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--state=active", "twitch-command-*.service"],
            capture_output=True,
            text=True,
            check=False
        )
        
        active_services = []
        for line in result.stdout.splitlines():
            if "twitch-command-" in line:
                parts = line.split()
                if parts:
                    active_services.append(parts[0])
        
        return active_services
    except Exception as e:
        print(f"Error listing active services: {e}")
        return []

if __name__ == "__main__":
    # This script can be run directly for testing
    if len(sys.argv) < 2:
        print("Usage: service_manager.py [setup|cleanup|status|start|stop|restart] [service_name]")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == "setup":
        # Example services list
        test_services = ["chat_logger", "command_logger", "system_logger"]
        setup_services(test_services)
    
    elif action == "cleanup":
        # Example current services
        current_services = ["twitch-command-chat_logger.service", "twitch-command-command_logger.service"]
        cleanup_services(current_services)
    
    elif action in ["start", "stop", "restart", "status"]:
        if len(sys.argv) < 3:
            print(f"Error: Service name required for {action} action")
            sys.exit(1)
        
        service_name = sys.argv[2]
        if not service_name.startswith("twitch-command-"):
            service_name = f"twitch-command-{service_name}"
        if not service_name.endswith(".service"):
            service_name = f"{service_name}.service"
        
        if action == "status":
            status = get_service_status(service_name)
            print(f"Service '{service_name}' status: {status}")
        else:
            manage_service(service_name, action)
    
    elif action == "list":
        active_services = list_active_services()
        print("Active services:")
        for service in active_services:
            print(f"  {service}")
    
    else:
        print(f"Error: Unknown action '{action}'")
        sys.exit(1)