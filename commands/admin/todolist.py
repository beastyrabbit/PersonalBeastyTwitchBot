import json
import signal
import sys
import threading
import time
from datetime import datetime
import redis
import obsws_python as obs
import pyvban
##########################
# Initialize
##########################
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)
pubsub = redis_client.pubsub()
pubsub.subscribe('twitch.command.todo')
pubsub.subscribe('twitch.command.todolist')
pubsub.subscribe('twitch.command.tasks')
pubsub.subscribe('twitch.command.task')
pubsub.subscribe('twitch.command.list')

##########################
# Exit Function
##########################
def handle_exit(signum, frame):
    print("Unsubscribing from all channels bofore exiting")
    pubsub.unsubscribe()
    # Place any cleanup code here
    sys.exit(0)  # Exit gracefully

# Register SIGINT handler
signal.signal(signal.SIGINT, handle_exit)

def update_display_ids():
    """Recalculates and updates display IDs for all todos"""
    raw_todos = redis_client.lrange('todos', 0, -1)

    # Process into sorted groups
    groups = {}
    for todo_json in raw_todos:
        todo = json.loads(todo_json)
        group = todo.get('group', 'default')
        groups.setdefault(group, []).append(todo)

    # Sort groups and flatten
    sorted_groups = []
    if 'default' in groups:
        sorted_groups.append(('default', groups.pop('default')))
    sorted_groups += sorted(groups.items())

    # Generate new display IDs
    display_id = 0
    updated_todos = []
    for group_name, group_todos in sorted_groups:
        for todo in group_todos:
            display_id += 1
            todo['display_id'] = display_id
            updated_todos.append(json.dumps(todo))

    # Update Redis if changes needed
    if updated_todos:
        redis_client.delete('todos')
        redis_client.rpush('todos', *updated_todos)


##########################
# Helper Functions
##########################

def send_message_to_redis(send_message):
    redis_client.publish('twitch.chat.send', send_message)


##########################
# Main
##########################

#``` !todo add <group> <task> ```
#``` !todo add  <task> ```
#``` !todo remove <task id> ```
#``` !todo remove <group> ```
#``` !todo remove ``` (remove first element)
#``` !todo complete <task id> ```
#``` !todo complete <group> ```
#``` !todo clear  ``` (clear all)

for message in pubsub.listen():
    if message["type"] == "message":
        message_obj = json.loads(message['data'].decode('utf-8'))
        print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
        if not message_obj["author"]["broadcaster"]:
            send_message_to_redis('🚨 Only the broadcaster can use this command 🚨')
            continue
        # first we check what subcommand is being used
        message_content = message_obj.get('content').split()
        if message_content[1] == "add":
            if len(message_content) == 4:
                group = message_content[2]
                text = message_content[3]
            else:
                group = "default"
                text = message_content[2]

            redis_client.rpush('todos', json.dumps({'text': text, 'done': False, 'group': group}))
            update_display_ids()
            redis_client.publish('todo_updates', 'refresh')
            print(f"Added: {text}")
            continue
        if message_content[1] == "remove":
            if len(message_content) == 3:
                # we check if the third argument is a number or string
                if message_content[2].isdigit():
                    position = int(message_content[2])
                    for todo_json in redis_client.lrange('todos', 0, -1):
                        todo = json.loads(todo_json)
                        if todo["display_id"] == position:
                            redis_client.lrem('todos', 0, todo_json)
                            update_display_ids()
                            redis_client.publish('todo_updates', 'refresh')
                            print(f"Removed: {todo['text']}")
                            break
                    continue
                if message_content[2].isalpha():
                    group = message_content[2]
                    for todo_json in redis_client.lrange('todos', 0, -1):
                        todo = json.loads(todo_json)
                        if todo["group"] == group:
                            redis_client.lrem('todos', 0, todo_json)
                    update_display_ids()
                    redis_client.publish('todo_updates', 'refresh')
                    print(f"Removed group: {group}")
                    continue
            if len(message_content) == 2:
                todo = redis_client.lpop('todos')
                if todo:
                    update_display_ids()
                    redis_client.publish('todo_updates', 'refresh')
                    print(f"Removed: {json.loads(todo)['text']}")
                else:
                    print("No todos to remove!")
                continue
        if message_content[1] == "complete":
            if message_content[2].isdigit():
                position = int(message_content[2])
                for todo_json in redis_client.lrange('todos', 0, -1):
                    todo = json.loads(todo_json)
                    if todo["display_id"] == position:
                        todo['done'] = not todo['done']
                        redis_client.lset('todos', position - 1, json.dumps(todo))
                        update_display_ids()
                        redis_client.publish('todo_updates', 'refresh')
                        print(f"Toggled position {position}")
                        break
                continue
            if message_content[2].isalpha():
                group = message_content[2]
                for todo_json in redis_client.lrange('todos', 0, -1):
                    todo = json.loads(todo_json)
                    if todo["group"] == group:
                        todo['done'] = not todo['done']
                        redis_client.lset('todos', position - 1, json.dumps(todo))
                update_display_ids()
                redis_client.publish('todo_updates', 'refresh')
                print(f"Toggled group {group}")
                continue
        if message_content[1] == "clear":
            redis_client.delete('todos')
            update_display_ids()
            redis_client.publish('todo_updates', 'refresh')
            print("Cleared all todos")
            continue





















