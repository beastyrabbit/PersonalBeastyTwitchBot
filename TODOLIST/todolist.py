import json
import redis
from flask import Flask, render_template, Response

app = Flask(__name__)
redis_client = redis.Redis(host='192.168.50.115', port=6379, db=0)

def get_todos():
    groups = {}
    for todo_json in redis_client.lrange('todos', 0, -1):
        todo = json.loads(todo_json)
        group = todo.get('group', 'default')
        if group not in groups:
            groups[group] = []
        groups[group].append(todo)

    # Sort groups: default first, then alphabetical
    sorted_groups = []
    if 'default' in groups:
        sorted_groups.append(('default', groups.pop('default')))
    sorted_groups += sorted(groups.items())

    return sorted_groups
@app.route('/')
def index():
    todos = get_todos()
    print(todos)
    return render_template('index.html', todos=todos)

@app.route('/stream')
def stream():
    def event_stream():
        pubsub = redis_client.pubsub()
        pubsub.subscribe('todo_updates')
        for message in pubsub.listen():
            if message['type'] == 'message':
                yield f"data: {message['data'].decode()}\n\n"
                print(message['data'])
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)