# Redis PubSub Documentation

This document describes how Redis PubSub is used in the TwitchBotV2 project, following an OpenAPI-like structure.

## Overview

The TwitchBotV2 project uses Redis PubSub for real-time communication between different components of the system. Redis is configured with the following parameters:

- **Host**: 192.168.50.115
- **Port**: 6379
- **Databases**:
  - DB 0: Main database for most operations and PubSub
  - DB 1: Environment-specific data

## Channels

### Twitch Chat Channels

#### `twitch.chat.send`

Used to send messages to Twitch chat.

- **Publisher Components**: Various commands, utilities
- **Subscriber Components**: Chat interface
- **Message Format**: String (the message to be sent to chat)
- **Example**:
  ```
  "Hello, welcome to the stream!"
  ```

#### `twitch.chat.announcement`

Used to send announcement messages to Twitch chat.

- **Publisher Components**: Admin commands
- **Subscriber Components**: Chat interface
- **Message Format**: String (the announcement message)
- **Example**:
  ```
  "Stream starting in 5 minutes!"
  ```

#### `twitch.chat.shoutout`

Used to send shoutout messages to Twitch chat.

- **Publisher Components**: Shoutout command
- **Subscriber Components**: Chat interface
- **Message Format**: String (the shoutout message)
- **Example**:
  ```
  "Go check out @username who was last streaming Category!"
  ```

#### `twitch.chat.received`

Used to process messages received from Twitch chat.

- **Publisher Components**: Chat interface
- **Subscriber Components**: Chat logger
- **Message Format**: JSON object (details of the received message)
- **Example**:
  ```json
  {
    "content": "Hello everyone!",
    "author": {
      "name": "username",
      "display_name": "Username",
      "mention": "@Username"
    },
    "timestamp": "2023-06-01T12:34:56Z"
  }
  ```

#### `beastyrabbit.chat.send`

Used to send messages to Twitch chat from the BeastyRabbit helper.

- **Publisher Components**: BeastyRabbit helper
- **Subscriber Components**: Chat interface
- **Message Format**: String (the message to be sent to chat)
- **Redis Database**: DB 0 (specifically uses DB 0)
- **Example**:
  ```
  "Hello from BeastyRabbit!"
  ```

### Command Channels

#### `twitch.command.[command_name]`

Used to trigger commands from Twitch chat. Multiple channels exist for different commands and their aliases.

- **Publisher Components**: Command parser
- **Subscriber Components**: Command handlers
- **Message Format**: JSON object
- **Example**:
  ```json
  {
    "Command": "lurk",
    "content": "!lurk see you later",
    "author": {
      "name": "username",
      "display_name": "Username",
      "mention": "@Username"
    },
    "timestamp": "2023-06-01T12:34:56Z"
  }
  ```

Common command channels include:
- `twitch.command.lurk`, `twitch.command.hide`, `twitch.command.away`, `twitch.command.offline`
- `twitch.command.unlurk`, `twitch.command.back`, `twitch.command.online`, `twitch.command.show`
- `twitch.command.points`, `twitch.command.stats`, `twitch.command.dustbunnies`, `twitch.command.balance`
- `twitch.command.gamble`, `twitch.command.bet`, `twitch.command.gambling`
- `twitch.command.blackjack`, `twitch.command.bj`
- `twitch.command.slots`, `twitch.command.slot`
- `twitch.command.invest`, `twitch.command.investment`, `twitch.command.banking`
- `twitch.command.collect`, `twitch.command.interest`
- `twitch.command.give`, `twitch.command.donate`, `twitch.command.gift`, `twitch.command.share`
- `twitch.command.steal`, `twitch.command.rob`
- `twitch.command.roomba`, `twitch.command.clean`, `twitch.command.vacuum`
- `twitch.command.fight`, `twitch.command.battle`, `twitch.command.duel`
- `twitch.command.accept`
- `twitch.command.todo`, `twitch.command.todolist`, `twitch.command.tasks`, `twitch.command.task`, `twitch.command.list`
- `twitch.command.shoutout`, `twitch.command.so`, `twitch.command.host`
- `twitch.command.brb`, `twitch.command.pause`, `twitch.command.break`
- `twitch.command.unbrb`
- `twitch.command.discord`
- `twitch.command.timer`, `twitch.command.countdown`, `twitch.command.clock`
- `twitch.command.timezone`, `twitch.command.time`
- `twitch.command.translate`, `twitch.command.tr`
- `twitch.command.tts`
- `twitch.command.hug`, `twitch.command.cuddle`, `twitch.command.snuggle`
- `twitch.command.gameoflife`, `twitch.command.gol`, `twitch.command.gl`
- `twitch.command.system`, `twitch.command.sys`
- `twitch.command.suika`

### System Channels

#### `system.[command].send`

Used to send system-specific messages.

- **Publisher Components**: Various commands, utilities
- **Subscriber Components**: System interface
- **Message Format**: JSON object
- **Example**:
  ```json
  {
    "type": "system",
    "source": "system",
    "content": "Command is ready to be used"
  }
  ```

#### `admin.[command].send` (Deprecated)

Legacy channel for backward compatibility. Use `system.[command].send` instead.

- **Publisher Components**: Various commands, utilities
- **Subscriber Components**: Admin interface
- **Message Format**: JSON object
- **Example**:
  ```json
  {
    "type": "admin",
    "source": "system",
    "content": "Command is ready to be used"
  }
  ```

### Internal Channels

#### `internal.command.[command_name]`

Used for internal communication between components.

- **Publisher Components**: Various commands
- **Subscriber Components**: Command handlers
- **Message Format**: JSON object (varies by command)
- **Example**:
  ```json
  {
    "username": "streamername",
    "game": "Just Chatting"
  }
  ```

Known internal channels:
- `internal.command.get_shoutout`
- `internal.command.post_shoutout`
- `twitch.chat.shoutout.request`
- `twitch.chat.shoutout.response`

#### `twitch.chat.shoutout.request`

Used to request information about a user for a shoutout.

- **Publisher Components**: Shoutout command
- **Subscriber Components**: Shoutout handler
- **Message Format**: JSON object (details of the user to get information about)
- **Example**:
  ```json
  {
    "username": "username",
    "id": "request-123"
  }
  ```

#### `twitch.chat.shoutout.response`

Used to respond with information about a user for a shoutout.

- **Publisher Components**: Shoutout handler
- **Subscriber Components**: Shoutout command
- **Message Format**: JSON object (details of the user)
- **Example**:
  ```json
  {
    "username": "username",
    "display_name": "Username",
    "game": "Just Chatting",
    "title": "Hanging out with chat",
    "id": "request-123"
  }
  ```

### Feature-specific Channels

#### `todo_updates`

Used to notify about updates to the todo list.

- **Publisher Components**: Todo list command
- **Subscriber Components**: Todo list UI
- **Message Format**: String ("refresh")
- **Example**:
  ```
  "refresh"
  ```

## Data Structures

### User Data

User data is stored in Redis with keys following the pattern `user:{username}`.

- **Format**: JSON object
- **Example**:
  ```json
  {
    "name": "username",
    "display_name": "Username",
    "log": {
      "chat": 10,
      "command": 5,
      "admin": 0,
      "system": 3,
      "lurk": 2,
      "unlurk": 1
    },
    "dustbunnies": {},
    "banking": {}
  }
  ```

## Usage Examples

### Sending a Chat Message

To send a message to Twitch chat, publish to the `twitch.chat.send` channel with the message as the payload.

### Sending a System Message

To send a system message, publish to the `system.[command].send` channel with a JSON object containing type, source, and content.

### Sending an Admin Message (Deprecated)

Legacy method for backward compatibility. Use "Sending a System Message" instead.

To send an admin message, publish to the `admin.[command].send` channel with a JSON object containing type, source, and content.

### Subscribing to Commands

To handle commands, subscribe to the relevant command channels (e.g., `twitch.command.example`) and process the JSON messages received.

## Error Handling

When a Redis operation fails, most components will log the error and continue operation if possible. Critical components may exit gracefully by ensuring all Redis subscriptions are properly closed before terminating.
