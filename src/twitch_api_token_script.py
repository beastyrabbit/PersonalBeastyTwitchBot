import json
import os
from datetime import datetime, timedelta

import redis
from dotenv import load_dotenv

import requests
from flask import Flask, request, jsonify
from werkzeug.serving import run_simple

# Construct the absolute path to the .env file
env_path = os.path.join(os.path.dirname(__file__), '..', 'DONOTOPEN', '.env')
# Load the environment variables from the .env file
load_dotenv(env_path)
redis_client_env = redis.Redis(host='192.168.50.115', port=6379, db=1)

REDIRECT_URI = 'https://twitch_recall.beasty.cloud/callback'
SCOPES="chat:read user:read:chat chat:edit user:write:chat moderator:manage:announcements moderator:manage:chat_messages moderator:manage:shoutouts whispers:read user:manage:whispers moderator:read:chatters channel:read:redemptions channel:manage:redemptions channel:manage:polls channel:manage:predictions moderator:manage:chat_settings channel:moderate channel:manage:moderators channel:manage:vips channel:manage:raids channel:manage:broadcast channel:read:hype_train channel:edit:commercial channel:read:subscriptions user:read:emotes user:read:follows moderator:read:followers user:read:moderated_channels user:read:blocked_users user:manage:blocked_users user:edit:broadcast moderator:manage:banned_users moderator:manage:automod moderator:manage:shield_mode moderator:manage:unban_requests clips:edit channel:read:ads channel:manage:ads moderator:manage:blocked_terms moderator:manage:warnings moderator:read:moderators moderator:read:vips moderator:read:suspicious_users bits:read"
CLIENT_ID = redis_client_env.get("TWITCH_CLIENT_ID").decode('utf-8')
CLIENT_SECRET = redis_client_env.get("TWITCH_CLIENT_SECRET").decode('utf-8')

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
	"""Remove the token from Redis, forcing a new authorization flow."""
	if redis_client_env.exists("twitch_token"):
		redis_client_env.delete("twitch_token")
		print("Token successfully removed from Redis. A new token will be requested.")
		return True
	else:
		print("No token found in Redis. Nothing to remove.")
		return False


# Function to save the token to a JSON file
def save_token(token_data):
	"""Save token to file."""
	token_data['expires_at'] = (datetime.now() + timedelta(seconds=token_data['expires_in'])).isoformat()
	# save token in redis as json
	token_data = json.dumps(token_data)
	redis_client_env.set("twitch_token", token_data)


# Function to load the token from a JSON file
def load_token():
	"""Load token from Redis if it exists."""
	token_data = redis_client_env.get("twitch_token")
	if token_data:
		return json.loads(token_data)
	return None


def display_token_info():
	"""Display information about the current token."""
	token_data = load_token()
	if not token_data:
		print("No token found in Redis.")
		return False

	try:
		print("\n=== Token Information ===")

		# Display access token if available
		if 'access_token' in token_data:
			access_token = token_data['access_token']
			print(f"Access Token: {access_token[:5]}...{access_token[-5:]}")
		else:
			print("Access Token: Not found in token data")

		# Display expiration information if available
		if 'expires_at' in token_data:
			try:
				expires_at = datetime.fromisoformat(token_data['expires_at'])
				# Ensure expires_at is naive if it has timezone info
				if expires_at.tzinfo is not None:
					expires_at = expires_at.replace(tzinfo=None)
				now = datetime.now()
				time_left = expires_at - now

				print(f"Expires At: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")

				if now < expires_at:
					hours_left = time_left.total_seconds() / 3600
					print(f"Status: Valid (expires in {hours_left:.1f} hours)")
				else:
					print(f"Status: Expired (expired {abs(time_left.total_seconds() / 3600):.1f} hours ago)")
			except ValueError as e:
				print(f"Expiration Date: Error parsing date - {str(e)}")
		else:
			print("Expiration: Not found in token data")

		# Display refresh token if available
		if 'refresh_token' in token_data:
			refresh_token = token_data['refresh_token']
			print(f"Refresh Token: {refresh_token[:5]}...{refresh_token[-5:]}")
		else:
			print("Refresh Token: Not found in token data")

		# Display token type if available
		if 'token_type' in token_data:
			print(f"Token Type: {token_data['token_type']}")

		# Display scopes if available
		if 'scope' in token_data:
			scopes = token_data['scope']
			if isinstance(scopes, list):
				print(f"Scopes: {', '.join(scopes)}")
			else:
				print(f"Scopes: {scopes}")

		print("========================\n")
		return True
	except Exception as e:
		print(f"Error displaying token information: {str(e)}")
		return False


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
		try:
			expires_at = datetime.fromisoformat(token_data['expires_at'])
			# Ensure expires_at is naive if it has timezone info
			if expires_at.tzinfo is not None:
				expires_at = expires_at.replace(tzinfo=None)
			if datetime.now() < expires_at - timedelta(hours=1):
				return token_data['access_token']  # Token is valid
			print('Token expired. Refreshing...')
			return refresh_token(token_data['refresh_token'])
		except (KeyError, ValueError) as e:
			print(f'Error with token data: {str(e)}. Requesting a new token...')
			force_refresh_token()

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

	try:
		# Exchange the code for a token
		access_token = exchange_code_for_token(auth_code)
		print(f"\nToken successfully acquired! Token: {access_token[:5]}...{access_token[-5:]}")

		# Return a nice HTML response
		html_response = """
		<!DOCTYPE html>
		<html>
		<head>
			<title>Authorization Successful</title>
			<style>
				body {
					font-family: Arial, sans-serif;
					text-align: center;
					padding: 50px;
					background-color: #f5f5f5;
				}
				.container {
					background-color: white;
					border-radius: 10px;
					padding: 30px;
					box-shadow: 0 4px 8px rgba(0,0,0,0.1);
					max-width: 600px;
					margin: 0 auto;
				}
				h1 {
					color: #6441A4;
				}
				.success-icon {
					color: #28a745;
					font-size: 48px;
					margin-bottom: 20px;
				}
			</style>
		</head>
		<body>
			<div class="container">
				<div class="success-icon">✓</div>
				<h1>Authorization Successful!</h1>
				<p>The Twitch token has been successfully acquired and saved.</p>
				<p>You can now close this page and return to the terminal.</p>
			</div>
		</body>
		</html>
		"""

		# Schedule server shutdown after a short delay to ensure the page is displayed
		import threading
		threading.Timer(1.0, shutdown_server).start()

		return html_response
	except Exception as e:
		print(f"\nError during token exchange: {str(e)}")
		return f'Authorization failed: {str(e)}', 500

@app.route('/health', methods=['GET'])
def health():
	return jsonify({"status": "ok"}), 200


# Function to start the Flask server
def run_server():
	"""Run the Flask server to handle OAuth callback."""
	print('Starting local server to handle Twitch OAuth...')
	print('The server will automatically shut down after the authorization is complete.')
	print('If you encounter any issues, you can manually restart the process.')
	try:
		run_simple('0.0.0.0', 5000, app, use_reloader=False)
	except Exception as e:
		print(f"Error starting server: {str(e)}")
		raise


# Function to shut down the Flask server
def shutdown_server():
	"""Shutdown the Flask server."""
	print("\nAuthorization process complete. Shutting down server...")
	try:
		func = request.environ.get('werkzeug.server.shutdown')
		if func is None:
			print('Werkzeug server shutdown function not found. Using alternative shutdown method...')
			# Use threading to shutdown the server gracefully
			import threading
			threading.Thread(target=lambda: os._exit(0)).start()
		else:
			func()
			print("Server shutdown successful.")
	except Exception as e:
		print(f"Error during server shutdown: {str(e)}")
		print("Forcing process exit...")
		os._exit(0)  # Forcefully exit the process as a last resort


# Display menu and get user choice
def display_menu():
	"""Display an interactive menu and return the user's choice."""
	print("\n=== Twitch API Token Management ===")
	print("1. Get a valid token (refresh or new if needed)")
	print("2. Display information about the current token")
	print("3. Force refresh the token using the refresh token")
	print("4. Remove the current token and request a new one")
	print("5. Exit")
	print("===================================================")

	while True:
		try:
			choice = input("\nEnter your choice (1-5): ")
			choice = int(choice)
			if 1 <= choice <= 5:
				return choice
			else:
				print("Invalid choice. Please enter a number between 1 and 5.")
		except ValueError:
			print("Invalid input. Please enter a number.")


# Main script
if __name__ == '__main__':
	while True:
		try:
			choice = display_menu()

			if choice == 1:
				# Get a valid token (will request a new one if needed)
				access_token = get_valid_token()
				if access_token:
					print(f'\nAccess token obtained successfully: {access_token[:5]}...{access_token[-5:]}')
					print('Select option 2 to see more details about the token.')
				else:
					print('\nFailed to get access token')

			elif choice == 2:
				# Display token info
				if not display_token_info():
					print("\nNo token found. Select option 1 to obtain a new token.")

			elif choice == 3:
				# Force refresh the token using the refresh token
				token_data = load_token()
				if token_data and 'refresh_token' in token_data:
					print("\nRefreshing token...")
					access_token = refresh_token(token_data['refresh_token'])
					print(f"Token refreshed successfully: {access_token[:5]}...{access_token[-5:]}")
				else:
					print("\nNo valid token found to refresh. Select option 1 to request a new one.")

			elif choice == 4:
				# Force a new token by removing the current one
				if force_refresh_token():
					print("\nSelect option 1 to request a new token.")

			elif choice == 5:
				# Exit the program
				print("\nExiting program. Goodbye!")
				break

			# Pause before showing the menu again
			input("\nPress Enter to continue...")

		except Exception as e:
			print(f"\nError: {str(e)}")
			input("\nPress Enter to continue...")
