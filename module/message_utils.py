import json
import signal
import sys
import inspect
import os
from datetime import datetime
from module.shared_redis import redis_client, pubsub

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    """Handle graceful exit by unsubscribing from Redis channels.

    @param signum: Signal number
    @param frame: Current stack frame
    """
    print("Unsubscribing from all channels before exiting")
    try:
        pubsub.unsubscribe()
        pubsub.punsubscribe()
    except:
        pass
    sys.exit(0)  # Exit gracefully

def register_exit_handler():
    """Register the SIGINT handler for graceful exit."""
    signal.signal(signal.SIGINT, handle_exit)

##########################
# Logging System
##########################
# Log levels
class LogLevel:
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50
    IMPORTANT = 55  # Level for important notifications
    STARTUP = 60  # Special level for startup messages

    # Map string level names to numeric values
    LEVEL_MAP = {
        "DEBUG": DEBUG,
        "INFO": INFO,
        "WARNING": WARNING,
        "ERROR": ERROR,
        "CRITICAL": CRITICAL,
        "IMPORTANT": IMPORTANT,
        "STARTUP": STARTUP
    }

    @staticmethod
    def get_level(level_name):
        """Convert a string level name to its numeric value.

        @param level_name: The level name to convert
        @return: Numeric log level value
        """
        if isinstance(level_name, int):
            return level_name

        level_name = level_name.upper() if isinstance(level_name, str) else "INFO"
        return LogLevel.LEVEL_MAP.get(level_name, LogLevel.INFO)

    @staticmethod
    def get_level_name(level):
        """Convert a numeric level value to its string name.

        @param level: The numeric log level
        @return: String name of the log level
        """
        if level == LogLevel.DEBUG:
            return "DEBUG"
        elif level == LogLevel.INFO:
            return "INFO"
        elif level == LogLevel.WARNING:
            return "WARNING"
        elif level == LogLevel.ERROR:
            return "ERROR"
        elif level == LogLevel.CRITICAL:
            return "CRITICAL"
        elif level == LogLevel.IMPORTANT:
            return "IMPORTANT"
        elif level == LogLevel.STARTUP:
            return "STARTUP"
        else:
            return f"LEVEL_{level}"

def get_caller_info():
    """Get information about the caller of the logging function.

    @return: Dictionary with filename, line number, and function name
    """
    frame = inspect.currentframe().f_back.f_back  # Go back two frames to get the caller
    filename = os.path.basename(frame.f_code.co_filename)
    lineno = frame.f_lineno
    function = frame.f_code.co_name
    return {
        "filename": filename,
        "lineno": lineno,
        "function": function
    }

def log_message(level, message, command=None, extra_data=None):
    """Send a log message to Redis.

    @param level: The log level (use LogLevel constants or string names)
    @param message: The message content to send
    @param command: The command type for the Redis channel (optional, defaults to "log")
    @param extra_data: Additional data to include in the log message (optional)
    """
    if command is None:
        command = "log"

    # Convert string level to numeric if needed
    numeric_level = LogLevel.get_level(level)
    level_name = LogLevel.get_level_name(numeric_level)

    caller_info = get_caller_info()

    # Check if the calling file has a LOG_LEVEL defined and respect it
    caller_module = inspect.getmodule(inspect.currentframe().f_back.f_back)
    if caller_module and hasattr(caller_module, 'LOG_LEVEL'):
        caller_log_level = LogLevel.get_level(caller_module.LOG_LEVEL)
        # Skip logging if the message level is lower than the caller's log level
        if numeric_level < caller_log_level:
            return

    log_message_obj = {
        "type": "system",
        "source": "system",
        "content": message,
        "level": numeric_level,
        "level_name": level_name,
        "timestamp": datetime.now().isoformat(),
        "caller": caller_info
    }

    # Add extra_data if provided
    if extra_data:
        log_message_obj["extra_data"] = extra_data

    redis_client.publish(f'system.log.{command}', json.dumps(log_message_obj))

def log_debug(message, command=None, extra_data=None):
    """Send a debug log message to Redis.

    @param message: The message content to send
    @param command: The command type for the Redis channel (optional, defaults to "log")
    @param extra_data: Additional data to include in the log message (optional)
    """
    log_message("DEBUG", message, command, extra_data)

def log_info(message, command=None, extra_data=None):
    """Send an info log message to Redis.

    @param message: The message content to send
    @param command: The command type for the Redis channel (optional, defaults to "log")
    @param extra_data: Additional data to include in the log message (optional)
    """
    log_message("INFO", message, command, extra_data)

def log_warning(message, command=None, extra_data=None):
    """Send a warning log message to Redis.

    @param message: The message content to send
    @param command: The command type for the Redis channel (optional, defaults to "log")
    @param extra_data: Additional data to include in the log message (optional)
    """
    log_message("WARNING", message, command, extra_data)

def log_error(message, command=None, extra_data=None):
    """Send an error log message to Redis.

    @param message: The message content to send
    @param command: The command type for the Redis channel (optional, defaults to "log")
    @param extra_data: Additional data to include in the log message (optional)
    """
    log_message("ERROR", message, command, extra_data)

def log_critical(message, command=None, extra_data=None):
    """Send a critical log message to Redis.

    @param message: The message content to send
    @param command: The command type for the Redis channel (optional, defaults to "log")
    @param extra_data: Additional data to include in the log message (optional)
    """
    log_message("CRITICAL", message, command, extra_data)

def log_important(message, command=None, extra_data=None):
    """Send an important notification message to Redis.

    @param message: The message content to send
    @param command: The command type for the Redis channel (optional, defaults to "log")
    @param extra_data: Additional data to include in the log message (optional)
    """
    log_message("IMPORTANT", message, command, extra_data)

def log_startup(message, command=None, extra_data=None):
    """Send a startup log message to Redis.

    @param message: The message content to send
    @param command: The command type for the Redis channel (optional, defaults to "log")
    @param extra_data: Additional data to include in the log message (optional)
    """
    log_message("STARTUP", message, command, extra_data)

##########################
# Messaging Functions
##########################

# Keeping backward compatibility for now
def send_admin_message_to_redis(message, command):
    """Deprecated: Use log_info, log_error, etc. instead.

    This function is kept for backward compatibility and will be removed in the future.

    @param message: The message content to send
    @param command: The command type for the Redis channel
    """
    return log_info(message, command)

def send_message_to_redis(send_message, command=None):
    """Send a chat message to Redis.

    @param send_message: The message to send
    @param command: The command type (optional)
    """
    redis_client.publish('twitch.chat.send', send_message)
