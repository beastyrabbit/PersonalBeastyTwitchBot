import json
from datetime import datetime

from module.shared_redis import redis_client, pubsub

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.fight')
pubsub.subscribe('twitch.command.battle')
pubsub.subscribe('twitch.command.duel')
pubsub.subscribe('twitch.command.flight')

COOLDOWN_SECONDS = 30
cooldown_users = {}

##########################
# Exit Function
##########################
register_exit_handler()

##########################
# Helper Functions
##########################
def get_user_data(username, display_name=None):
    username_lower = username.lower()
    user_key = f"user:{username_lower}"
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user = json.loads(user_json)
    else:
        user = {
            "name": username,
            "display_name": display_name or username,
            "log": {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0},
            "dustbunnies": {},
            "banking": {},
            "fighting": {},
        }
    if "fighting" not in user:
        user["fighting"] = {}
    return user, user_key

def save_user_data(user_key, user):
    redis_client.set(user_key, json.dumps(user))

def check_cooldown(username):
    now = datetime.now()
    if username in cooldown_users:
        last = cooldown_users[username]
        if (now - last).total_seconds() < COOLDOWN_SECONDS:
            return COOLDOWN_SECONDS - int((now - last).total_seconds())
    cooldown_users[username] = now
    return 0

def handle_fight_command(message_obj):
    author = message_obj["author"]
    username = author["display_name"]
    username_lower = author["name"].lower()
    mention = author["mention"]
    content = message_obj.get("content", "")
    if not content:
        send_message_to_redis(f"{mention} Please provide a username to fight with. Usage: !fight <username>")
        return
    target = content.strip().split()[0]
    if target.startswith("@"): target = target[1:]
    target = target.lower()
    if target == username_lower:
        send_message_to_redis(f"{mention} You can't fight yourself!")
        return
    # Cooldown check
    remaining = check_cooldown(username_lower)
    if remaining:
        send_message_to_redis(f"{mention} Please wait {remaining} seconds before challenging again.")
        return
    # Save fight request
    target_user, target_key = get_user_data(target, target)
    target_user["fighting"]["fight_requested_by"] = username_lower
    save_user_data(target_key, target_user)
    send_message_to_redis(f"@{target} {username} has requested a fight with you! Type !accept to fight back!")

##########################
# Main
##########################
send_admin_message_to_redis("Fight command is ready to be used", "fight")
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command', '').lower()
            if command in ["fight", "battle", "duel", "flight"]:
                handle_fight_command(message_obj)
        except Exception as e:
            print(f"Error processing fight command: {e}")
            send_admin_message_to_redis(f"Error in fight command: {str(e)}","fight")