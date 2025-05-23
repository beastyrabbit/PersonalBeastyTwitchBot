import json
import random
from datetime import datetime

from openai import OpenAI

from module.message_utils import send_system_message_to_redis, send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug, log_warning
from module.shared_redis import redis_client, pubsub, redis_client_env

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.accept')

COOLDOWN_SECONDS = 30
cooldown_users = {}

##########################
# Classes, Weapons, Abilities
##########################
CLASSES = {
    "Warrior": {
        "health": (120, 160),
        "mana": (30, 50),
        "weapons": ["Greatsword", "Battle Axe"],
        "special": "Berserk",
        "abilities": ["Power Strike", "Shield Block", "Battle Cry", "Charge", "Second Wind"]
    },
    "Rogue": {
        "health": (70, 100),
        "mana": (40, 60),
        "weapons": ["Dagger", "Shortbow"],
        "special": "Backstab",
        "abilities": ["Poison Blade", "Evasion", "Shadowstep", "Quick Shot", "Smoke Bomb"]
    },
    "Mage": {
        "health": (50, 80),
        "mana": (80, 120),
        "weapons": ["Fire Staff", "Ice Wand"],
        "special": "Fireball",
        "abilities": ["Magic Missile", "Frost Nova", "Arcane Shield", "Mana Burn", "Heal"]
    },
}

WEAPONS = {
    "Greatsword": {"dmg": (18, 28), "hit_chance": (65, 85), "effect": None},
    "Battle Axe": {"dmg": (22, 32), "hit_chance": (60, 80), "effect": "bleed"},
    "Dagger": {"dmg": (10, 18), "hit_chance": (85, 100), "effect": "instakill_chance"},
    "Shortbow": {"dmg": (14, 22), "hit_chance": (75, 95), "effect": "double_hit"},
    "Fire Staff": {"dmg": (12, 20), "hit_chance": (70, 90), "effect": "burn"},
    "Ice Wand": {"dmg": (10, 16), "hit_chance": (80, 100), "effect": "freeze"},
}

ABILITIES = {
    "Power Strike": {"cost": 10, "effect": "damage", "value": (20, 30)},
    "Shield Block": {"cost": 8, "effect": "block", "value": (10, 20)},
    "Battle Cry": {"cost": 12, "effect": "buff", "value": (5, 10)},
    "Charge": {"cost": 15, "effect": "damage", "value": (15, 25)},
    "Second Wind": {"cost": 20, "effect": "heal", "value": (20, 30)},
    "Poison Blade": {"cost": 10, "effect": "dot", "value": (5, 10)},
    "Evasion": {"cost": 8, "effect": "dodge", "value": (1, 2)},
    "Shadowstep": {"cost": 12, "effect": "damage", "value": (15, 25)},
    "Quick Shot": {"cost": 10, "effect": "damage", "value": (10, 20)},
    "Smoke Bomb": {"cost": 15, "effect": "miss", "value": (1, 2)},
    "Magic Missile": {"cost": 10, "effect": "damage", "value": (18, 28)},
    "Frost Nova": {"cost": 12, "effect": "freeze", "value": (1, 2)},
    "Arcane Shield": {"cost": 15, "effect": "block", "value": (15, 25)},
    "Mana Burn": {"cost": 10, "effect": "mana_drain", "value": (10, 20)},
    "Heal": {"cost": 20, "effect": "heal", "value": (20, 35)},
}

##########################
# Exit Function
##########################
register_exit_handler()

##########################
# Helper Functions
##########################
def get_openai_api_key():
    """Gets OpenAI API key from Redis. Returns str key or raises RuntimeError if not found."""
    try:
        log_debug("Retrieving OpenAI API key from Redis", "accept")
        key = redis_client_env.get("OPENAI_API_KEY")
        if not key:
            error_msg = "OPENAI_API_KEY not found in redis_client_env"
            log_error(error_msg, "accept")
            raise RuntimeError(error_msg)
        return key.decode("utf-8")
    except Exception as e:
        error_msg = f"Error retrieving OpenAI API key: {e}"
        log_error(error_msg, "accept", {"error": str(e)})
        raise

def let_ai_narrate_the_fight(fight_sequence, class_info):
    """
    Use OpenAI to generate a narrative description of the fight.

    Args:
        fight_sequence (list): List of fight events
        class_info (dict): Information about the fighters' classes

    Returns:
        str: AI-generated narration of the fight
    """
    try:
        log_info("Generating AI narration for fight", "accept", {
            "sequence_length": len(fight_sequence),
            "fighters": list(class_info.keys())
        })

        api_key = get_openai_api_key()
        client = OpenAI(api_key=api_key)
        formatted_fight = "\n".join(fight_sequence)
        class_summary = "\n".join([
            f"{name}: Class={info['class']}, Weapon={info['weapon']}, Abilities={', '.join(info['abilities'])}, Special={info['special']}"
            for name, info in class_info.items()
        ])

        narration_prompt = (
            "You are a fantasy battle narrator. Give a short, dramatic, and vivid battle report (max 3 short sentences). "
            "Include the classes, weapons, abilities, and special events that happened. "
            "Here are the fighters and their loadouts:\n"
            f"{class_summary}\n\n"
            "Here is the fight log:\n\n"
            f"{formatted_fight}"
        )

        log_debug("Sending request to OpenAI API", "accept")
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": narration_prompt}
            ],
            max_tokens=300,
            temperature=0.7,
        )

        narration = completion.choices[0].message.content.strip()
        log_info("Received AI narration", "accept", {"length": len(narration)})
        return narration

    except Exception as e:
        error_msg = f"Error generating AI narration: {e}"
        log_error(error_msg, "accept", {
            "error": str(e),
            "fighters": list(class_info.keys()) if class_info else []
        })
        raise

def get_user_data(username, display_name=None):
    """
    Retrieve user data from Redis or create a new user if not found.

    Args:
        username (str): The username to retrieve
        display_name (str, optional): The display name to use if creating a new user

    Returns:
        tuple: (user_data, user_key) - The user data dictionary and Redis key
    """
    try:
        username_lower = username.lower()
        user_key = f"user:{username_lower}"

        log_debug(f"Retrieving user data for {username}", "accept")

        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user = json.loads(user_json)
            log_debug(f"Found existing user {username}", "accept")
        else:
            log_info(f"Creating new user account for {username}", "accept")
            user = {
                "name": username,
                "display_name": display_name or username,
                "log": {"chat": 0, "command": 0, "admin": 0, "lurk": 0, "unlurk": 0},
                "dustbunnies": {},
                "banking": {},
                "fighting": {},
            }

        if "fighting" not in user:
            log_debug(f"Creating fighting object for {username}", "accept")
            user["fighting"] = {}

        return user, user_key

    except Exception as e:
        error_msg = f"Error retrieving user data: {e}"
        log_error(error_msg, "accept", {
            "error": str(e),
            "username": username
        })
        # Return a basic user object to prevent further errors
        return {
            "name": username,
            "display_name": display_name or username,
            "fighting": {}
        }, f"user:{username.lower()}"

def save_user_data(user_key, user):
    """Saves user data to Redis using the specified key."""
    try:
        log_debug(f"Saving user data for {user.get('display_name', 'Unknown')}", "accept")
        redis_client.set(user_key, json.dumps(user))

    except Exception as e:
        error_msg = f"Error saving user data: {e}"
        log_error(error_msg, "accept", {
            "error": str(e),
            "user": user.get('display_name', 'Unknown')
        })

def check_cooldown(username):
    """Checks if user is on cooldown. Returns remaining seconds or 0 if not on cooldown."""
    try:
        now = datetime.now()

        if username in cooldown_users:
            last = cooldown_users[username]
            time_since_last = (now - last).total_seconds()

            log_debug(f"User {username} last used accept {time_since_last} seconds ago", "accept")

            if time_since_last < COOLDOWN_SECONDS:
                remaining = COOLDOWN_SECONDS - int(time_since_last)
                log_info(f"User {username} still on cooldown for {remaining} seconds", "accept", {
                    "cooldown_remaining": remaining
                })
                return remaining

        log_debug(f"User {username} not on cooldown, adding to cooldown list", "accept")
        cooldown_users[username] = now
        return 0

    except Exception as e:
        error_msg = f"Error checking cooldown: {e}"
        log_error(error_msg, "accept", {
            "error": str(e),
            "username": username
        })
        return 0  # Default to no cooldown in case of error

def random_class_and_loadout():
    class_name = random.choice(list(CLASSES.keys()))
    class_data = CLASSES[class_name]
    health = random.randint(*class_data["health"])
    mana = random.randint(*class_data["mana"])
    weapon = random.choice(class_data["weapons"])
    abilities = class_data["abilities"][:]
    random.shuffle(abilities)
    return {
        "class": class_name,
        "health": health,
        "mana": mana,
        "weapon": weapon,
        "abilities": abilities,
        "special": class_data["special"],
    }

def use_ability(user, opponent, user_state, opponent_state, fight_log):
    # Pick a random ability the user can afford
    affordable = [a for a in user_state["abilities"] if user_state["mana"] >= ABILITIES[a]["cost"]]
    if not affordable:
        return False  # No ability used
    ability = random.choice(affordable)
    ab = ABILITIES[ability]
    user_state["mana"] -= ab["cost"]
    effect = ab["effect"]
    value = random.randint(*ab["value"])
    if effect == "damage":
        opponent_state["health"] -= value
        fight_log.append(f"{user} uses {ability} on {opponent}, dealing {value} damage! {opponent} has {opponent_state['health']} health left.")
    elif effect == "heal":
        user_state["health"] += value
        fight_log.append(f"{user} uses {ability} and heals for {value} health! Now at {user_state['health']} health.")
    elif effect == "block":
        user_state["block"] = user_state.get("block", 0) + value
        fight_log.append(f"{user} uses {ability} and gains a shield of {value} points!")
    elif effect == "buff":
        user_state["buff"] = user_state.get("buff", 0) + value
        fight_log.append(f"{user} uses {ability} and increases their damage by {value} for the next attack!")
    elif effect == "dot":
        opponent_state["dot"] = opponent_state.get("dot", 0) + value
        fight_log.append(f"{user} uses {ability} and poisons {opponent} for {value} damage per turn!")
    elif effect == "dodge":
        user_state["dodge"] = user_state.get("dodge", 0) + value
        fight_log.append(f"{user} uses {ability} and will dodge the next {value} attack(s)!")
    elif effect == "miss":
        opponent_state["miss"] = opponent_state.get("miss", 0) + value
        fight_log.append(f"{user} uses {ability} and causes {opponent} to miss their next {value} attack(s)!")
    elif effect == "freeze":
        opponent_state["frozen"] = opponent_state.get("frozen", 0) + value
        fight_log.append(f"{user} uses {ability} and freezes {opponent} for {value} turn(s)!")
    elif effect == "mana_drain":
        drained = min(value, opponent_state["mana"])
        opponent_state["mana"] -= drained
        fight_log.append(f"{user} uses {ability} and drains {drained} mana from {opponent}!")
    return True

def weapon_attack(user, opponent, user_state, opponent_state, fight_log):
    weapon = user_state["weapon"]
    weapon_stats = WEAPONS[weapon]
    dmg = random.randint(*weapon_stats["dmg"])
    hit_chance = random.randint(*weapon_stats["hit_chance"])
    effect = weapon_stats["effect"]
    # Buff
    if user_state.get("buff", 0):
        dmg += user_state["buff"]
        user_state["buff"] = 0
    # Block
    if opponent_state.get("block", 0):
        block = opponent_state["block"]
        if block >= dmg:
            opponent_state["block"] -= dmg
            dmg = 0
        else:
            dmg -= block
            opponent_state["block"] = 0
    # Dodge
    if opponent_state.get("dodge", 0):
        opponent_state["dodge"] -= 1
        fight_log.append(f"{opponent} dodges the attack from {user}!")
        return
    # Miss
    if user_state.get("miss", 0):
        user_state["miss"] -= 1
        fight_log.append(f"{user} misses their attack due to confusion!")
        return
    # Frozen
    if user_state.get("frozen", 0):
        user_state["frozen"] -= 1
        fight_log.append(f"{user} is frozen and cannot act!")
        return
    # Hit?
    if random.randint(1, 100) <= hit_chance:
        # Instakill
        if effect == "instakill_chance" and random.random() < 0.05:
            opponent_state["health"] = 0
            fight_log.append(f"{user} uses {weapon} and lands a deadly blow! {opponent} is instantly defeated!")
            return
        # Double hit
        if effect == "double_hit" and random.random() < 0.15:
            fight_log.append(f"{user} uses {weapon} and attacks twice!")
            for _ in range(2):
                weapon_attack(user, opponent, user_state, opponent_state, fight_log)
            return
        # Bleed
        if effect == "bleed" and random.random() < 0.2:
            opponent_state["dot"] = opponent_state.get("dot", 0) + 5
            fight_log.append(f"{user} uses {weapon} and causes {opponent} to bleed for 5 damage per turn!")
        # Burn
        if effect == "burn" and random.random() < 0.2:
            opponent_state["dot"] = opponent_state.get("dot", 0) + 7
            fight_log.append(f"{user} uses {weapon} and burns {opponent} for 7 damage per turn!")
        # Freeze
        if effect == "freeze" and random.random() < 0.15:
            opponent_state["frozen"] = opponent_state.get("frozen", 0) + 1
            fight_log.append(f"{user} uses {weapon} and freezes {opponent} for 1 turn!")
        # Normal hit
        opponent_state["health"] -= dmg
        fight_log.append(f"{user} hits {opponent} with {weapon} for {dmg} damage. {opponent} has {opponent_state['health']} health left.")
    else:
        fight_log.append(f"{user} attacks with {weapon} but misses {opponent}!")

def handle_accept_command(message_obj):
    """Processes accept command to start a fight between users."""
    try:
        author = message_obj["author"]
        username = author["display_name"]
        username_lower = author["name"].lower()
        mention = author["mention"]
        content = message_obj.get("content", "")

        log_info(f"Processing accept command from {username}", "accept", {
            "user": username,
            "content": content
        })

        # Cooldown check
        remaining = check_cooldown(username_lower)
        if remaining:
            log_info(f"User {username} is on cooldown for {remaining} seconds", "accept")
            send_message_to_redis(f"{mention} Please wait {remaining} seconds before accepting again.")
            return

        # Determine opponent
        if content:
            opponent = content.strip().split()[0]
            if opponent.startswith("@"): opponent = opponent[1:]
            opponent = opponent.lower()
            log_info(f"User {username} specified opponent: {opponent}", "accept")
        else:
            user, user_key = get_user_data(username_lower, username)
            opponent = user["fighting"].get("fight_requested_by")

            if not opponent:
                log_warning(f"User {username} has no pending fight requests", "accept")
                send_message_to_redis(f"{mention} You do not have any pending fight requests.")
                return

            log_info(f"User {username} accepting pending fight request from {opponent}", "accept")

        # Remove fight request
        user, user_key = get_user_data(username_lower, username)
        user["fighting"]["fight_requested_by"] = ""
        save_user_data(user_key, user)

        # Start fight
        log_info(f"Starting fight between {username} and {opponent}", "accept")
        send_message_to_redis(f"@{username} has accepted the fight with @{opponent}! Let the battle begin!")

        # Assign classes, weapons, mana, abilities
        fighter1 = random_class_and_loadout()
        fighter2 = random_class_and_loadout()

        log_debug(f"Assigned {username} as {fighter1['class']} with {fighter1['weapon']}", "accept")
        log_debug(f"Assigned {opponent} as {fighter2['class']} with {fighter2['weapon']}", "accept")

        fighter1_state = {
            "health": fighter1["health"],
            "mana": fighter1["mana"],
            "weapon": fighter1["weapon"],
            "abilities": fighter1["abilities"],
            "special": fighter1["special"],
        }
        fighter2_state = {
            "health": fighter2["health"],
            "mana": fighter2["mana"],
            "weapon": fighter2["weapon"],
            "abilities": fighter2["abilities"],
            "special": fighter2["special"],
        }
        class_info = {
            username: fighter1,
            opponent: fighter2,
        }
        fight_log = []
        winner = None
        loser = None
        turn = 0
        user_names = [username, opponent]
        states = [fighter1_state, fighter2_state]

        # Main fight loop
        log_debug("Starting fight simulation", "accept")
        while True:
            attacker_idx = turn % 2
            defender_idx = (turn + 1) % 2
            attacker = user_names[attacker_idx]
            defender = user_names[defender_idx]
            attacker_state = states[attacker_idx]
            defender_state = states[defender_idx]

            # Apply DOT
            if attacker_state.get("dot", 0):
                dot = attacker_state["dot"]
                attacker_state["health"] -= dot
                fight_log.append(f"{attacker} suffers {dot} damage from ongoing effects. {attacker} has {attacker_state['health']} health left.")

            # Check if dead
            if attacker_state["health"] <= 0:
                winner = defender
                loser = attacker
                log_debug(f"{attacker} died from DOT effects, {defender} wins", "accept")
                break

            # Try to use ability (50% chance)
            used_ability = False
            if attacker_state["abilities"] and random.random() < 0.5:
                used_ability = use_ability(attacker, defender, attacker_state, defender_state, fight_log)

            # If not, do weapon attack
            if not used_ability:
                weapon_attack(attacker, defender, attacker_state, defender_state, fight_log)

            # Check if defender is dead
            if defender_state["health"] <= 0:
                winner = attacker
                loser = defender
                log_debug(f"{defender} was defeated by {attacker}", "accept")
                break

            turn += 1

            # Limit fight length
            if turn > 50:
                fight_log.append("The fight was too long and ends in a draw!")
                log_info("Fight ended in a draw due to turn limit", "accept")
                winner = None
                break

        # AI narration
        try:
            log_info("Generating AI narration for the fight", "accept")
            ai_message = let_ai_narrate_the_fight(fight_log, class_info)
            for i in range(0, len(ai_message), 450):
                send_message_to_redis(ai_message[i: i + 450])
        except Exception as e:
            error_msg = f"AI narration failed: {e}"
            log_error(error_msg, "accept", {"error": str(e)})
            send_system_message_to_redis(error_msg, "fight")

        if winner:
            log_info(f"{winner} won the fight against {loser}", "accept", {
                "winner": winner,
                "loser": loser,
                "turns": turn
            })
            send_message_to_redis(f'@{winner} has won the fight! 🎉')

            # Update stats
            winner_user, winner_key = get_user_data(winner, winner)
            loser_user, loser_key = get_user_data(loser, loser)

            previous_wins = winner_user["fighting"].get("fights_won", 0)
            previous_losses = loser_user["fighting"].get("fights_lost", 0)

            winner_user["fighting"]["fights_won"] = previous_wins + 1
            loser_user["fighting"]["fights_lost"] = previous_losses + 1

            log_info(f"Updated {winner}'s win count to {previous_wins + 1}", "accept")
            log_info(f"Updated {loser}'s loss count to {previous_losses + 1}", "accept")

            save_user_data(winner_key, winner_user)
            save_user_data(loser_key, loser_user)
        else:
            log_info("Fight ended in a draw", "accept")
            send_message_to_redis("The fight ended in a draw!")

    except Exception as e:
        error_msg = f"Error handling accept command: {e}"
        log_error(error_msg, "accept", {
            "error": str(e),
            "user": message_obj.get("author", {}).get("display_name", "Unknown")
        })

##########################
# Main
##########################
# Send startup message
log_startup("Accept command is ready to be used", "accept")
send_system_message_to_redis("Accept command is running", "fight")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command', '').lower()
            content = message_obj.get('content', '')

            if command == "accept":
                log_info(f"Received accept command", "accept", {"content": content})
                handle_accept_command(message_obj)

        except Exception as e:
            error_msg = f"Error processing accept command: {e}"
            # Log the error with detailed information
            log_error(error_msg, "accept", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
            send_system_message_to_redis(f"Error in accept command: {str(e)}", "fight")
