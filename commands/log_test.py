#!/usr/bin/env python3
"""Test script for sending log messages at different levels.

This script provides a menu-driven interface for sending test log messages
at different log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL, STARTUP).
It can be used to test the logging system and verify that messages are
displayed correctly and sent to OBS.
"""
import json
import sys
import time

from module.message_utils import (
    register_exit_handler, log_message,
    log_important
)
from module.shared_redis import redis_client

##########################
# Configuration
##########################
# Set the log level for this command
LOG_LEVEL = "DEBUG"  # Use lowest level to ensure all messages are processed

##########################
# Initialize
##########################
# Register SIGINT handler for clean exit
register_exit_handler()

##########################
# Helper Functions
##########################
def print_menu():
    """Print the main menu options."""
    print("\n===== Log Test Menu =====")
    print("1. Send DEBUG message")
    print("2. Send INFO message")
    print("3. Send WARNING message")
    print("4. Send ERROR message")
    print("5. Send CRITICAL message")
    print("6. Send IMPORTANT message")
    print("7. Send STARTUP message")
    print("8. Send custom message (with options)")
    print("9. Send all test messages")
    print("0. Exit")
    print("========================")
    return input("Enter your choice (0-9): ")

def send_test_message(level, custom_message=None, extra_data=None):
    """Send a test message at the specified log level.

    @param level: The log level to use
    @param custom_message: Optional custom message text
    @param extra_data: Optional extra data to include in the message
    """
    message = custom_message or f"This is a test {level} message sent at {time.strftime('%H:%M:%S')}"

    # Use log_message directly for all log levels except IMPORTANT
    if level == "IMPORTANT":
        log_important(message, "log_test", extra_data)
    else:
        log_message(level, message, "log_test", extra_data)

    print(f"Sent {level} message: {message}")
    return True

def get_custom_message():
    """Get a custom message from the user."""
    return input("Enter your custom message: ")

def get_custom_options():
    """Get custom styling options from the user."""
    print("\n=== Custom Styling Options ===")
    print("Leave blank to use default values")

    style = input("Style (message, error, highlight): ").strip()
    color = input("Color (hex code, e.g. #FF0000): ").strip()
    icon = input("Icon (e.g. star, rocket, bug): ").strip()

    extra_data = {}
    if style:
        extra_data['style'] = style
    if color:
        extra_data['color'] = color
    if icon:
        extra_data['icon'] = icon

    # For highlight style, ask for highlight color
    if style == "highlight":
        highlight_color = input("Highlight color (hex code): ").strip()
        if highlight_color:
            extra_data['highlightColor'] = highlight_color

    # For error style, ask if it can be closed
    if style == "error":
        can_close = input("Can close? (y/n): ").strip().lower()
        if can_close == 'y':
            extra_data['canClose'] = True

    return extra_data

def send_all_test_messages():
    """Send test messages at all log levels."""
    print("\nSending test messages at all log levels...")

    send_test_message("DEBUG")
    time.sleep(0.5)  # Add a small delay between messages

    send_test_message("INFO")
    time.sleep(0.5)

    send_test_message("WARNING")
    time.sleep(0.5)

    send_test_message("ERROR")
    time.sleep(0.5)

    send_test_message("CRITICAL")
    time.sleep(0.5)

    send_test_message("IMPORTANT")
    time.sleep(0.5)

    send_test_message("STARTUP")

    print("All test messages sent!")

##########################
# Main
##########################
def main():
    """Main function that runs the interactive menu."""
    # Send startup message
    log_message("STARTUP", "Log test script is ready to be used", "log_test", {
        "version": "1.0.0",
        "config": {
            "log_level": LOG_LEVEL
        }
    })

    print("Log Test Script")
    print("This script allows you to send test log messages at different levels.")

    while True:
        choice = print_menu()

        if choice == "0":
            print("Exiting...")
            break

        elif choice == "1":
            send_test_message("DEBUG")

        elif choice == "2":
            send_test_message("INFO")

        elif choice == "3":
            send_test_message("WARNING")

        elif choice == "4":
            send_test_message("ERROR")

        elif choice == "5":
            send_test_message("CRITICAL")

        elif choice == "6":
            send_test_message("IMPORTANT")

        elif choice == "7":
            send_test_message("STARTUP")

        elif choice == "8":
            # Custom message with options
            level_choice = input("\nSelect log level (1-7): ")
            level_map = {
                "1": "DEBUG",
                "2": "INFO",
                "3": "WARNING",
                "4": "ERROR",
                "5": "CRITICAL",
                "6": "IMPORTANT",
                "7": "STARTUP"
            }

            if level_choice in level_map:
                level = level_map[level_choice]
                message = get_custom_message()
                extra_data = get_custom_options()
                send_test_message(level, message, extra_data)
            else:
                print("Invalid log level choice")

        elif choice == "9":
            send_all_test_messages()

        else:
            print("Invalid choice. Please try again.")

        # Add a small delay before showing the menu again
        time.sleep(1)

if __name__ == "__main__":
    main()
