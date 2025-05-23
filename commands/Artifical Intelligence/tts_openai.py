#!/usr/bin/env python3
"""
TTS Command (OpenAI-based, direct to VBAN   )

This command listens for TTS requests and uses OpenAI's TTS API to generate speech from text, then sends the audio to the appropriate output (e.g., VBAN/OBS or other configured system).
"""
import json

from openai import OpenAI

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug
from module.shared_obs import send_text_to_voice
from module.shared_redis import redis_client_env, pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.tts')

##########################
# Exit Function
##########################
register_exit_handler()

##########################
# Helper Functions
##########################
def get_openai_api_key():
    """Get the OpenAI API key from Redis environment."""
    try:
        key = redis_client_env.get("OPENAI_API_KEY")
        if not key:
            error_msg = "OPENAI_API_KEY not found in redis_client_env."
            log_error(error_msg, "tts")
            raise RuntimeError(error_msg)
        log_debug("Successfully retrieved OpenAI API key", "tts")
        return key.decode("utf-8")
    except Exception as e:
        error_msg = f"Error retrieving OpenAI API key: {e}"
        log_error(error_msg, "tts", {"error": str(e)})
        raise

def generate_tts_audio(text, voice="alloy", model="tts-1"):
    """Generate text-to-speech audio using OpenAI API."""
    try:
        log_debug(f"Generating TTS audio (text length: {len(text)})", "tts", {
            "voice": voice,
            "model": model
        })

        api_key = get_openai_api_key()
        client = OpenAI(api_key=api_key)

        log_debug("Sending TTS request to OpenAI", "tts")
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text
        )

        # Save to a temp file (optional, for debugging)
        # with open("/tmp/tts_output.mp3", "wb") as f:
        #     f.write(response.content)

        log_info("TTS audio generated successfully", "tts", {
            "text_length": len(text),
            "audio_size": len(response.content)
        })
        return response.content
    except Exception as e:
        error_msg = f"Error generating TTS audio: {e}"
        log_error(error_msg, "tts", {"error": str(e), "text_length": len(text)})
        raise

def handle_tts_command(message_obj):
    """Handle a TTS command from a user."""
    try:
        author = message_obj.get('author', {})
        username = author.get('display_name', 'Unknown')
        text = message_obj.get('content', '')

        log_debug(f"Processing TTS command from {username}", "tts")

        if not text:
            log_info(f"TTS command received with no text from {username}", "tts")
            return

        log_info(f"TTS command received from {username}", "tts", {
            "text": text,
            "text_length": len(text)
        })

        try:
            # Generate TTS audio (not played here, just for demonstration)
            audio_bytes = generate_tts_audio(text)

            # Send the text to the output system (e.g., VBAN/OBS)
            log_debug(f"Sending text to voice system", "tts")
            send_text_to_voice.send(text)

            send_message_to_redis(f"{username} said: {text}")
            log_info(f"TTS processed successfully for {username}", "tts")
        except Exception as e:
            error_msg = f"Error processing TTS for {username}: {str(e)}"
            log_error(error_msg, "tts", {"error": str(e), "text": text})
            raise
    except Exception as e:
        error_msg = f"Error handling TTS command: {e}"
        log_error(error_msg, "tts", {"error": str(e)})
        print(error_msg)

##########################
# Main
##########################
log_startup("TTS command is ready to be used", "tts")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command', '')
            content = message_obj.get('content', '')
            user = message_obj.get('author', {}).get('display_name', 'Unknown')

            log_debug(f"TTS request received", "tts", {
                "command": command,
                "content_length": len(content),
                "user": user
            })

            handle_tts_command(message_obj)
        except json.JSONDecodeError as je:
            error_msg = f"JSON error in TTS command: {je}"
            print(error_msg)
            log_error(error_msg, "tts", {
                "error": str(je),
                "data": message.get('data', 'N/A')
            })
        except Exception as e:
            error_msg = f"Unexpected error in TTS command: {str(e)}"
            print(error_msg)
            log_error(error_msg, "tts", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
