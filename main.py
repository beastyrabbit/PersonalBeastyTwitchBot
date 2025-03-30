import signal
import sys
import time

def handle_exit(signum, frame):
    print("\nSIGINT received! Cleaning up before exit...")
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

print("Running... Press Ctrl+C to exit.")

# Simulate a long-running process
while True:
    try:
        time.sleep(1)  # Sleep to reduce CPU usage
    except Exception as e:
        print(f"Exception caught: {e}")
