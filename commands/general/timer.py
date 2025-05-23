import json
import threading

from module.message_utils import send_system_message_to_redis, send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning
from module.shared_redis import redis_client, pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.timer')
pubsub.subscribe('twitch.command.countdown')
pubsub.subscribe('twitch.command.clock')

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def timer_callback(message, command, timer_type, username, time_name, time_value):
    """
    Callback function for timer events.

    Args:
        message (str): The message to send
        command (str): The command name
        timer_type (str): The type of timer event (halfway, two_minutes, completed)
        username (str): The username who set the timer
        time_name (str): The name of the timer
        time_value (int): The original timer value in minutes
    """
    try:
        log_info(f"Timer event: {timer_type}", "timer", {
            "user": username,
            "timer_name": time_name,
            "timer_value": time_value,
            "event_type": timer_type
        })
        send_message_to_redis(message, command)
    except Exception as e:
        error_msg = f"Error in timer callback: {e}"
        log_error(error_msg, "timer", {
            "error": str(e),
            "timer_type": timer_type,
            "username": username,
            "time_name": time_name
        })
        print(error_msg)

def setup_timer(username, time_name, time_in_minutes):
    """
    Set up a timer with notifications.

    Args:
        username (str): The username who set the timer
        time_name (str): The name of the timer
        time_in_minutes (int): The timer duration in minutes

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        log_info(f"Setting up timer for {username}", "timer", {
            "user": username,
            "timer_name": time_name,
            "timer_minutes": time_in_minutes
        })

        time_in_seconds = time_in_minutes * 60

        # Inform the chat about the timer being set
        send_message_to_redis(f'{time_name.capitalize()} Timer set for {time_in_minutes} minute(s) 🤖 !', command="timer")

        # Half point if time is longer than 25 minutes
        if time_in_seconds > 1500:
            log_debug(f"Setting up halfway notification for {time_name} timer", "timer")
            halfway_msg = f'@{username} your {time_name.capitalize()} Timer has halfway done! 🚨'
            threading.Timer(
                time_in_seconds / 2, 
                timer_callback, 
                args=[halfway_msg, "timer", "halfway", username, time_name, time_in_minutes]
            ).start()

        # 2 min left on timer
        if time_in_seconds > 120:  # Only if timer is longer than 2 minutes
            log_debug(f"Setting up 2-minute warning for {time_name} timer", "timer")
            two_min_msg = f'@{username} your {time_name.capitalize()} Timer has 2 minutes left! 🚨'
            threading.Timer(
                time_in_seconds - 120, 
                timer_callback, 
                args=[two_min_msg, "timer", "two_minutes", username, time_name, time_in_minutes]
            ).start()

        # Notify the chat that the timer is up
        log_debug(f"Setting up completion notification for {time_name} timer", "timer")
        completion_msg = f'@{username} your {time_name.capitalize()} Timer is up! 🚨'
        threading.Timer(
            time_in_seconds, 
            timer_callback, 
            args=[completion_msg, "timer", "completed", username, time_name, time_in_minutes]
        ).start()

        return True

    except Exception as e:
        error_msg = f"Error setting up timer: {e}"
        log_error(error_msg, "timer", {
            "error": str(e),
            "username": username,
            "time_name": time_name,
            "time_in_minutes": time_in_minutes
        })
        print(error_msg)
        return False

##########################
# Main
##########################
# Send startup message
log_startup("Timer command is ready to be used", "timer")
send_system_message_to_redis("Timer command is running", "timer")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content', '')
            print(f"Chat Command: {command} and Message: {content}")

            log_info(f"Received {command} command", "timer", {"content": content})

            # Parse timer parameters
            content_parts = content.split()
            username = message_obj["author"]["mention"]

            # Check if we have enough parameters
            if len(content_parts) < 3:
                log_warning(f"Invalid timer command format from {username}", "timer", {
                    "content": content,
                    "expected_format": "!timer <name> <minutes>"
                })
                send_message_to_redis(f"Invalid time value. Please specify the time in minutes (e.g., !timer focus 5).")
                continue

            time_name = content_parts[1]

            # Parse time value
            try:
                time_in_minutes = int(content_parts[2])
                if time_in_minutes <= 0:
                    raise ValueError("Time must be positive")
            except ValueError as e:
                log_warning(f"Invalid time value from {username}: {content_parts[2]}", "timer")
                send_message_to_redis(f"Invalid time value. Please specify a positive number of minutes.")
                continue

            # Set up the timer
            setup_timer(username, time_name, time_in_minutes)

        except Exception as e:
            error_msg = f"Error processing timer command: {e}"
            print(error_msg)
            # Log the error with detailed information
            log_error(error_msg, "timer", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
            send_system_message_to_redis(f"Error in timer command: {str(e)}", "timer")
