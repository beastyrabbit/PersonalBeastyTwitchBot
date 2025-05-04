#!/usr/bin/env python3
"""
Translate Command (AI-based, direct)

This command listens for translation requests and uses the OpenAI API to translate text between English and German, then sends the result to chat/admin as appropriate.
"""
import json

from openai import OpenAI

from module.message_utils import send_admin_message_to_redis, send_message_to_redis, register_exit_handler
from module.shared_redis import redis_client_env, pubsub

##########################
# Initialize
##########################
pubsub.subscribe('twitch.command.translate')
pubsub.subscribe('twitch.command.tr')

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
        "You are a precise translation assistant. Follow these instructions exactly:\n"
        "1. For English input: Translate to German while preserving the original tone and style.\n"
        "2. For German input: Translate to English while preserving the original tone and style.\n"
        "3. For other languages: Translate to English while preserving the original tone and style.\n"
        "4. For idiomatic expressions or cultural references: Add a [detailed explanation in brackets].\n"
        "5. Preserve emojis, formatting.\n"
        "6. Automatically identify the language and translate accordingly."
    )
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        max_tokens=200,
        temperature=0.2,  # Reduced temperature for more consistent translations
    )
    return completion.choices[0].message.content.strip()

def handle_translate_command(message_obj):
    """
    Processes a translation request and sends the response back.
    
    The message must contain text to translate after the '!translate' command.
    """
    author = message_obj.get('author', {})
    username = author.get('display_name', 'Unknown')
    mention = author.get('mention', username)
    
    # Extract text - remove the command if present
    full_content = message_obj.get('content', '').strip()
    text = full_content
    #strip command
    text = text.replace('!translate ','').replace('!tr ', '').strip()
    
    # Check if there's text to translate
    if not text:
        send_message_to_redis(f"{mention} Please provide text to translate. Example: !translate Hello world")
        send_admin_message_to_redis(f"Empty translation request from {username}")
        return

    send_admin_message_to_redis(f"Translation request from {username}: {text}")
    
    try:
        # Perform translation
        translation = translate_text_openai(text)
        
        # Format and send response
        send_message_to_redis(f"{mention} → {translation}")
        
    except Exception as e:
        error_message = str(e)
        send_message_to_redis(f"{mention} Sorry, an error occurred during translation.")
        send_admin_message_to_redis(f"Translation error for {username}: {error_message}")

##########################
# Main
##########################
send_admin_message_to_redis("Translation command is ready and listening for '!translate'")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command', '')
            content = message_obj.get('content', '')
            
            # More detailed logging for better diagnostics
            print(f"Translation request: Command={command}, Content={content}")
            
            # Process message
            handle_translate_command(message_obj)
            
        except json.JSONDecodeError as je:
            error_msg = f"JSON error in translation command: {je}"
            print(error_msg)
            send_admin_message_to_redis(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error in translation command: {str(e)}"
            print(error_msg)
            send_admin_message_to_redis(error_msg)