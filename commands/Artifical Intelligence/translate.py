#!/usr/bin/env python3
"""
Translate Command (AI-based, direct)

This command listens for translation requests and uses the OpenAI API to translate text between English and German, then sends the result to chat/admin as appropriate.
"""
import json

from openai import OpenAI

from module.message_utils import send_message_to_redis, register_exit_handler
from module.message_utils import log_startup, log_info, log_error, log_debug
from module.shared_redis import redis_client_env, pubsub

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "INFO"  # Use "DEBUG", "INFO", "WARNING", "ERROR", or "CRITICAL"

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
    """Get the OpenAI API key from Redis environment."""
    try:
        key = redis_client_env.get("OPENAI_API_KEY")
        if not key:
            error_msg = "OPENAI_API_KEY not found in redis_client_env."
            log_error(error_msg, "translate")
            raise RuntimeError(error_msg)
        log_debug("Successfully retrieved OpenAI API key", "translate")
        return key.decode("utf-8")
    except Exception as e:
        error_msg = f"Error retrieving OpenAI API key: {e}"
        log_error(error_msg, "translate", {"error": str(e)})
        raise

def translate_text_openai(text):
    """Translate text using OpenAI API."""
    try:
        log_debug(f"Translating text (length: {len(text)})", "translate")
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

        log_debug("Sending translation request to OpenAI", "translate")
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            max_tokens=200,
            temperature=0.2,  # Reduced temperature for more consistent translations
        )

        translated_text = completion.choices[0].message.content.strip()
        log_info("Translation completed successfully", "translate", {
            "original_length": len(text),
            "translated_length": len(translated_text)
        })
        return translated_text
    except Exception as e:
        error_msg = f"Error translating text: {e}"
        log_error(error_msg, "translate", {"error": str(e), "text_length": len(text)})
        raise

def handle_translate_command(message_obj):
    """
    Processes a translation request and sends the response back.

    The message must contain text to translate after the '!translate' command.
    """
    try:
        author = message_obj.get('author', {})
        username = author.get('display_name', 'Unknown')
        mention = author.get('mention', username)

        log_debug(f"Processing translation request from {username}", "translate")

        # Extract text - remove the command if present
        full_content = message_obj.get('content', '').strip()
        text = full_content
        # Strip command
        text = text.replace('!translate ','').replace('!tr ', '').strip()

        # Check if there's text to translate
        if not text:
            log_info(f"Empty translation request from {username}", "translate")
            send_message_to_redis(f"{mention} Please provide text to translate. Example: !translate Hello world")
            return

        log_info(f"Translation request from {username}", "translate", {
            "text": text,
            "text_length": len(text)
        })

        try:
            # Perform translation
            translation = translate_text_openai(text)

            log_info(f"Translation completed for {username}", "translate", {
                "original_text": text,
                "translated_text": translation
            })

            # Format and send response
            send_message_to_redis(f"{mention} → {translation}")

        except Exception as e:
            error_message = str(e)
            log_error(f"Translation error for {username}", "translate", {
                "error": error_message,
                "text": text
            })
            send_message_to_redis(f"{mention} Sorry, an error occurred during translation.")
    except Exception as e:
        error_msg = f"Error handling translation command: {e}"
        log_error(error_msg, "translate", {"error": str(e)})
        print(error_msg)

##########################
# Main
##########################
log_startup("Translation command is ready and listening for '!translate'", "translate")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            message_obj = json.loads(message['data'].decode('utf-8'))
            command = message_obj.get('command', '')
            content = message_obj.get('content', '')
            user = message_obj.get('author', {}).get('display_name', 'Unknown')

            # More detailed logging for better diagnostics
            log_debug(f"Translation request received", "translate", {
                "command": command,
                "content_length": len(content),
                "user": user
            })

            # Process message
            handle_translate_command(message_obj)

        except json.JSONDecodeError as je:
            error_msg = f"JSON error in translation command: {je}"
            print(error_msg)
            log_error(error_msg, "translate", {
                "error": str(je),
                "data": message.get('data', 'N/A')
            })
        except Exception as e:
            error_msg = f"Unexpected error in translation command: {str(e)}"
            print(error_msg)
            log_error(error_msg, "translate", {
                "error": str(e),
                "traceback": str(e.__traceback__),
                "message_data": str(message.get('data', 'N/A'))
            })
