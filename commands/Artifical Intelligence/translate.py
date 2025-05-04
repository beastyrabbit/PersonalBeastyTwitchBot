#!/usr/bin/env python3
"""
Translate Command (AI-based, direct)

This command listens for translation requests and uses the OpenAI API to translate text between English and German, then sends the result to chat/admin as appropriate.
"""
import json
import os
from openai import OpenAI
from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared import redis_client, redis_client_env, pubsub

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.translate')

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

def translate_text_openai(text):
    api_key = get_openai_api_key()
    client = OpenAI(api_key=api_key)
    system_prompt = (
        "You are a translation assistant. If the input is English, translate it to German. "
        "If the input is German, translate it to English. "
        "If the translation is not 1 to 1, add a very short, soft explanation. "
        "If the input is a sentence, translate the sentence. "
        "Your answer should be very short."
    )
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        max_tokens=200,
        temperature=0.3,
    )
    return completion.choices[0].message.content.strip()

def handle_translate_command(message_obj):
    author = message_obj.get('author', {})
    username = author.get('display_name', 'Unknown')
    text = message_obj.get('content', '')
    if not text:
        send_admin_message_to_redis(f"Translate command received with no text from {username}.")
        return

    send_admin_message_to_redis(f"Translate command received from {username}: {text}")
    try:
        translation = translate_text_openai(text)
        send_message_to_redis(f"{username} translation: {translation}")
    except Exception as e:
        send_admin_message_to_redis(f"Error processing translation for {username}: {str(e)}")

##########################
# Main
##########################
send_admin_message_to_redis("Translate command is ready to be used.")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            handle_translate_command(message_obj)
        except Exception as e:
            print(f"Error processing translate command: {e}")
            send_admin_message_to_redis(f"Error in translate command: {str(e)}") 