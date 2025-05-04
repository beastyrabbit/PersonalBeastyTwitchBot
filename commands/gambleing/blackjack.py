#!/usr/bin/env python3
"""
Blackjack Command

This command allows users to play blackjack with their collected dustbunnies.
Users can join a game, hit, stand, double down, or split their hands.

Usage:
!blackjack join - Join the current blackjack game
!blackjack hit - Hit (take another card)
!blackjack stand - Stand (keep current hand)
!blackjack double - Double down (double bet and take exactly one more card)
!blackjack split - Split matching cards into two hands
"""
import json
import random
import time
from datetime import datetime
from threading import Thread, Lock

from module.shared_redis import redis_client, pubsub

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler

##########################
# Initialize
##########################
# Subscribe to blackjack command and its alias
pubsub.subscribe('twitch.command.blackjack')
pubsub.subscribe('twitch.command.bj')

# Initialize game state
GAME_STATE_KEY = 'game:blackjack:state'
GAME_PLAYERS_KEY = 'game:blackjack:players'
GAME_TIMEOUT_SECONDS = 60  # Time for players to join or make decisions

# Blackjack game states
STATE_IDLE = 'idle'
STATE_JOINING = 'joining'
STATE_PLAYING = 'playing'
STATE_DEALER_TURN = 'dealer_turn'
STATE_GAME_OVER = 'game_over'

# Game lock for thread safety
game_lock = Lock()

# Card values
CARD_SUITS = ['♥', '♦', '♣', '♠']
CARD_VALUES = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']

# Initialize game
game_state = {
    'state': STATE_IDLE,
    'timestamp': datetime.now().timestamp(),
    'dealer_hand': [],
    'current_player_index': 0,
    'deck': []
}

# Save initial game state
redis_client.set(GAME_STATE_KEY, json.dumps(game_state))

##########################
# Exit Function
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def create_new_deck():
    """Create and shuffle a new deck of cards"""
    deck = []
    for suit in CARD_SUITS:
        for value in CARD_VALUES:
            deck.append({'suit': suit, 'value': value})
    random.shuffle(deck)
    return deck

def get_card_value(card):
    """Get the numerical value of a card"""
    if card['value'] in ['J', 'Q', 'K']:
        return 10
    elif card['value'] == 'A':
        return 11  # Initially count as 11, can be reduced to 1 if needed
    else:
        return int(card['value'])

def calculate_hand_value(hand):
    """Calculate the value of a hand, accounting for aces"""
    value = sum(get_card_value(card) for card in hand)
    # Adjust for aces if busting
    aces = sum(1 for card in hand if card['value'] == 'A')
    while value > 21 and aces > 0:
        value -= 10  # Convert an ace from 11 to 1
        aces -= 1
    return value

def format_card(card):
    """Format a card for display"""
    return f"{card['value']}{card['suit']}"

def format_hand(hand):
    """Format a hand for display"""
    return ' '.join(format_card(card) for card in hand)

def get_game_state():
    """Get the current game state from Redis"""
    state_json = redis_client.get(GAME_STATE_KEY)
    if state_json:
        return json.loads(state_json)
    return game_state

def save_game_state(state):
    """Save the game state to Redis"""
    redis_client.set(GAME_STATE_KEY, json.dumps(state))

def get_player_data(username_lower):
    """Get player data from Redis"""
    player_key = f"game:blackjack:player:{username_lower}"
    player_json = redis_client.get(player_key)
    if player_json:
        return json.loads(player_json)
    return None

def save_player_data(username_lower, player_data):
    """Save player data to Redis"""
    player_key = f"game:blackjack:player:{username_lower}"
    redis_client.set(player_key, json.dumps(player_data))

def get_game_players():
    """Get the list of players in the current game"""
    players_json = redis_client.get(GAME_PLAYERS_KEY)
    if players_json:
        return json.loads(players_json)
    return []

def save_game_players(players):
    """Save the list of players to Redis"""
    redis_client.set(GAME_PLAYERS_KEY, json.dumps(players))

def deal_card(state, hand):
    """Deal a card from the deck to a hand"""
    if not state['deck']:
        state['deck'] = create_new_deck()
    card = state['deck'].pop(0)
    hand.append(card)
    return card

def start_game_timer():
    """Start a timer thread for game state transitions"""
    def timer_thread():
        time.sleep(GAME_TIMEOUT_SECONDS)
        with game_lock:
            state = get_game_state()
            players = get_game_players()
            
            if state['state'] == STATE_JOINING:
                if players:
                    # Start the game with joined players
                    start_game(state, players)
                else:
                    # No players joined, return to idle
                    state['state'] = STATE_IDLE
                    save_game_state(state)
                    send_message_to_redis("No players joined the Blackjack game. Game cancelled.")
            
            elif state['state'] == STATE_PLAYING:
                # Time's up for current player
                current_index = state['current_player_index']
                if current_index < len(players):
                    # Auto-stand for current player
                    username = players[current_index]
                    player_data = get_player_data(username)
                    
                    if player_data:
                        send_message_to_redis(f"@{player_data['display_name']} took too long to decide. Standing with {format_hand(player_data['hand'])} ({calculate_hand_value(player_data['hand'])})")
                        
                        # Move to next player
                        state['current_player_index'] += 1
                        save_game_state(state)
                        
                        if state['current_player_index'] >= len(players):
                            # All players have played, dealer's turn
                            dealer_turn(state, players)
                        else:
                            # Next player's turn
                            next_player = players[state['current_player_index']]
                            next_player_data = get_player_data(next_player)
                            send_message_to_redis(f"@{next_player_data['display_name']}'s turn. Your hand: {format_hand(next_player_data['hand'])} ({calculate_hand_value(next_player_data['hand'])}). Type !blackjack hit or !blackjack stand")
                            start_game_timer()
                    
    thread = Thread(target=timer_thread)
    thread.daemon = True
    thread.start()

def start_game(state, players):
    """Start a blackjack game with the joined players"""
    # Initialize new game
    state['state'] = STATE_PLAYING
    state['dealer_hand'] = []
    state['current_player_index'] = 0
    state['deck'] = create_new_deck()
    save_game_state(state)
    
    # Deal initial cards
    for _ in range(2):  # Two rounds of dealing
        # Deal to each player first
        for username in players:
            player_data = get_player_data(username)
            deal_card(state, player_data['hand'])
            save_player_data(username, player_data)
        
        # Then deal to dealer
        deal_card(state, state['dealer_hand'])
    
    save_game_state(state)
    
    # Show dealer's up card
    dealer_up_card = state['dealer_hand'][0]
    send_message_to_redis(f"Dealer shows: {format_card(dealer_up_card)}")
    
    # First player's turn
    if players:
        first_player = players[0]
        player_data = get_player_data(first_player)
        hand_value = calculate_hand_value(player_data['hand'])
        
        # Check for natural blackjack
        if hand_value == 21:
            send_message_to_redis(f"@{player_data['display_name']} has Blackjack! {format_hand(player_data['hand'])}")
            state['current_player_index'] += 1
            save_game_state(state)
            
            if state['current_player_index'] >= len(players):
                # All players have blackjack or have played, dealer's turn
                dealer_turn(state, players)
            else:
                # Next player's turn
                next_player = players[state['current_player_index']]
                next_player_data = get_player_data(next_player)
                send_message_to_redis(f"@{next_player_data['display_name']}'s turn. Your hand: {format_hand(next_player_data['hand'])} ({calculate_hand_value(next_player_data['hand'])}). Type !blackjack hit or !blackjack stand")
                start_game_timer()
        else:
            send_message_to_redis(f"@{player_data['display_name']}'s turn. Your hand: {format_hand(player_data['hand'])} ({hand_value}). Type !blackjack hit or !blackjack stand")
            start_game_timer()

def dealer_turn(state, players):
    """Dealer's turn after all players have played"""
    state['state'] = STATE_DEALER_TURN
    save_game_state(state)
    
    send_message_to_redis(f"Dealer's turn. Dealer's hand: {format_hand(state['dealer_hand'])}")
    
    # Dealer hits until 17 or higher
    dealer_value = calculate_hand_value(state['dealer_hand'])
    while dealer_value < 17:
        new_card = deal_card(state, state['dealer_hand'])
        dealer_value = calculate_hand_value(state['dealer_hand'])
        send_message_to_redis(f"Dealer draws: {format_card(new_card)}. Hand: {format_hand(state['dealer_hand'])} ({dealer_value})")
        time.sleep(1)  # Pause for drama
    
    save_game_state(state)
    
    # Determine winners
    end_game(state, players)

def end_game(state, players):
    """End the game and determine winners"""
    state['state'] = STATE_GAME_OVER
    save_game_state(state)
    
    dealer_value = calculate_hand_value(state['dealer_hand'])
    dealer_bust = dealer_value > 21
    
    if dealer_bust:
        send_message_to_redis(f"Dealer busts with {dealer_value}!")
    else:
        send_message_to_redis(f"Dealer stands with {dealer_value}.")
    
    # Process each player's results
    for username in players:
        player_data = get_player_data(username)
        if not player_data:
            continue
            
        player_value = calculate_hand_value(player_data['hand'])
        player_bust = player_value > 21
        bet_amount = player_data['bet']
        user_key = f"user:{username}"
        
        # Get user data
        if redis_client.exists(user_key):
            user_json = redis_client.get(user_key)
            user = json.loads(user_json)
        else:
            continue
            
        # Initialize gambling stats if they don't exist
        if "gambling" not in user:
            user["gambling"] = {
                "input": 0,
                "results": 0,
                "wins": 0,
                "losses": 0
            }
        
        # Determine outcome
        if player_bust:
            # Player busts, loses bet
            result_message = f"@{player_data['display_name']} busts with {player_value} and loses {bet_amount} dustbunnies!"
            user["gambling"]["results"] = user["gambling"].get("results", 0) - bet_amount
            user["gambling"]["losses"] = user["gambling"].get("losses", 0) + bet_amount
        elif dealer_bust:
            # Dealer busts, player wins
            winnings = bet_amount * 2
            result_message = f"@{player_data['display_name']} wins {bet_amount} dustbunnies with {player_value}!"
            user["dustbunnies"]["collected_dustbunnies"] = user["dustbunnies"].get("collected_dustbunnies", 0) + bet_amount
            user["gambling"]["results"] = user["gambling"].get("results", 0) + bet_amount
            user["gambling"]["wins"] = user["gambling"].get("wins", 0) + bet_amount
        elif player_value > dealer_value:
            # Player beats dealer
            winnings = bet_amount * 2
            result_message = f"@{player_data['display_name']} wins {bet_amount} dustbunnies with {player_value} vs dealer's {dealer_value}!"
            user["dustbunnies"]["collected_dustbunnies"] = user["dustbunnies"].get("collected_dustbunnies", 0) + bet_amount
            user["gambling"]["results"] = user["gambling"].get("results", 0) + bet_amount
            user["gambling"]["wins"] = user["gambling"].get("wins", 0) + bet_amount
        elif player_value == dealer_value:
            # Push (tie)
            result_message = f"@{player_data['display_name']} pushes with {player_value}. Bet returned."
            user["dustbunnies"]["collected_dustbunnies"] = user["dustbunnies"].get("collected_dustbunnies", 0) + bet_amount
        else:
            # Dealer wins
            result_message = f"@{player_data['display_name']} loses {bet_amount} dustbunnies with {player_value} vs dealer's {dealer_value}."
            user["gambling"]["results"] = user["gambling"].get("results", 0) - bet_amount
            user["gambling"]["losses"] = user["gambling"].get("losses", 0) + bet_amount
        
        # Save user data
        redis_client.set(user_key, json.dumps(user))
        send_message_to_redis(result_message)
    
    # Clean up game data
    for username in players:
        player_key = f"game:blackjack:player:{username}"
        redis_client.delete(player_key)
    
    # Reset game state after a short delay
    time.sleep(5)
    state['state'] = STATE_IDLE
    save_game_state(state)
    redis_client.delete(GAME_PLAYERS_KEY)
    send_message_to_redis("Blackjack game ended. Type !blackjack join to start a new game!")

def handle_blackjack(message_obj):
    """Process the blackjack command"""
    try:
        username = message_obj["author"]["display_name"]
        username_lower = message_obj["author"]["name"].lower()
        user_key = f"user:{username_lower}"
        mention = message_obj["author"]["mention"]
        
        # Get command content (action and any arguments)
        content = message_obj.get('content', '')
        if not content:
            send_message_to_redis(f"{mention} Please specify an action: join, hit, stand, double, or split.")
            return
            
        content_parts = content.strip().split()
        action = content_parts[0].lower()
        
        with game_lock:
            state = get_game_state()
            players = get_game_players()
            
            # Handle different blackjack actions
            if action == 'join':
                handle_join(state, players, username, username_lower, mention, user_key)
            elif action == 'hit':
                handle_hit(state, players, username_lower, mention)
            elif action == 'stand':
                handle_stand(state, players, username_lower, mention)
            elif action == 'double':
                handle_double(state, players, username_lower, mention, user_key)
            elif action == 'split':
                handle_split(state, players, username_lower, mention)
            else:
                send_message_to_redis(f"{mention} Please specify a valid action: join, hit, stand, double, or split.")
                
    except Exception as e:
        print(f"Error processing blackjack command: {e}")
        send_admin_message_to_redis(f"Error in blackjack command: {str(e)}", "blackjack")

def handle_join(state, players, username, username_lower, mention, user_key):
    """Handle the join action for blackjack"""
    # Check if game is already in progress
    if state['state'] not in [STATE_IDLE, STATE_JOINING]:
        send_message_to_redis(f"{mention} A game is already in progress. Please wait for it to finish.")
        return
        
    # Check if player is already in the game
    if username_lower in players:
        send_message_to_redis(f"{mention} You are already in this blackjack game.")
        return
        
    # Get user data to verify they have enough points
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user = json.loads(user_json)
    else:
        send_message_to_redis(f"{mention} You don't have an account to play blackjack with.")
        return
        
    # Check if user has enough dustbunnies (minimum bet is 10)
    if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"] or user["dustbunnies"].get("collected_dustbunnies", 0) < 10:
        send_message_to_redis(f"{mention} You need at least 10 dustbunnies to play blackjack.")
        return
        
    # Set initial bet amount (can be adjusted later)
    bet_amount = 10
    
    # Remove bet from user's balance
    user["dustbunnies"]["collected_dustbunnies"] -= bet_amount
    
    # Initialize gambling stats if they don't exist
    if "gambling" not in user:
        user["gambling"] = {
            "input": 0,
            "results": 0,
            "wins": 0,
            "losses": 0
        }
        
    # Record gambling attempt
    user["gambling"]["input"] = user["gambling"].get("input", 0) + bet_amount
    
    # Save user data
    redis_client.set(user_key, json.dumps(user))
    
    # Create player data for the game
    player_data = {
        'username': username_lower,
        'display_name': username,
        'hand': [],
        'bet': bet_amount,
        'status': 'active'
    }
    save_player_data(username_lower, player_data)
    
    # Add player to the game
    players.append(username_lower)
    save_game_players(players)
    
    # Start joining phase if not already started
    if state['state'] == STATE_IDLE:
        state['state'] = STATE_JOINING
        state['timestamp'] = datetime.now().timestamp()
        save_game_state(state)
        send_message_to_redis(f"{mention} started a new Blackjack game! Type !blackjack join to play. Game starts in {GAME_TIMEOUT_SECONDS} seconds.")
        start_game_timer()
    else:
        send_message_to_redis(f"{mention} joined the Blackjack game!")

def handle_hit(state, players, username_lower, mention):
    """Handle the hit action for blackjack"""
    if state['state'] != STATE_PLAYING:
        send_message_to_redis(f"{mention} No blackjack game is currently in the playing phase.")
        return
        
    if username_lower not in players:
        send_message_to_redis(f"{mention} You are not in this blackjack game.")
        return
        
    # Check if it's this player's turn
    current_index = state['current_player_index']
    if current_index >= len(players) or players[current_index] != username_lower:
        send_message_to_redis(f"{mention} It's not your turn yet.")
        return
        
    # Get player data
    player_data = get_player_data(username_lower)
    if not player_data:
        send_message_to_redis(f"{mention} Error retrieving your game data.")
        return
        
    # Deal a new card
    new_card = deal_card(state, player_data['hand'])
    save_player_data(username_lower, player_data)
    save_game_state(state)
    
    # Calculate new hand value
    hand_value = calculate_hand_value(player_data['hand'])
    send_message_to_redis(f"{mention} hits and gets {format_card(new_card)}. Hand: {format_hand(player_data['hand'])} ({hand_value})")
    
    # Check if player busts
    if hand_value > 21:
        send_message_to_redis(f"{mention} busts with {hand_value}!")
        
        # Move to next player
        state['current_player_index'] += 1
        save_game_state(state)
        
        if state['current_player_index'] >= len(players):
            # All players have played, dealer's turn
            dealer_turn(state, players)
        else:
            # Next player's turn
            next_player = players[state['current_player_index']]
            next_player_data = get_player_data(next_player)
            send_message_to_redis(f"@{next_player_data['display_name']}'s turn. Your hand: {format_hand(next_player_data['hand'])} ({calculate_hand_value(next_player_data['hand'])}). Type !blackjack hit or !blackjack stand")
            start_game_timer()
    elif hand_value == 21:
        send_message_to_redis(f"{mention} has 21!")
        
        # Move to next player
        state['current_player_index'] += 1
        save_game_state(state)
        
        if state['current_player_index'] >= len(players):
            # All players have played, dealer's turn
            dealer_turn(state, players)
        else:
            # Next player's turn
            next_player = players[state['current_player_index']]
            next_player_data = get_player_data(next_player)
            send_message_to_redis(f"@{next_player_data['display_name']}'s turn. Your hand: {format_hand(next_player_data['hand'])} ({calculate_hand_value(next_player_data['hand'])}). Type !blackjack hit or !blackjack stand")
            start_game_timer()

def handle_stand(state, players, username_lower, mention):
    """Handle the stand action for blackjack"""
    if state['state'] != STATE_PLAYING:
        send_message_to_redis(f"{mention} No blackjack game is currently in the playing phase.")
        return
        
    if username_lower not in players:
        send_message_to_redis(f"{mention} You are not in this blackjack game.")
        return
        
    # Check if it's this player's turn
    current_index = state['current_player_index']
    if current_index >= len(players) or players[current_index] != username_lower:
        send_message_to_redis(f"{mention} It's not your turn yet.")
        return
        
    # Get player data
    player_data = get_player_data(username_lower)
    if not player_data:
        send_message_to_redis(f"{mention} Error retrieving your game data.")
        return
        
    # Player stands
    hand_value = calculate_hand_value(player_data['hand'])
    send_message_to_redis(f"{mention} stands with {format_hand(player_data['hand'])} ({hand_value})")
    
    # Move to next player
    state['current_player_index'] += 1
    save_game_state(state)
    
    if state['current_player_index'] >= len(players):
        # All players have played, dealer's turn
        dealer_turn(state, players)
    else:
        # Next player's turn
        next_player = players[state['current_player_index']]
        next_player_data = get_player_data(next_player)
        send_message_to_redis(f"@{next_player_data['display_name']}'s turn. Your hand: {format_hand(next_player_data['hand'])} ({calculate_hand_value(next_player_data['hand'])}). Type !blackjack hit or !blackjack stand")
        start_game_timer()

def handle_double(state, players, username_lower, mention, user_key):
    """Handle the double down action for blackjack"""
    if state['state'] != STATE_PLAYING:
        send_message_to_redis(f"{mention} No blackjack game is currently in the playing phase.")
        return
        
    if username_lower not in players:
        send_message_to_redis(f"{mention} You are not in this blackjack game.")
        return
        
    # Check if it's this player's turn
    current_index = state['current_player_index']
    if current_index >= len(players) or players[current_index] != username_lower:
        send_message_to_redis(f"{mention} It's not your turn yet.")
        return
        
    # Get player data
    player_data = get_player_data(username_lower)
    if not player_data:
        send_message_to_redis(f"{mention} Error retrieving your game data.")
        return
        
    # Check if player has exactly 2 cards (required for doubling)
    if len(player_data['hand']) != 2:
        send_message_to_redis(f"{mention} You can only double down on your initial two cards.")
        return
        
    # Get user data to verify they have enough points for doubling
    if redis_client.exists(user_key):
        user_json = redis_client.get(user_key)
        user = json.loads(user_json)
    else:
        send_message_to_redis(f"{mention} Error retrieving your account data.")
        return
        
    # Check if user has enough dustbunnies to double bet
    current_bet = player_data['bet']
    if "dustbunnies" not in user or "collected_dustbunnies" not in user["dustbunnies"] or user["dustbunnies"].get("collected_dustbunnies", 0) < current_bet:
        send_message_to_redis(f"{mention} You don't have enough dustbunnies to double your bet.")
        return
        
    # Double the bet
    user["dustbunnies"]["collected_dustbunnies"] -= current_bet
    user["gambling"]["input"] = user["gambling"].get("input", 0) + current_bet
    redis_client.set(user_key, json.dumps(user))
    
    player_data['bet'] *= 2
    save_player_data(username_lower, player_data)
    
    send_message_to_redis(f"{mention} doubles down! Bet is now {player_data['bet']} dustbunnies.")
    
    # Deal exactly one more card
    new_card = deal_card(state, player_data['hand'])
    save_player_data(username_lower, player_data)
    save_game_state(state)
    
    # Calculate new hand value
    hand_value = calculate_hand_value(player_data['hand'])
    send_message_to_redis(f"{mention} gets {format_card(new_card)}. Final hand: {format_hand(player_data['hand'])} ({hand_value})")
    
    # Move to next player (player automatically stands after doubling)
    state['current_player_index'] += 1
    save_game_state(state)
    
    if state['current_player_index'] >= len(players):
        # All players have played, dealer's turn
        dealer_turn(state, players)
    else:
        # Next player's turn
        next_player = players[state['current_player_index']]
        next_player_data = get_player_data(next_player)
        send_message_to_redis(f"@{next_player_data['display_name']}'s turn. Your hand: {format_hand(next_player_data['hand'])} ({calculate_hand_value(next_player_data['hand'])}). Type !blackjack hit or !blackjack stand")
        start_game_timer()

def handle_split(state, players, username_lower, mention):
    """Handle the split action for blackjack"""
    # Not implemented in this basic version
    send_message_to_redis(f"{mention} Splitting is not implemented in this version of Blackjack. Try !blackjack hit or !blackjack stand")

##########################
# Main
##########################
send_admin_message_to_redis("Blackjack command is ready to be used", "blackjack")

# Main message loop
for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            handle_blackjack(message_obj)
        except Exception as e:
            print(f"Error processing command: {e}")
            send_admin_message_to_redis(f"Error in blackjack command: {str(e)}", "blackjack")