import argparse
import json
import redis
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Redis connection with error handling
try:
    r = redis.Redis(host='192.168.50.115', port=6379, db=0)
    r.ping()  # Test connection
    logger.info("Connected to Redis successfully")
except redis.ConnectionError as e:
    logger.error(f"Failed to connect to Redis: {e}")
    print(f"Error: Could not connect to Redis server: {e}")
    r = None

def update_display_ids():
    """Recalculates and updates display IDs for all todos"""
    try:
        if r is None:
            logger.error("Redis client is not available")
            print("Error: Redis connection is not available")
            return False

        try:
            raw_todos = r.lrange('todos', 0, -1)
        except redis.RedisError as e:
            logger.error(f"Failed to retrieve todos from Redis: {e}")
            print(f"Error: Failed to retrieve todos: {e}")
            return False

        # Process into sorted groups
        groups = {}
        for todo_json in raw_todos:
            try:
                todo = json.loads(todo_json)
                group = todo.get('group', 'default')
                groups.setdefault(group, []).append(todo)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse todo JSON: {e}, data: {todo_json}")
                continue  # Skip invalid JSON entries

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
                try:
                    updated_todos.append(json.dumps(todo))
                except Exception as e:
                    logger.error(f"Failed to serialize todo to JSON: {e}, data: {todo}")
                    continue

        # Update Redis if changes needed
        if updated_todos:
            try:
                r.delete('todos')
                r.rpush('todos', *updated_todos)
                logger.info(f"Updated {len(updated_todos)} todos with new display IDs")
                return True
            except redis.RedisError as e:
                logger.error(f"Failed to update todos in Redis: {e}")
                print(f"Error: Failed to update todos: {e}")
                return False
        return True
    except Exception as e:
        logger.error(f"Unexpected error in update_display_ids: {e}")
        print(f"Error: An unexpected error occurred: {e}")
        return False


def add_todo(text, group):
    """Add a new todo item to the list"""
    try:
        if r is None:
            logger.error("Redis client is not available")
            print("Error: Redis connection is not available")
            return False

        try:
            todo_data = {'text': text, 'done': False, 'group': group}
            todo_json = json.dumps(todo_data)
            r.rpush('todos', todo_json)
            logger.info(f"Added todo: {text} in group: {group}")

            if update_display_ids():
                try:
                    r.publish('todo_updates', 'refresh')
                    print(f"Added: {text}")
                    return True
                except redis.RedisError as e:
                    logger.error(f"Failed to publish update: {e}")
                    print(f"Warning: Todo added but notification failed: {e}")
                    return True
            return False
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to add todo: {e}")
            print(f"Error: Failed to add todo: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in add_todo: {e}")
        print(f"Error: An unexpected error occurred: {e}")
        return False

def remove_first():
    """Remove the first todo item from the list"""
    try:
        if r is None:
            logger.error("Redis client is not available")
            print("Error: Redis connection is not available")
            return False

        try:
            todo = r.lpop('todos')
            if todo:
                try:
                    todo_text = json.loads(todo)['text']
                    logger.info(f"Removed first todo: {todo_text}")

                    if update_display_ids():
                        try:
                            r.publish('todo_updates', 'refresh')
                            print(f"Removed: {todo_text}")
                            return True
                        except redis.RedisError as e:
                            logger.error(f"Failed to publish update: {e}")
                            print(f"Warning: Todo removed but notification failed: {e}")
                            return True
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse removed todo: {e}")
                    print("Removed an item but couldn't parse its content")
                    update_display_ids()
                    r.publish('todo_updates', 'refresh')
                    return True
            else:
                logger.info("No todos to remove")
                print("No todos to remove!")
                return False
        except redis.RedisError as e:
            logger.error(f"Failed to remove todo: {e}")
            print(f"Error: Failed to remove todo: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in remove_first: {e}")
        print(f"Error: An unexpected error occurred: {e}")
        return False

def remove_numb(position):
    """Remove a todo item by its position"""
    try:
        if r is None:
            logger.error("Redis client is not available")
            print("Error: Redis connection is not available")
            return False

        if position < 1:
            logger.error(f"Invalid position: {position}")
            print(f"Error: Position must be a positive number")
            return False

        try:
            # Get the todo at the specified position
            index = position - 1
            todo = r.lindex('todos', index)

            if todo:
                try:
                    todo_text = json.loads(todo)['text']
                    logger.info(f"Removing todo at position {position}: {todo_text}")

                    # Remove the item at the specified position
                    r.lrem('todos', 1, todo)

                    if update_display_ids():
                        try:
                            r.publish('todo_updates', 'refresh')
                            print(f"Removed: {todo_text}")
                            return True
                        except redis.RedisError as e:
                            logger.error(f"Failed to publish update: {e}")
                            print(f"Warning: Todo removed but notification failed: {e}")
                            return True
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse removed todo: {e}")
                    print("Removed an item but couldn't parse its content")
                    update_display_ids()
                    r.publish('todo_updates', 'refresh')
                    return True
            else:
                logger.info(f"No todo at position {position}")
                print(f"No todo at position {position}")
                return False
        except redis.RedisError as e:
            logger.error(f"Failed to remove todo: {e}")
            print(f"Error: Failed to remove todo: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in remove_numb: {e}")
        print(f"Error: An unexpected error occurred: {e}")
        return False

def toggle_done(position):
    """Toggle the done status of a todo item"""
    try:
        if r is None:
            logger.error("Redis client is not available")
            print("Error: Redis connection is not available")
            return False

        if position < 1:
            logger.error(f"Invalid position: {position}")
            print(f"Error: Position must be a positive number")
            return False

        try:
            # Get the todo at the specified position
            index = position - 1
            todo_json = r.lindex('todos', index)

            if todo_json:
                try:
                    todo = json.loads(todo_json)
                    todo['done'] = not todo['done']
                    status = "completed" if todo['done'] else "uncompleted"

                    try:
                        r.lset('todos', index, json.dumps(todo))
                        logger.info(f"Toggled todo at position {position} to {status}")

                        if update_display_ids():
                            try:
                                r.publish('todo_updates', 'refresh')
                                print(f"Toggled position {position} to {status}")
                                return True
                            except redis.RedisError as e:
                                logger.error(f"Failed to publish update: {e}")
                                print(f"Warning: Todo updated but notification failed: {e}")
                                return True
                    except redis.RedisError as e:
                        logger.error(f"Failed to update todo: {e}")
                        print(f"Error: Failed to update todo: {e}")
                        return False
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse todo: {e}")
                    print(f"Error: Failed to parse todo at position {position}")
                    return False
            else:
                logger.info(f"No todo at position {position}")
                print(f"No todo at position {position}")
                return False
        except redis.RedisError as e:
            logger.error(f"Failed to retrieve todo: {e}")
            print(f"Error: Failed to retrieve todo: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in toggle_done: {e}")
        print(f"Error: An unexpected error occurred: {e}")
        return False

def list_todos():
    """List all todo items"""
    try:
        if r is None:
            logger.error("Redis client is not available")
            print("Error: Redis connection is not available")
            return False

        try:
            todos = r.lrange('todos', 0, -1)
            if not todos:
                print("No todos found")
                return True

            for idx, todo_json in enumerate(todos):
                try:
                    data = json.loads(todo_json)
                    status = "✓" if data.get('done', False) else " "
                    group = f" [{data.get('group', 'default')}]" if data.get('group') != 'default' else ""
                    print(f"{idx+1}. [{status}]{group} {data.get('text', 'No text')}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse todo: {e}, data: {todo_json}")
                    print(f"{idx+1}. [?] <corrupted data>")
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to retrieve todos: {e}")
            print(f"Error: Failed to retrieve todos: {e}")
            return False
    except Exception as e:
        logger.error(f"Unexpected error in list_todos: {e}")
        print(f"Error: An unexpected error occurred: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Beasty Todo Manager")
    subparsers = parser.add_subparsers(dest='command')

    add_parser = subparsers.add_parser('add')
    add_parser.add_argument('text', help='Todo text')
    add_parser.add_argument('group', help='group')

    remove_parser = subparsers.add_parser('remove')
    remove_parser.add_argument('position', type=int)

    subparsers.add_parser('remove_first')


    toggle_parser = subparsers.add_parser('toggle')
    toggle_parser.add_argument('position', type=int)

    subparsers.add_parser('list')

    args = parser.parse_args()

    if args.command == 'add':
        add_todo(args.text, args.group)
    elif args.command == 'remove':
        remove_numb(args.position)
    elif args.command == 'remove_first':
        remove_first()
    elif args.command == 'toggle':
        toggle_done(args.position)
    elif args.command == 'list':
        list_todos()
    else:
        parser.print_help()
