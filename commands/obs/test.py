import requests


def translate_text_openai(text):
    """Translate text using OpenAI API."""
    try:
        system_prompt = (
            "You are a precise translation assistant. Follow these instructions exactly:\n"
            "1. For English input: Translate to German while preserving the original tone and style.\n"
            "2. For German input: Translate to English while preserving the original tone and style.\n"
            "3. For other languages: Translate to English while preserving the original tone and style.\n"
            "4. For idiomatic expressions or cultural references: Add a [detailed explanation in brackets].\n"
            "5. Preserve emojis, formatting.\n"
            "6. Automatically identify the language and translate accordingly."
        )

        remote_url = "http://192.168.50.51:11434/api/chat"  # ← adjust IP

        payload = {
            "model": "translator",  # Or another available model
            "messages": [
                {"role": "user", "content": text}
            ],
            "stream": False
        }

        response = requests.post(remote_url, json=payload)
        #print(response.json())


        translated_text = response.json()["message"]["content"]
        print(f"Original text: {text}")
        print(f"Translated Text: {translated_text}")

        return translated_text
    except Exception as e:
        error_msg = f"Error translating text: {e}"
        print(error_msg)
        raise

translate_text_openai("Bauernhof")
translate_text_openai("Farm")
translate_text_openai("wurstsalat")
translate_text_openai("Birne")
translate_text_openai("Hello, how are you? I hope you're doing well! 😊")
translate_text_openai("Hallo, wie geht es dir? Ich hoffe, es geht dir gut! 😊")
translate_text_openai("Das ist ein Test mit Emojis! 🚀🌟")