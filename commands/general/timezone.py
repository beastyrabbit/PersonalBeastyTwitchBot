import json
from datetime import datetime, timedelta

import pytz
import redis

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)

pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.timezone')
pubsub.subscribe('twitch.command.time')

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def get_timezone_info(timezone_name=None):
    """
    Get time information for a specific timezone.

    Args:
        timezone_name (str, optional): The name of the timezone to check. Defaults to None.

    Returns:
        dict: A dictionary containing timezone information
    """
    try:
        # Always get German timezone info
        german_timezone = pytz.timezone('Europe/Berlin')
        german_time = datetime.now(german_timezone).strftime('%H:%M:%S')
        is_dst = german_timezone.localize(datetime.now()).dst() != timedelta(0)
        german_timezone_name = 'Central European Summer Time (CEST)' if is_dst else 'Central European Time (CET)'

        result = {
            "german_time": german_time,
            "german_timezone_name": german_timezone_name,
            "custom_timezone_info": None,
            "error": None
        }

        # Handle optional custom timezone
        if timezone_name:
            try:
                # Normalize common US timezone abbreviations
                timezone_name = timezone_name.upper()
                if timezone_name == 'CST':
                    timezone_name = 'CST6CDT'
                elif timezone_name == 'EST':
                    timezone_name = 'EST5EDT'
                elif timezone_name == 'PST':
                    timezone_name = 'PST8PDT'

                log_debug(f"Processing custom timezone: {timezone_name}", "timezone")

                # Handle GMT offsets and standard timezone names
                if timezone_name.startswith('GMT'):
                    offset = int(timezone_name[3:])
                    target_timezone = pytz.FixedOffset(offset * 60)
                    timezone_display_name = f'GMT{offset:+}'
                else:
                    target_timezone = pytz.timezone(timezone_name)
                    timezone_display_name = timezone_name

                custom_time = datetime.now(target_timezone).strftime('%H:%M:%S')
                is_dst_custom = target_timezone.localize(datetime.now()).dst() != timedelta(0) if hasattr(
                    target_timezone, 'localize') else False
                dst_status = ' (DST Active)' if is_dst_custom else ''

                result["custom_timezone_info"] = {
                    "name": timezone_display_name,
                    "time": custom_time,
                    "dst_active": is_dst_custom,
                    "dst_status": dst_status
                }

                log_info(f"Retrieved time for timezone {timezone_display_name}", "timezone", {
                    "timezone": timezone_display_name,
                    "time": custom_time,
                    "dst_active": is_dst_custom
                })

            except pytz.UnknownTimeZoneError:
                error_msg = f"Unknown timezone: {timezone_name}"
                log_warning(error_msg, "timezone")
                result["error"] = {
                    "type": "UnknownTimeZoneError",
                    "message": error_msg
                }

            except Exception as e:
                error_msg = f"Error processing custom timezone {timezone_name}: {e}"
                log_error(error_msg, "timezone", {"error": str(e)})
                result["error"] = {
                    "type": "Exception",
                    "message": str(e)
                }

        return result

    except Exception as e:
        error_msg = f"Error in get_timezone_info: {e}"
        log_error(error_msg, "timezone", {"error": str(e)})
        return {
            "error": {
                "type": "Exception",
                "message": str(e)
            }
        }

##########################
# Main
##########################
# Send startup message
log_startup("Timezone command is ready to be used", "timezone")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command')
            content = message_obj.get('content', '')
            print(f"Chat Command: {command} and Message: {content}")

            log_info(f"Received {command} command", "timezone", {"content": content})

            # Parse timezone parameter
            custom_timezone = None
            content_parts = content.split()
            if len(content_parts) > 1:
                custom_timezone = content_parts[1]
                username = message_obj["author"]["display_name"]
                log_info(f"User {username} is checking timezone for {custom_timezone}", "timezone")
            else:
                username = message_obj["author"]["display_name"]
                log_info(f"User {username} is checking default timezone", "timezone")

            # Get timezone information
            timezone_info = get_timezone_info(custom_timezone)

            # Send German timezone info
            german_msg = f'The current time in Germany is {timezone_info["german_time"]} ({timezone_info["german_timezone_name"]})'
            send_message_to_redis(german_msg)

            # Send custom timezone info if requested
            if custom_timezone:
                if timezone_info["error"]:
                    if timezone_info["error"]["type"] == "UnknownTimeZoneError":
                        send_message_to_redis(
                            f'Invalid timezone: {custom_timezone}. Please use valid names like "GMT+7", "CET", "PST".')
                    else:
                        send_message_to_redis('An error occurred while processing the timezone. Please try again.')
                else:
                    custom_info = timezone_info["custom_timezone_info"]
                    custom_msg = f'The current time in {custom_info["name"]} is {custom_info["time"]}{custom_info["dst_status"]}.'
                    send_message_to_redis(custom_msg)

        except Exception as e:
            error_msg = f"Error processing timezone command: {e}"
            print(error_msg)
            # Log the error with detailed information
            log_error(error_msg, "timezone", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
            send_message_to_redis('An error occurred while processing the timezone. Please try again.')
