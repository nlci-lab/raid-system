import json
import os

DB_FILE = 'db/database.json'
TABLES = ['users', 'externals', 'flp', 'requests', 'attendance', 'leave_requests','chat']

def load_data():
    try:
        with open(DB_FILE, 'r') as f:
            data = json.load(f)

        if data == {}:
            data = {
                "users": [],
                "externals": [],
                "flp": [],
                "requests": [],
                "attendance": [],
                "leave_requests": [],
                "chat": []
            }
            save_data(data)

        return data

    except:
        data = {
            "users": [],
            "externals": [],
            "flp": [],
            "requests": [],
            "attendance": [],
            "leave_requests": [],
            "chat": []
        }
        save_data(data)
        return data

def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)