import subprocess

from twitchio.ext import commands

from helperfunc.base_values import CHANNEL_NAME, setup_logger, get_valid_token
from helperfunc.object_manager import UserManager, ObjectManager
from helperfunc.setting import BotList

# TODO: Channelpoint integration


# TODO: figure out how to do
# TODO: add emote to logs
# TODO: steal with log chance up to 10 times the current max (only in invenetory not bank)
# TODO: heist were you can get money from the bank


# TODO: For later
# TODO: Song request
# TODO: BTTV and 7TV emote requests
# TODO: add a discord chat bot integration
# TODO: time left on timer

# TODO: back back burner
# TODO: Only run bot when live
# TODO: Polls
# TODO: ads timer and message
# TODO: # Gambling commands / Slots / ?Blackjack (Streamavatars => how do the points work)
# TODO: Twitch plays

# TODO: When Streaming PC is working
# TODO: add tts on local machine with pngtuber
# TODO: add own Chatclient

#TODO: Add TTS Command to pronounce users


_logger = setup_logger(__name__)


def force_update_service(action):
	full_action_name = f"beastyhelper.service"
	try:
		# Run the systemctl command using subprocess
		result = subprocess.run(
			["systemctl", action, full_action_name],
			stderr=subprocess.PIPE,
			stdout=subprocess.PIPE,
			text=True,
			check=True
		)
		return result.stdout
	except subprocess.CalledProcessError as err:
		# Return the error output if the command fails
		return f"Error: {err.stderr}"


def manage_service(service_name, action):
	full_action_name = f"beasty_{service_name}_bot.service"
	try:
		# Run the systemctl command using subprocess
		result = subprocess.run(
			["systemctl", action, full_action_name],
			stderr=subprocess.PIPE,
			stdout=subprocess.PIPE,
			text=True,
			check=True
		)
		return result.stdout
	except subprocess.CalledProcessError as err:
		# Return the error output if the command fails
		return f"Error: {err.stderr}"



class Bot(commands.Bot):
	def __init__(self):
		# Initialise our Bot with our access token, prefix and a list of channels to join on boot...
		# prefix can be a callable, which returns a list of strings or a string...
		# initial_channels can also be a callable which returns a list of strings...
		access_token = get_valid_token()
		self.access_token = access_token
		self.object_manager = ObjectManager()
		self.user_manager: UserManager = self.object_manager.user_manager

		self.number_of_send_messages = 0
		super().__init__(token=access_token, prefix='!', initial_channels=[CHANNEL_NAME])

	async def event_command_error(self, context: commands.Context, error: Exception):
		if isinstance(error, commands.CommandNotFound):
			return

		if isinstance(error, commands.ArgumentParsingFailed):
			await context.send(error.message)

		elif isinstance(error, commands.MissingRequiredArgument):
			await context.send("You're missing an argument: " + error.name)

		elif isinstance(error, commands.CheckFailure):  # we'll explain checks later, but lets include it for now.
			await context.send('Sorry, you cant run that command: ' + error.args[0])

		#
		# elif isinstance(error, YoutubeConverterError):
		#  await context.send(f'{error.link} is not a valid youtube URL!')

		else:
			_logger.error(error)

	async def event_ready(self):
		# Notify us when everything is ready!
		# We are logged in and ready to chat and use commands...
		_logger.info(f'Logged in as | {self.nick}')
		_logger.info(f'User id is | {self.user_id}')
		await self.get_channel(CHANNEL_NAME).send("Bunny Manager is online!")

	async def event_message(self, message):
		# Messages with echo set to True are messages sent by the bot...
		# For now we just want to ignore them...
		if message.echo:
			return
		# Since we have commands and are overriding the default `event_message`
		# We must let the bot know we want to handle and invoke our commands...
		await self.handle_commands(message)

	@commands.command(name='manage', aliases=["run"])
	async def manage_command(self, ctx: commands.Context, action: str, bot_name: str, get_output: bool = False):
		_logger.info(f"Trying to {action} {bot_name} ")
		if not ctx.author.is_mod:
			_logger.warning(f"User {ctx.author.name} tryed to acces the Bots {bot_name} and action {action}")
			return

		if bot_name == 'all':
			for bot in BotList:
				message = manage_service(bot.value, action)
				_logger.info(f"Return Message for {bot.value}: {message}")
			await ctx.send("All Bots started!")
			return

		if bot_name == 'master':
			message = force_update_service(action)
			_logger.info(f"Return Message for master: {message}")
			# Only print last 490 chars because of transfer limit, ensure message is not None
			if get_output:
				if message:
					trimmed_message = message[-490:] if len(message) > 490 else message
					await ctx.send(trimmed_message)
				else:
					await ctx.send("No output received from the service command.")

		bot_found = False
		for bot in BotList:
			if bot.value == bot_name:
				message = manage_service(bot.value, action)
				_logger.info(f"Return Message for {bot.value}: {message}")
				# Only print last 490 chars because of transfer limit, ensure message is not None
				if get_output:
					if message:
						trimmed_message = message[-490:] if len(message) > 490 else message
						await ctx.send(trimmed_message)
					else:
						await ctx.send("No output received from the service command.")
					bot_found = True

		if not bot_found:
			await ctx.send(f"Typo in Botname: {bot_name}")


bot = Bot()
bot.run()
