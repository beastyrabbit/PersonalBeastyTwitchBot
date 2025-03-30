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

# Configuration constants
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
TOKEN_FILE = os.path.join(BASE_DIR, 'twitch_token.json')
CHANNEL_NAME = 'Beastyrabbit'
REDIS_HOST = '192.168.50.115'
REDIS_PORT = 6379
BotList = ["suika", "economy", "shoutout", "raid"]  # Added sample bot names
global_pubsub = {}

# Redis clients
redis_client_env = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=1)

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
	token_data = redis_client_env.get("twitch_token")
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


# Service management functions (unchanged)
def force_update_service(action):
	"""Force update the main helper service."""
	full_action_name = "beastyhelper.service"
	try:
		result = subprocess.run(
			["systemctl", action, full_action_name],
			stderr=subprocess.PIPE,
			stdout=subprocess.PIPE,
			text=True,
			check=True
		)
		return result.stdout
	except subprocess.CalledProcessError as err:
		return f"Error: {err.stderr}"


def manage_service(service_name, action):
	"""Manage a bot service by name."""
	full_action_name = f"beasty_{service_name}_bot.service"
	try:
		result = subprocess.run(
			["systemctl", action, full_action_name],
			stderr=subprocess.PIPE,
			stdout=subprocess.PIPE,
			text=True,
			check=True
		)
		return result.stdout
	except subprocess.CalledProcessError as err:
		return f"Error: {err.stderr}"


# Message processing functions (unchanged)
def is_message_a_command(message):
	"""Check if message starts with a command prefix."""
	return message.content.startswith("!")


def get_command_from_message(message):
	"""Extract command from message content."""
	command = message.content.split()[0]
	return command[1:]  # Remove the ! prefix


def evaluate_message_and_publish(bot, message):
	"""Process and publish message to appropriate Redis channels."""
	# Create unified message object
	message_obj = {
		"type": "chat",
		"timestamp": datetime.now().isoformat(),
		"source": "twitch",
		"content": message.content,
		"metadata": {
			"channel": message.channel.name,
			"room_id": message.tags.get('room-id')
		},
		"author": {
			"name": message.author.name,
			"display_name": message.author.display_name,
			"mention": message.author.mention,
			"color": message.author.color,
			"badges": message.author.badges,
			"moderator": message.author.is_mod,
			"subscriber": message.author.is_subscriber,
			"vip": message.author.is_vip,
			"broadcaster": message.author.is_broadcaster,
			"emotes": message.tags.get('emotes'),
		},
		"event_data": {}
	}

	if message.author.name == "beastyhelper":
		message_obj["type"] = "helper"

	# Handle command messages
	if is_message_a_command(message):
		command = get_command_from_message(message)
		message_obj["event_data"]["command"] = command
		message_obj["type"] = "command"
		print(f"Command Message: {message_obj}")
		bot.redis_client.publish(f'twitch.command.{command}', json.dumps(message_obj))
	else:
		print(f"Normal Message: {message_obj}")
		bot.redis_client.publish('twitch.chat.recieved', json.dumps(message_obj))


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
		self._loop.create_task(self.send_shoutout_task())
		self._loop.create_task(self.fetch_users_task())
		self._loop.create_task(self.send_announcement_task())

	# Event handlers (unchanged)
	async def event_ready(self):
		"""Handle bot ready event."""
		print(f'Logged in as | {self.nick}')
		print(f'User id is | {self.user_id}')
		self.hourly_check.start()

		# Make sure the channel is connected before sending
		channel = self.get_channel(CHANNEL_NAME)
		if channel:
			await channel.send("Bunny Manager is online!")
		else:
			print(f"Warning: Channel {CHANNEL_NAME} not found on startup")

		await self.setup()

	async def event_message(self, message):
		"""Process incoming messages."""
		# Ignore bot's own messages
		if message.echo:
			return

		# Update message counter
		try:
			message_count = self.redis_client.hget('stream:global', 'messege_counter')
			message_count = int(message_count) if message_count else 0
			message_count += 1
			self.redis_client.hset('stream:global', 'messege_counter', message_count)
		except Exception as e:
			print(f"Error updating message counter: {e}")

		# Handle commands and publish message
		#await self.handle_commands(message)
		evaluate_message_and_publish(self, message)

	async def fetch_users_task(self):
		"""Task to handle user fetch requests from Redis using XADD and XREAD."""
		print("Starting fetch_users task using XADD/XREAD...")

		request_stream = "request_stream"
		group_name = "user_fetch_group"
		consumer_name = "consumer_" + str(uuid.uuid4())[:8]  # Unique consumer name

		try:
			# Ensure the consumer group exists
			try:
				self.redis_client.xgroup_create(
					request_stream, groupname=group_name, id='0', mkstream=True
				)
			except redis.exceptions.ResponseError as e:
				if str(e) == "BUSYGROUP Consumer Group name already exists":
					print("Consumer group already exists.")
				else:
					raise e

			while True:
				try:
					# Use XREADGROUP to read from the stream
					messages = self.redis_client.xreadgroup(
						groupname=group_name,
						consumername=consumer_name,
						streams={request_stream: '>'},  # Only read new messages
						count=1,
						block=5000,  # Block for 5 seconds
					)

					if not messages:
						await asyncio.sleep(0.1)  # If no messages, sleep briefly
						continue

					stream_name, messages_list = messages[0]
					message_id, message_data = messages_list[0]

					# Process the message
					data = {
						k.decode('utf-8'): v.decode('utf-8')
						for k, v in message_data.items()
					}
					request_id = data.get('request_id')
					request_type = data.get('type')

					if request_type == 'fetch_user' and 'username' in data:
						username = data['username']
						try:
							# Use TwitchIO's API to fetch user data
							users = await self.fetch_users(names=[username])
							response = {
								'request_id': request_id,
								'success': True,
								'data': {
									'username': users[0].name if users else None,
									'user_id': users[0].id if users else None,
								},
							}
						except Exception as e:
							print(f"Error fetching user {username}: {e}")
							response = {
								'request_id': request_id,
								'success': False,
								'error': str(e),
							}

						# Publish the response to a dedicated stream
						response_stream = f'response_stream:{request_id}'
						self.redis_client.xadd(
							response_stream, {'user_data': json.dumps(response)}
						)

					elif request_type == 'fetch_channels' and 'user_id' in data:
						user_id = data['user_id']
						try:
							# Use TwitchIO's API to fetch channel data
							channels = await self.fetch_channels(
								broadcaster_ids=[user_id]
							)
							response = {
								'request_id': request_id,
								'success': True,
								'data': {
											'game_name': channels[0].game_name,
											'title': channels[0].title,
								}
							}
						except Exception as e:
							print(
								f"Error fetching channel for user_id {user_id}: {e}"
							)
							response = {
								'request_id': request_id,
								'success': False,
								'error': str(e),
							}

						# Publish the response to a dedicated stream
						response_stream = f'response_stream:{request_id}'
						self.redis_client.xadd(
							response_stream, {'channel_data': json.dumps(response)}
						)

					# Acknowledge the message as processed
					self.redis_client.xack(request_stream, group_name, message_id)

				except Exception as e:
					print(f"Error in fetch_users_task: {e}")
					await asyncio.sleep(1)  # Wait a bit before retrying

		except Exception as e:
			print(f"Fatal error in fetch_users_task setup: {e}")

	# Other background tasks (unchanged)
	async def send_shoutout_task(self):
		"""Task to listen for shoutout requests from Redis."""
		print("Starting send_shoutout task...")

		try:
			self.pubsub['shoutout'] =  self.redis_client.pubsub()
			self.pubsub['shoutout'].subscribe('twitch.chat.shoutout')

			# Create user object for API calls
			user = self.create_user('29319793', 'Beastyrabbit')

			while True:
				message = self.pubsub['shoutout'].get_message(ignore_subscribe_messages=True)
				if message:
					try:
						msg_content = message["data"].decode("utf-8")
						print(f"Shoutout request: {msg_content}")
						await user.shoutout(
							to_broadcaster_id=msg_content,
							moderator_id='1215902100',
							token=self.access_token
						)
						print(f"Sent shoutout to: {msg_content}")
					except Exception as e:
						print(f"Error sending shoutout: {e}")
				await asyncio.sleep(0.1)
		except Exception as e:
			print(f"Error in send_shoutout_task: {e}")

	async def send_announcement_task(self):
		"""Task to listen for announcement requests from Redis."""
		print("Starting send_announcement task...")

		try:

			self.pubsub['announcement'] =  self.redis_client.pubsub()
			self.pubsub['announcement'].subscribe('twitch.chat.announcement')

			user = self.create_user('29319793', 'Beastyrabbit')

			while True:
				message = self.pubsub['announcement'].get_message(ignore_subscribe_messages=True)
				if message and message["data"] != 1:  # Skip initial subscribe message
					try:
						msg_content = message["data"].decode("utf-8")
						print(f"Announcement request: {msg_content}")
						await user.chat_announcement(
							token=self.access_token,
							moderator_id='1215902100',
							message=msg_content,
							color='purple'
						)
						print(f"Sent announcement: {msg_content}")
					except Exception as e:
						print(f"Error sending announcement: {e}")
				await asyncio.sleep(0.1)
		except Exception as e:
			print(f"Error in send_announcement_task: {e}")

	async def send_message_task(self):
		"""Task to listen for chat message requests from Redis."""
		print("Starting send_message task...")

		try:

			self.pubsub['chat_send'] =  self.redis_client.pubsub()

			self.pubsub['chat_send'].subscribe('twitch.chat.send')

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

	# Routine and command handlers (unchanged)
	@routines.routine(hours=1)
	async def hourly_check(self):
		"""Periodic check to send engagement reminders."""
		try:
			message_count = self.redis_client.hget('stream:global', 'messege_counter')
			message_count = int(message_count) if message_count else 0
			print(f'Current Message count for hourly message: {message_count}')

			if message_count > 20:
				channel = self.get_channel(CHANNEL_NAME)
				if channel:
					await channel.send(
						'If you like the Content please consider following and check out the discord! 🐰🐻 '
						'Do you want to play Suikagame? Type !suika in chat 🍉🍉🍉 '
						'Get your shitty Doodle with some Carrot Charms!'
					)
					self.redis_client.hset('stream:global', 'messege_counter', 0)
				else:
					print(f"Warning: Channel {CHANNEL_NAME} not found for hourly message")
			else:
				print('Message count was below 20, no message sent.')
		except Exception as e:
			print(f"Error in hourly check: {e}")

	@commands.command(name='manage', aliases=["run"])
	async def manage_command(self, ctx: commands.Context, action: str, bot_name: str, get_output: bool = False):
		"""Command to manage bot services."""
		print(f"Trying to {action} {bot_name}")

		# Check permissions
		if not ctx.author.is_mod:
			print(f"User {ctx.author.name} tried to access the bot {bot_name} with action {action} (not a mod)")
			return

		# Handle special cases
		if bot_name == 'all':
			for bot in BotList:
				message = manage_service(bot, action)
				print(f"Return Message for {bot}: {message}")
			await ctx.send("All bots managed successfully!")
			return

		if bot_name == 'master':
			message = force_update_service(action)
			print(f"Return Message for master: {message}")
			if get_output and message:
				trimmed_message = message[-490:] if len(message) > 490 else message
				await ctx.send(trimmed_message)
			return

		# Handle specific bot
		if bot_name in BotList:
			message = manage_service(bot_name, action)
			print(f"Return Message for {bot_name}: {message}")
			if get_output and message:
				trimmed_message = message[-490:] if len(message) > 490 else message
				await ctx.send(trimmed_message)
		else:
			await ctx.send(f"Bot not found: {bot_name}. Available bots: {', '.join(BotList)}")


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
