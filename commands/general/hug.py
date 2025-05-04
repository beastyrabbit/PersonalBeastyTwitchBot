import json
import random
import signal
import sys
from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared import pubsub

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.hug')
pubsub.subscribe('twitch.command.cuddle')
pubsub.subscribe('twitch.command.snuggle')

##########################
# Exit Function
##########################
register_exit_handler()

##########################
# Helper Functions
##########################
hug_messages = [
    "squeezes @{username} like a teddy bear! 🧸",
    "gives @{username} the warmest bear hug! 🐻",
    "hugs @{username} so tightly that their worries vanish! 🌈",
    "wraps @{username} in a burrito of love! 🌯",
    "sends @{username} a virtual hug full of good vibes! 🌟",
    "hugs @{username} like it's their last hug on Earth! 🌍",
    "gives @{username} a hug so big, even gravity feels it! 🌌",
    "hugs @{username} and whispers, 'Everything's going to be okay.' 🥰",
    "hugs @{username} and doesn't let go for an awkwardly long time. 😳",
    "turns @{username} into a hug sandwich! 🥪",
    "hugs @{username} while humming a happy tune! 🎵",
    "hugs @{username} with the power of a thousand suns! ☀️",
    "gives @{username} a hug and a cookie! 🍪",
    "hugs @{username} so tightly that their soul gets cozy! ✨",
    "shares a cosmic hug with @{username}! 🚀",
    "gives @{username} the squishiest hug ever! 🫧",
    "hugs @{username} and sneaks a pat on the back! 🖐️",
    "throws @{username} into a hug tornado! 🌪️",
    "hugs @{username} like they're reuniting after 100 years! ⏳",
    "hugs @{username} while softly saying 'no takebacks!' 😜",
    "hugs @{username} and slips them a friendship bracelet. 🧶",
    "gives @{username} a magical hug with sparkles! ✨",
    "hugs @{username} and adds a sprinkle of love dust! 💖",
    "hugs @{username} while tap-dancing around! 🎩",
    "hugs @{username} and spins them in a circle! 🌀",
    "gives @{username} a hug so sweet it could melt chocolate! 🍫",
    "hugs @{username} and says, 'Tag, you're it!' 🏷️",
    "hugs @{username} like a koala on a eucalyptus tree! 🐨",
    "hugs @{username} with a big goofy smile! 😁",
    "gives @{username} the best hug in the multiverse! 🌠"
]

def handle_hug_command(message_obj):
    author = message_obj["author"]
    username = author["display_name"]
    mention = author["mention"]
    content = message_obj.get("content", "")
    if not content:
        send_message_to_redis(f"@{username} is hugging the world! 🌍")
        return
    target = content.strip().split()[0]
    if target.startswith("@"): target = target[1:]
    target = target.lower()
    hug_message = random.choice(hug_messages).replace("{username}", target)
    send_message_to_redis(f"@{username} {hug_message}")

##########################
# Main
##########################
send_admin_message_to_redis("Hug command is ready to be used")
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command', '').lower()
            if command in ["hug", "cuddle", "snuggle"]:
                handle_hug_command(message_obj)
        except Exception as e:
            print(f"Error processing hug command: {e}")
            send_admin_message_to_redis(f"Error in hug command: {str(e)}") 