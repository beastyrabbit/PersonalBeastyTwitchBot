import asyncio
import json
import os
import signal
import subprocess
import sys
import uuid
from datetime import datetime

import redis
from twitchio.ext import commands, routines
from module.shared import redis_client_env

# Configuration constants
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
CHANNEL_NAME = 'Beastyrabbit'
REDIS_HOST = '192.168.50.115'
REDIS_PORT = 6379
global_pubsub = {}

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
	print("Unsubscribing from all channels bofore exiting")
	global global_pubsub
	for pubsub in global_pubsub.values():
		pubsub.unsubscribe()
	# Place any cleanup code here
	sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)


# Token management functions (unchanged)
def load_token():
	"""Load token from Redis database."""
	token_data = redis_client_env.get("twitch_token_main")
	if token_data:
		return json.loads(token_data)
	return None


def get_valid_token():
	"""Ensure a valid token is available, refreshing if needed."""
	token_data = load_token()
	if token_data:
		expires_at = datetime.fromisoformat(token_data['expires_at'])
		if datetime.now() < expires_at:
			return token_data['access_token']  # Token is valid
		print('Token expired, re-authorizing...')
	return None  # Token expired or missing





# Bot Class
class Bot(commands.Bot):
	def __init__(self):
		access_token = get_valid_token()
		if not access_token:
			raise ValueError("Failed to get valid access token")

		self.redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=0)
		self.access_token = access_token
		self.number_of_send_messages = 0
		self.pubsub = {}
		global global_pubsub
		global_pubsub= self.pubsub

		super().__init__(token=access_token, prefix='!', initial_channels=[CHANNEL_NAME])
		self._loop = None  # Will be set when bot starts

	async def setup(self):
		"""Create background tasks after connection."""
		self._loop = asyncio.get_running_loop()
		self._loop.create_task(self.send_message_task())

	# Event handlers (unchanged)
	async def event_ready(self):
		"""Handle bot ready event."""
		print(f'Logged in as | {self.nick}')
		print(f'User id is | {self.user_id}')

		# Make sure the channel is connected before sending
		channel = self.get_channel(CHANNEL_NAME)
		if channel:
			await channel.send("Bunny Main Manager is online!")
		else:
			print(f"Warning: Channel {CHANNEL_NAME} not found on startup")

		await self.setup()

	async def event_message(self, message):
		"""Process incoming messages."""
		# Ignore bot's own messages
		if message.echo:
			return

		# Update message counter
		# Handle commands and publish message
		#await self.handle_commands(message)




	async def send_message_task(self):
		"""Task to listen for chat message requests from Redis."""
		print("Starting send_message task...")

		try:

			self.pubsub['chat_send'] =  self.redis_client.pubsub()

			self.pubsub['chat_send'].subscribe('twitch.chat.main.send')

			while True:
				message = self.pubsub['chat_send'].get_message(ignore_subscribe_messages=True)
				if message and message["data"] != 1:  # Skip initial subscribe message
					try:
						msg_content = message["data"].decode("utf-8")
						print(f"Chat message request: {msg_content}")

						# Get channel object and verify it exists before sending
						channel = self.get_channel(CHANNEL_NAME)
						if channel:
							await channel.send(msg_content)
							print(f"Sent message: {msg_content}")
						else:
							print(f"Error: Channel {CHANNEL_NAME} not found. Message not sent.")
					except Exception as e:
						print(f"Error sending chat message: {e}")
				await asyncio.sleep(0.1)
		except Exception as e:
			print(f"Error in send_message_task: {e}")



# Main execution
def main():
	"""Main entry point for the bot."""
	try:
		bot = Bot()
		bot.run()
	except Exception as e:
		print(f"Fatal error: {e}")


if __name__ == "__main__":
	main()
