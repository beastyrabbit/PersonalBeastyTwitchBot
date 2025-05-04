import json
import os
from datetime import datetime, timedelta

import redis
from dotenv import load_dotenv

import requests
from flask import Flask, request, jsonify
from werkzeug.serving import run_simple

from module.shared import redis_client_env

# Construct the absolute path to the .env file
env_path = os.path.join(os.path.dirname(__file__), '..', 'DONOTOPEN', '.env')
# Load the environment variables from the .env file
load_dotenv(env_path)

TOKEN_FILE = 'twitch_token.json'
REDIRECT_URI = 'https://twitch_recall.beasty.cloud/callback'
SCOPES="chat:read user:read:chat chat:edit user:write:chat moderator:manage:announcements moderator:manage:chat_messages moderator:manage:shoutouts whispers:read user:manage:whispers moderator:read:chatters channel:read:redemptions channel:manage:redemptions channel:manage:polls channel:manage:predictions moderator:manage:chat_settings channel:moderate channel:manage:moderators channel:manage:vips channel:manage:raids channel:manage:broadcast channel:read:hype_train channel:edit:commercial channel:read:subscriptions user:read:emotes user:read:follows moderator:read:followers user:read:moderated_channels user:read:blocked_users user:manage:blocked_users user:edit:broadcast moderator:manage:banned_users moderator:manage:automod moderator:manage:shield_mode moderator:manage:unban_requests clips:edit channel:read:ads channel:manage:ads moderator:manage:blocked_terms moderator:manage:warnings moderator:read:moderators moderator:read:vips moderator:read:suspicious_users bits:read"
CLIENT_ID = redis_client_env.get("TWITCH_CLIENT_ID").decode('utf-8')
CLIENT_SECRET = redis_client_env.get("TWITCH_CLIENT_SECRET").decode('utf-8')
FORCE_REFRESH = False

if CLIENT_ID is None or CLIENT_SECRET is None:
	raise ValueError('Please set the TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET environment variables')

app = Flask(__name__)
# Function to exchange the authorization code for an access token
def exchange_code_for_token(auth_code):
	"""Exchange the authorization code for an access token."""
	url = 'https://id.twitch.tv/oauth2/token'
	params = {
		'client_id': CLIENT_ID,
		'client_secret': CLIENT_SECRET,
		'code': auth_code,
		'grant_type': 'authorization_code',
		'redirect_uri': REDIRECT_URI,
	}
	response = requests.post(url, data=params)
	response.raise_for_status()
	token_data = response.json()
	save_token(token_data)
	return token_data['access_token']


def force_refresh_token():
	# Just remove the token from redis
	redis_client_env.delete("twitch_token_main")

# Function to save the token to a JSON file
def save_token(token_data):
	"""Save token to file."""
	token_data['expires_at'] = (datetime.now() + timedelta(seconds=token_data['expires_in'])).isoformat()
	# save token in redis as json
	token_data = json.dumps(token_data)
	redis_client_env.set("twitch_token_main", token_data)


# Function to load the token from a JSON file
def load_token():
	"""Load token from file if it exists."""
	token_data = redis_client_env.get("twitch_token_main")
	if token_data:
		return json.loads(token_data)


# Function to refresh the token using the refresh token
def refresh_token(refresh_token):
	"""Refresh the token using the refresh token."""
	url = 'https://id.twitch.tv/oauth2/token'
	params = {
		'client_id': CLIENT_ID,
		'client_secret': CLIENT_SECRET,
		'grant_type': 'refresh_token',
		'refresh_token': refresh_token,
	}
	response = requests.post(url, data=params)
	response.raise_for_status()
	token_data = response.json()
	save_token(token_data)
	return token_data['access_token']


# Function to ensure a valid token exists
def get_valid_token():
	"""Ensure a valid token is available, refreshing or re-authorizing if needed."""
	token_data = load_token()

	if token_data:
		expires_at = datetime.fromisoformat(token_data['expires_at'])
		if datetime.now() < expires_at - timedelta(hours=1):
			return token_data['access_token']  # Token is valid
		print('Token expired. Refreshing...')
		return refresh_token(token_data['refresh_token'])

	# No token available; start authorization flow
	print('No valid token found. Please visit the following URL to authorize:')
	print('------------------------------------------------------------------')
	auth_url = f"https://id.twitch.tv/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={SCOPES.replace(' ', '+')}"
	print(auth_url)
	print('------------------------------------------------------------------')
	run_server()  # Wait for user to authorize
	token_data = load_token()  # Load the token saved after exchange
	if not token_data:
		raise RuntimeError('Failed to retrieve token after authorization.')
	return token_data['access_token']


# Flask route to handle Twitch OAuth callback
@app.route('/callback')
def callback():
	"""Handle the redirect from Twitch and get the authorization code."""
	auth_code = request.args.get('code')
	if not auth_code:
		return 'Authorization failed. No code provided.', 400

	#print(f'Authorization code received: {auth_code}')
	exchange_code_for_token(auth_code)  # Exchange for a token
	# Trigger server shutdown
	shutdown_server()
	return 'Authorization successful! You can close this page.'

@app.route('/health', methods=['GET'])
def health():
	return jsonify({"status": "ok"}), 200


# Function to start the Flask server
def run_server():
	"""Run the Flask server to handle OAuth callback."""
	print('Starting local server to handle Twitch OAuth...')
	run_simple('0.0.0.0', 5000, app)


# Function to shut down the Flask server
def shutdown_server():
	"""Shutdown the Flask server."""
	func = request.environ.get('werkzeug.server.shutdown')
	if func is None:
		print('Werkzeug server shutdown function not found. Exiting...')
		os._exit(0)  # Forcefully exit the process
	func()


# Main script
if __name__ == '__main__':
	if FORCE_REFRESH:
		force_refresh_token()
	access_token = get_valid_token()
	if access_token is None:
		raise ValueError('Failed to get access token')
	if access_token:
		#only show the first 5 characters of the token
		print(f'Access token: {access_token[:3]}...{access_token[-2:]} ')
