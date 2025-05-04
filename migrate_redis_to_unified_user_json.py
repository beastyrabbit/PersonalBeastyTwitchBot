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


def migrate_to_unified_user_json(test=False, show_final_json=False):
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    migrated_users = set()
    keys_dustbunnies = r.keys('dustbunnies:*')
    keys_banking = r.keys('banking:*')
    keys_global = r.keys('global:*')

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
        # If old user_json has top-level counters, move them to log
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            if k in user_json and not isinstance(user_json[k], dict):
                user_json.setdefault('log', {})[k] = user_json[k]
                del user_json[k]
        # Ensure all log keys exist
        user_json.setdefault('log', {})
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            user_json['log'].setdefault(k, 0)
        update_user_subobject(user_json, 'dustbunnies', old)
        if test or show_final_json:
            print(f"[TEST] Final user JSON for {username}:\n{json.dumps(user_json, indent=2)}\n")
        if not test:
            r.set(user_key, json.dumps(user_json))
        migrated_users.add(username)
        # r.delete(key)  # Uncomment to remove old key after verifying migration

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
        # Migrate counters to log sub-object
        # If old user_json has top-level counters, move them to log
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            if k in user_json and not isinstance(user_json[k], dict):
                user_json.setdefault('log', {})[k] = user_json[k]
                del user_json[k]
        # Ensure all log keys exist
        user_json.setdefault('log', {})
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            user_json['log'].setdefault(k, 0)
        update_user_subobject(user_json, 'banking', old)
        if test or show_final_json:
            print(f"[TEST] Final user JSON for {username}:\n{json.dumps(user_json, indent=2)}\n")
        if not test:
            r.set(user_key, json.dumps(user_json))
        migrated_users.add(username)
        # r.delete(key)  # Uncomment to remove old key after verifying migration

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
        # Migrate counters to log sub-object
        # If old user_json has top-level counters, move them to log
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            if k in user_json and not isinstance(user_json[k], dict):
                user_json.setdefault('log', {})[k] = user_json[k]
                del user_json[k]
        # Ensure all log keys exist
        user_json.setdefault('log', {})
        for k in ['chat', 'command', 'admin', 'lurk', 'unlurk']:
            user_json['log'].setdefault(k, 0)
        changed = False
        # Handle both int and dict types for legacy values
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
        # r.delete(key)  # Uncomment to remove old key after verifying migration

    print(f"Migrated users: {sorted(migrated_users)}")
    print(f"Total migrated: {len(migrated_users)}")
    if test:
        print("[TEST MODE] No changes were written to Redis.")
    else:
        print("Migration complete. You may now remove legacy keys if you have verified the new structure.")

if __name__ == '__main__':
    test_mode = '--test' in sys.argv
    show_final_json = '--show-json' in sys.argv or test_mode  # Always show final JSON in test mode
    migrate_to_unified_user_json(test=test_mode, show_final_json=show_final_json)
