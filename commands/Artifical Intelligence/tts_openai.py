#!/usr/bin/env python3
"""
TTS Command (OpenAI-based, direct to VBAN   )

This command listens for TTS requests and uses OpenAI's TTS API to generate speech from text, then sends the audio to the appropriate output (e.g., VBAN/OBS or other configured system).
"""
import json

from openai import OpenAI

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared_obs import send_text_to_voice
from module.shared_redis import redis_client_env, pubsub

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
    key = redis_client_env.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not found in redis_client_env.")
    return key.decode("utf-8")

def generate_tts_audio(text, voice="alloy", model="tts-1"):
    api_key = get_openai_api_key()
    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text
    )
    # Save to a temp file (optional, for debugging)
    # with open("/tmp/tts_output.mp3", "wb") as f:
    #     f.write(response.content)
    return response.content

def handle_tts_command(message_obj):
    author = message_obj.get('author', {})
    username = author.get('display_name', 'Unknown')
    text = message_obj.get('content', '')
    if not text:
        send_admin_message_to_redis(f"TTS command received with no text from {username}.")
        return

    send_admin_message_to_redis(f"TTS command received from {username}: {text}")
    try:
        # Generate TTS audio (not played here, just for demonstration)
        audio_bytes = generate_tts_audio(text)
        # Send the text to the output system (e.g., VBAN/OBS)
        send_text_to_voice.send(text)
        send_message_to_redis(f"{username} said: {text}")
    except Exception as e:
        send_admin_message_to_redis(f"Error processing TTS for {username}: {str(e)}")

##########################
# Main
##########################
send_admin_message_to_redis("TTS command is ready to be used.")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            handle_tts_command(message_obj)
        except Exception as e:
            print(f"Error processing TTS command: {e}")
            send_admin_message_to_redis(f"Error in TTS command: {str(e)}") 