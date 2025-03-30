import argparse
import json
import redis

r = redis.Redis(host='192.168.50.115', port=6379, db=0)

def update_display_ids():
    """Recalculates and updates display IDs for all todos"""
    raw_todos = r.lrange('todos', 0, -1)

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
        r.delete('todos')
        r.rpush('todos', *updated_todos)


def add_todo(text,group):
    r.rpush('todos', json.dumps({'text': text, 'done': False, 'group': group}))
    update_display_ids()
    r.publish('todo_updates', 'refresh')
    print(f"Added: {text}")

def remove_first():
    todo = r.lpop('todos')
    if todo:
        update_display_ids()
        r.publish('todo_updates', 'refresh')
        print(f"Removed: {json.loads(todo)['text']}")
    else:
        print("No todos to remove!")

def remove_numb(position):
    index = position - 1
    todo = r.lindex('todos', index)
    if todo:
        r.lset('todos', index, r.lindex('todos', -1))
        update_display_ids()
        r.publish('todo_updates', 'refresh')
        print(f"Removed: {json.loads(todo)['text']}")
    else:
        print(f"No todo at position {position}")

def toggle_done(position):
    index = position - 1
    todo = json.loads(r.lindex('todos', index))
    if todo:
        todo['done'] = not todo['done']
        r.lset('todos', index, json.dumps(todo))
        update_display_ids()
        r.publish('todo_updates', 'refresh')
        print(f"Toggled position {position}")
    else:
        print(f"No todo at position {position}")

def list_todos():
    for idx, todo in enumerate(r.lrange('todos', 0, -1)):
        data = json.loads(todo)
        status = "✓" if data['done'] else " "
        print(f"{idx+1}. [{status}] {data['text']}")

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