import redis
import json
import sys
from datetime import datetime

REDIS_HOST = '192.168.50.115'
REDIS_PORT = 6379
REDIS_DB = 0

def default_user_json(username):
    # Create a new user JSON with log sub-object for all counters
    return {
        'name': username,
        'display_name': username,
        'log': {
            'chat': 0,
            'command': 0,
            'admin': 0,
            'lurk': 0,
            'unlurk': 0
        },
        'dustbunnies': {},
        'banking': {}
    }

def update_user_subobject(user_json, subkey, old_data, exclude_keys=None):
    # Only copy fields specific to the sub-object
    if exclude_keys is None:
        exclude_keys = ('name', 'display_name')
    user_json[subkey] = {k: v for k, v in old_data.items() if k not in exclude_keys}

def migrate_to_unified_user_json(test=False, show_final_json=False, log_file_path='migration_log.jsonl'):
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    migrated_users = set()
    keys_dustbunnies = r.keys('dustbunnies:*')
    keys_banking = r.keys('banking:*')
    keys_global = r.keys('global:*')
    legacy_keys_to_delete = []
    log_entries = []

    def log_action(action, key, username, old_data, new_data=None):
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'action': action,
            'key': key.decode('utf-8') if isinstance(key, bytes) else key,
            'username': username,
            'old_data': old_data,
            'new_data': new_data
        }
        log_entries.append(entry)

    # Migrate dustbunnies
    for key in keys_dustbunnies:
        username = key.decode('utf-8').split(':', 1)[1]
        user_key = f'user:{username}'
        try:
            old = json.loads(r.get(key))
        except Exception as e:
            print(f"[ERROR] Could not decode {key}: {e}")
            continue
        user_json = json.loads(r.get(user_key)) if r.exists(user_key) else default_user_json(username)
        # Migrate counters to log sub-object
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            if k in user_json and not isinstance(user_json[k], dict):
                user_json.setdefault('log', {})[k] = user_json[k]
                del user_json[k]
        user_json.setdefault('log', {})
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            user_json['log'].setdefault(k, 0)
        update_user_subobject(user_json, 'dustbunnies', old)
        if test or show_final_json:
            print(f"[TEST] Final user JSON for {username}:\n{json.dumps(user_json, indent=2)}\n")
        if not test:
            r.set(user_key, json.dumps(user_json))
        migrated_users.add(username)
        legacy_keys_to_delete.append(key)
        log_action('migrate_dustbunnies', key, username, old, user_json)

    # Migrate banking
    for key in keys_banking:
        username = key.decode('utf-8').split(':', 1)[1]
        user_key = f'user:{username}'
        try:
            old = json.loads(r.get(key))
        except Exception as e:
            print(f"[ERROR] Could not decode {key}: {e}")
            continue
        user_json = json.loads(r.get(user_key)) if r.exists(user_key) else default_user_json(username)
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            if k in user_json and not isinstance(user_json[k], dict):
                user_json.setdefault('log', {})[k] = user_json[k]
                del user_json[k]
        user_json.setdefault('log', {})
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            user_json['log'].setdefault(k, 0)
        update_user_subobject(user_json, 'banking', old)
        if test or show_final_json:
            print(f"[TEST] Final user JSON for {username}:\n{json.dumps(user_json, indent=2)}\n")
        if not test:
            r.set(user_key, json.dumps(user_json))
        migrated_users.add(username)
        legacy_keys_to_delete.append(key)
        log_action('migrate_banking', key, username, old, user_json)

    # Migrate lurk/unlurk (global:{username})
    for key in keys_global:
        username = key.decode('utf-8').split(':', 1)[1]
        user_key = f'user:{username}'
        try:
            old = json.loads(r.get(key))
        except Exception as e:
            print(f"[ERROR] Could not decode {key}: {e}")
            continue
        user_json = json.loads(r.get(user_key)) if r.exists(user_key) else default_user_json(username)
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            if k in user_json and not isinstance(user_json[k], dict):
                user_json.setdefault('log', {})[k] = user_json[k]
                del user_json[k]
        user_json.setdefault('log', {})
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            user_json['log'].setdefault(k, 0)
        changed = False
        if isinstance(old, int):
            user_json['log']['lurk'] = old
            changed = True
        elif isinstance(old, dict):
            if 'lurk' in old:
                user_json['log']['lurk'] = old['lurk']
                changed = True
            if 'unlurk' in old:
                user_json['log']['unlurk'] = old['unlurk']
                changed = True
        if changed:
            if test or show_final_json:
                print(f"[TEST] Final user JSON for {username}:\n{json.dumps(user_json, indent=2)}\n")
            if not test:
                r.set(user_key, json.dumps(user_json))
            migrated_users.add(username)
            legacy_keys_to_delete.append(key)
            log_action('migrate_global', key, username, old, user_json)

    # Write log file
    if log_entries and not test:
        with open(log_file_path, 'w', encoding='utf-8') as f:
            for entry in log_entries:
                f.write(json.dumps(entry) + '\n')
        print(f"Migration log written to {log_file_path}")

    print(f"Migrated users: {sorted(migrated_users)}")
    print(f"Total migrated: {len(migrated_users)}")
    if test:
        print("[TEST MODE] No changes were written to Redis.")
        return
    print("Migration complete.\n")
    if legacy_keys_to_delete:
        answer = input(f"Do you want to delete {len(legacy_keys_to_delete)} legacy keys? (y/n): ").strip().lower()
        if answer == 'y':
            for key in legacy_keys_to_delete:
                r.delete(key)
            print("Legacy keys have been deleted.")
        else:
            print("Legacy keys were NOT deleted.")

def list_unknown_keys():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    all_keys = r.keys('*')
    known_prefixes = (b'user:', b'dustbunnies:', b'banking:', b'global:')
    unknown = [k.decode('utf-8') for k in all_keys if not k.startswith(known_prefixes)]
    if unknown:
        print("Unknown/legacy keys in Redis:")
        for k in unknown:
            print(f"  {k}")
    else:
        print("No unknown keys found. All keys match known patterns.")

if __name__ == '__main__':
    test_mode = '--test' in sys.argv
    show_final_json = '--show-json' in sys.argv or test_mode
    if '--list-unknown' in sys.argv:
        list_unknown_keys()
    else:
        migrate_to_unified_user_json(test=test_mode, show_final_json=show_final_json)
