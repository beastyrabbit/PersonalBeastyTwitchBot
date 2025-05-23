import json
import signal
import sys

import redis

from module.message_utils import send_admin_message_to_redis, send_message_to_redis

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

send_admin_message_to_redis("Todolist command is ready to be used", "todolist")

for message in pubsub.listen():
    if message["type"] == "message":
        try:
            # Parse the message
            try:
                message_obj = json.loads(message['data'].decode('utf-8'))
                print(f"Chat Command: {message_obj.get('command')} and Message: {message_obj.get('content')}")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                print(f"Error parsing message: {e}")
                continue

            # Check if the user is the broadcaster
            if not message_obj["author"]["broadcaster"]:
                send_message_to_redis('🚨 Only the broadcaster can use this command 🚨', command="todolist")
                continue

            # Get the message content
            message_content = message_obj.get('content', '').split()

            # Check if there are enough arguments
            if len(message_content) < 2:
                send_message_to_redis('❌ Invalid command format. Use !todo <add|remove|complete|clear> [args]', command="todolist")
                continue

            # first we check what subcommand is being used
        except Exception as e:
            print(f"Error processing message: {e}")
            continue

        # Process the command
        if message_content[1] == "add":
            try:
                # Validate arguments
                if len(message_content) < 3:
                    send_message_to_redis('❌ Invalid add command. Use !todo add [group] <task>', command="todolist")
                    continue

                # Parse arguments
                if len(message_content) >= 4:
                    group = message_content[2]
                    text = ' '.join(message_content[3:])  # Allow multi-word tasks
                else:
                    group = "default"
                    text = ' '.join(message_content[2:])  # Allow multi-word tasks

                # Validate text and group
                if not text.strip():
                    send_message_to_redis('❌ Task text cannot be empty', command="todolist")
                    continue

                # Add the todo
                try:
                    redis_client.rpush('todos', json.dumps({'text': text, 'done': False, 'group': group}))
                    update_display_ids()
                    redis_client.publish('todo_updates', 'refresh')
                    send_message_to_redis(f'✅ Added task: "{text}" to group: {group}', command="todolist")
                    print(f"Added: {text} to group: {group}")
                except Exception as e:
                    send_message_to_redis(f'❌ Failed to add task: {e}', command="todolist")
                    print(f"Error adding task: {e}")
            except Exception as e:
                send_message_to_redis(f'❌ Error processing add command: {e}', command="todolist")
                print(f"Error in add command: {e}")
            continue
        if message_content[1] == "remove":
            try:
                # Check arguments
                if len(message_content) == 3:
                    # Case 1: Remove by position (display_id)
                    if message_content[2].isdigit():
                        try:
                            position = int(message_content[2])
                            if position < 1:
                                send_message_to_redis('❌ Position must be a positive number', command="todolist")
                                continue

                            found = False
                            for todo_json in redis_client.lrange('todos', 0, -1):
                                try:
                                    todo = json.loads(todo_json)
                                    if todo.get("display_id") == position:
                                        redis_client.lrem('todos', 0, todo_json)
                                        update_display_ids()
                                        redis_client.publish('todo_updates', 'refresh')
                                        send_message_to_redis(f'✅ Removed task: "{todo["text"]}"', command="todolist")
                                        print(f"Removed: {todo['text']}")
                                        found = True
                                        break
                                except json.JSONDecodeError as e:
                                    print(f"Error parsing todo: {e}")
                                    continue

                            if not found:
                                send_message_to_redis(f'❌ No task found with ID {position}', command="todolist")
                                print(f"No task found with ID {position}")
                        except Exception as e:
                            send_message_to_redis(f'❌ Error removing task: {e}', command="todolist")
                            print(f"Error removing task: {e}")

                    # Case 2: Remove by group
                    elif message_content[2].isalpha():
                        try:
                            group = message_content[2]
                            removed_count = 0

                            for todo_json in redis_client.lrange('todos', 0, -1):
                                try:
                                    todo = json.loads(todo_json)
                                    if todo.get("group") == group:
                                        redis_client.lrem('todos', 0, todo_json)
                                        removed_count += 1
                                except json.JSONDecodeError as e:
                                    print(f"Error parsing todo: {e}")
                                    continue

                            if removed_count > 0:
                                update_display_ids()
                                redis_client.publish('todo_updates', 'refresh')
                                send_message_to_redis(f'✅ Removed {removed_count} tasks from group: {group}', command="todolist")
                                print(f"Removed {removed_count} tasks from group: {group}")
                            else:
                                send_message_to_redis(f'❌ No tasks found in group: {group}', command="todolist")
                                print(f"No tasks found in group: {group}")
                        except Exception as e:
                            send_message_to_redis(f'❌ Error removing group: {e}', command="todolist")
                            print(f"Error removing group: {e}")

                    # Case 3: Invalid argument
                    else:
                        send_message_to_redis('❌ Invalid argument. Use a number for task ID or a word for group name', command="todolist")

                # Case 4: Remove first task
                elif len(message_content) == 2:
                    try:
                        todo = redis_client.lpop('todos')
                        if todo:
                            try:
                                todo_data = json.loads(todo)
                                update_display_ids()
                                redis_client.publish('todo_updates', 'refresh')
                                send_message_to_redis(f'✅ Removed first task: "{todo_data["text"]}"', command="todolist")
                                print(f"Removed: {todo_data['text']}")
                            except json.JSONDecodeError as e:
                                print(f"Error parsing removed todo: {e}")
                                update_display_ids()
                                redis_client.publish('todo_updates', 'refresh')
                                send_message_to_redis('✅ Removed first task (corrupted data)', command="todolist")
                        else:
                            send_message_to_redis('❌ No tasks to remove', command="todolist")
                            print("No todos to remove!")
                    except Exception as e:
                        send_message_to_redis(f'❌ Error removing first task: {e}', command="todolist")
                        print(f"Error removing first task: {e}")

                # Case 5: Too many arguments
                else:
                    send_message_to_redis('❌ Too many arguments. Use !todo remove [id|group]', command="todolist")
            except Exception as e:
                send_message_to_redis(f'❌ Error processing remove command: {e}', command="todolist")
                print(f"Error in remove command: {e}")
            continue
        if message_content[1] == "complete":
            try:
                # Check if we have enough arguments
                if len(message_content) < 3:
                    send_message_to_redis('❌ Invalid complete command. Use !todo complete <id|group>', command="todolist")
                    continue

                # Case 1: Complete by position (display_id)
                if message_content[2].isdigit():
                    try:
                        position = int(message_content[2])
                        if position < 1:
                            send_message_to_redis('❌ Position must be a positive number', command="todolist")
                            continue

                        found = False
                        for todo_json in redis_client.lrange('todos', 0, -1):
                            try:
                                todo = json.loads(todo_json)
                                if todo.get("display_id") == position:
                                    # Toggle the done status
                                    todo['done'] = not todo['done']
                                    status = "completed" if todo['done'] else "uncompleted"

                                    # Find the index of this todo in the list
                                    todos = redis_client.lrange('todos', 0, -1)
                                    for i, t in enumerate(todos):
                                        if t == todo_json:
                                            redis_client.lset('todos', i, json.dumps(todo))
                                            break

                                    update_display_ids()
                                    redis_client.publish('todo_updates', 'refresh')
                                    send_message_to_redis(f'✅ Marked task "{todo["text"]}" as {status}', command="todolist")
                                    print(f"Toggled position {position} to {status}")
                                    found = True
                                    break
                            except json.JSONDecodeError as e:
                                print(f"Error parsing todo: {e}")
                                continue

                        if not found:
                            send_message_to_redis(f'❌ No task found with ID {position}', command="todolist")
                            print(f"No task found with ID {position}")
                    except Exception as e:
                        send_message_to_redis(f'❌ Error completing task: {e}', command="todolist")
                        print(f"Error completing task: {e}")

                # Case 2: Complete by group
                elif message_content[2].isalpha():
                    try:
                        group = message_content[2]
                        completed_count = 0
                        todos = redis_client.lrange('todos', 0, -1)

                        # First pass: check if any todos exist in this group
                        group_exists = False
                        for todo_json in todos:
                            try:
                                todo = json.loads(todo_json)
                                if todo.get("group") == group:
                                    group_exists = True
                                    break
                            except json.JSONDecodeError:
                                continue

                        if not group_exists:
                            send_message_to_redis(f'❌ No tasks found in group: {group}', command="todolist")
                            print(f"No tasks found in group: {group}")
                            continue

                        # Second pass: toggle all todos in this group
                        for i, todo_json in enumerate(todos):
                            try:
                                todo = json.loads(todo_json)
                                if todo.get("group") == group:
                                    # Toggle the done status
                                    todo['done'] = not todo['done']
                                    redis_client.lset('todos', i, json.dumps(todo))
                                    completed_count += 1
                            except (json.JSONDecodeError, redis.RedisError) as e:
                                print(f"Error updating todo in group {group}: {e}")
                                continue

                        if completed_count > 0:
                            update_display_ids()
                            redis_client.publish('todo_updates', 'refresh')
                            send_message_to_redis(f'✅ Toggled {completed_count} tasks in group: {group}', command="todolist")
                            print(f"Toggled {completed_count} tasks in group: {group}")
                    except Exception as e:
                        send_message_to_redis(f'❌ Error completing group: {e}', command="todolist")
                        print(f"Error completing group: {e}")

                # Case 3: Invalid argument
                else:
                    send_message_to_redis('❌ Invalid argument. Use a number for task ID or a word for group name', command="todolist")
            except Exception as e:
                send_message_to_redis(f'❌ Error processing complete command: {e}', command="todolist")
                print(f"Error in complete command: {e}")
            continue
        if message_content[1] == "clear":
            try:
                # Check if there are any todos to clear
                todos_count = redis_client.llen('todos')

                if todos_count > 0:
                    # Ask for confirmation if there are many todos
                    if len(message_content) > 2 and message_content[2].lower() == "confirm":
                        try:
                            redis_client.delete('todos')
                            redis_client.publish('todo_updates', 'refresh')
                            send_message_to_redis(f'✅ Cleared all {todos_count} tasks', command="todolist")
                            print(f"Cleared all {todos_count} todos")
                        except redis.RedisError as e:
                            send_message_to_redis(f'❌ Error clearing tasks: {e}', command="todolist")
                            print(f"Error clearing todos: {e}")
                    else:
                        # If there are more than 5 todos, ask for confirmation
                        if todos_count > 5:
                            send_message_to_redis(f'⚠️ You are about to delete {todos_count} tasks. Use "!todo clear confirm" to proceed', command="todolist")
                            print(f"Confirmation required to clear {todos_count} todos")
                        else:
                            try:
                                redis_client.delete('todos')
                                redis_client.publish('todo_updates', 'refresh')
                                send_message_to_redis(f'✅ Cleared all {todos_count} tasks', command="todolist")
                                print(f"Cleared all {todos_count} todos")
                            except redis.RedisError as e:
                                send_message_to_redis(f'❌ Error clearing tasks: {e}', command="todolist")
                                print(f"Error clearing todos: {e}")
                else:
                    send_message_to_redis('ℹ️ No tasks to clear', command="todolist")
                    print("No todos to clear")
            except Exception as e:
                send_message_to_redis(f'❌ Error processing clear command: {e}', command="todolist")
                print(f"Error in clear command: {e}")
            continue
