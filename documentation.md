# Documenation for Twitchbot
This is the documentation for the Twitchbot. It is a simple bot that can be used to interact with the Twitch chat. It can be used to send messages to the chat, read messages from the chat, and perform other actions. The bot is written in Python and uses the Twitch API to interact with the chat.
## Chat Commands
### Dustbunnies Commands
#### !roomba
Alternative command: 
``` !clean !vacuum ```
#### !give
Alternative command: 
``` !donate !share !gift ```
Command Syntax: 
``` !give <@user> <amount> ```

### !steal
Alternative command: 
``` !rob  ```
Command Syntax: 
``` !steal <@user> ```

## Banking Commands
### !collect
Alternative command: 
``` !interest ```
### !invest
Alternative command: 
``` !deposit !investment !investments !bank !banking !investing ```
Command Syntax: 
``` !invest <amount> ```
## General Commands
### !points
Alternative command: 
``` !stats !balance !dustbunnies ```
### !lurk
Alternative command: 
``` !hide !away !offline ```
### !unlurk
Alternative command: 
``` !show !back !online ```
### !suike
Command Syntax: 
``` !suike <time in minutes> ```
Default time is 5 minutes
### !timezone
Alternative command: 
``` !time ```
### !timer
Alternative command: 
``` !countdown !clock ```
Command Syntax: 
``` !timer <name> <time in minutes> ```


## Admin Commands
### !brb
Alternative command: 
``` !pause !break ```
Command Syntax: 
``` !brb <time in minutes> ```

### !unbrb

### !discord

### !so
Alternative command: 
``` !shoutout !host ```

### !todo
Alternative command: 
``` !tasks !list !todolist ```

Command Syntax: 
If no group is added "default" will be autoadded
``` !todo add <group> <task> ```
``` !todo add  <task> ```

``` !todo remove <task id> ```

``` !todo remove <group> ```

``` !todo remove ``` (remove first element)

``` !todo complete <task id> ```

``` !todo complete <group> ```

``` !todo clear  ``` (clear all)

### !hug
Alternative command: 
``` !cuddle !snuggle ```
Command Syntax: 
``` !hug <@user> ```
Description: 
Sends a random, fun hug message to the mentioned user. If no user is mentioned, hugs the world.

### !slots
Alternative command: 
``` !slot ```
Command Syntax: 
``` !slots <amount> ```  
``` !slots all ```
Description: 
Play the slot machine with the specified amount of dustbunnies or all your dustbunnies. Win or lose based on matching symbols.

### !blackjack
Alternative command: 
``` !bj ```
Command Syntax: 
``` !blackjack join ```  
``` !blackjack hit ```  
``` !blackjack stand ```  
``` !blackjack double ```  
``` !blackjack split ```
Description: 
Play blackjack with your dustbunnies. Join a game, hit, stand, double down, or split your hand.

### !fight
Alternative command: 
``` !battle !duel !flight ```
Command Syntax: 
``` !fight <@user> ```
Description: 
Challenge another user to a fight. The other user must accept with !accept.

### !accept
Command Syntax: 
``` !accept ```
Description: 
Accept a fight challenge. The fight is then simulated with classes, weapons, and abilities.

### !tts
Command Syntax: 
``` !tts <text> ```
Description: 
Uses OpenAI's TTS API to generate speech from the given text and sends it to the configured output.

### !translate
Command Syntax: 
``` !translate <text> ```
Description: 
Translates the given text between English and German using OpenAI. If the translation is not 1:1, a short explanation is added.

# Unified Message Object Documentation

The following JSON structure is designed to handle all types of messages in your Twitch admin panel:

```json
{
  "type": "string",
  "timestamp": "string",
  "source": "string",
  "content": "string",
  "metadata": {
    "channel": "string",
    "room_id": "string"
  },
  "author": {
    "name": "string",
    "display_name": "string",
    "mention": "string",
    "color": "string",
    "badges": {},
    "moderator": boolean,
    "subscriber": boolean,
    "vip": boolean,
    "broadcaster": boolean,
    "emotes": {}
  },
  "event_data": {}
}
