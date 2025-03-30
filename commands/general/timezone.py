import json
import signal
import sys
import time
from datetime import datetime, timedelta

import pytz
import redis

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
def handle_exit(signum, frame):
    print("Unsubscribing from all channels bofore exiting")
    pubsub.unsubscribe()
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

##########################
# Helper Functions
##########################

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)


##########################
# Main
##########################
for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        custom_timezone = message_obj.get('content').split()[1] if len(message_obj.get('content').split()) > 1 else None
        if custom_timezone:
            print(f'{message_obj["auther"]["name"]} is checking the timezone for {custom_timezone}')
            custom_timezone = custom_timezone.upper()
            if custom_timezone == 'CST':
                custom_timezone = 'CST6CDT'
            if custom_timezone == 'EST':
                custom_timezone = 'EST5EDT'
            if custom_timezone == 'PST':
                custom_timezone = 'PST8PDT'

        else:
            print(f'{message_obj["auther"]["name"]} is checking the timezone')

        try:
            # Always display German timezone
            german_timezone = pytz.timezone('Europe/Berlin')
            german_time = datetime.now(german_timezone).strftime('%H:%M:%S')
            is_dst = german_timezone.localize(datetime.now()).dst() != timedelta(0)
            german_timezone_name = 'Central European Summer Time (CEST)' if is_dst else 'Central European Time (CET)'

            send_message_to_redis(f'The current time in Germany is {german_time} ({german_timezone_name})')

            # Handle optional custom timezone
            if custom_timezone:
                try:
                    if custom_timezone.upper().startswith('GMT'):
                        offset = int(custom_timezone[3:])
                        target_timezone = pytz.FixedOffset(offset * 60)
                        timezone_display_name = f'GMT{offset:+}'
                    else:
                        target_timezone = pytz.timezone(custom_timezone)
                        timezone_display_name = custom_timezone

                    custom_time = datetime.now(target_timezone).strftime('%H:%M:%S')
                    is_dst_custom = target_timezone.localize(datetime.now()).dst() != timedelta(0) if hasattr(
                        target_timezone, 'localize') else False
                    dst_status = ' (DST Active)' if is_dst_custom else ''
                    send_message_to_redis(f'The current time in {timezone_display_name} is {custom_time}{dst_status}.')

                except pytz.UnknownTimeZoneError:
                    send_message_to_redis(
                        f'Invalid timezone: {custom_timezone}. Please use valid names like "GMT+7", "CET", "PST".')
        except Exception as e:
            print(f'Error in timezone command: {e}')
            send_message_to_redis('An error occurred while processing the timezone. Please try again.')















