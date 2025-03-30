import asyncio
from twitchio import Client

# Replace with your actual OAuth token and client ID
TOKEN = "your_oauth_token_here"
CLIENT_ID = "your_client_id_here"

async def get_followed_channels():
    # Initialize the TwitchIO client
    client = Client(token=TOKEN, client_id=CLIENT_ID)

    # Fetch user information
    users = await client.fetch_users(token=TOKEN)
    if not users:
        print("Failed to retrieve user information.")
        return

    user = users[0]
    user_id = user.id

    # Fetch the list of followed channels
    followed_channels = await client.fetch_channel_following(token=TOKEN, broadcaster_id=user_id)

    # Display the followed channels
    for follow in followed_channels:
        print(f"Channel: {follow.to_name} (ID: {follow.to_id})")

    # Close the client connection
    await client.close()

# Run the asynchronous function
asyncio.run(get_followed_channels())
