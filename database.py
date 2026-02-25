import json
import os

DB_FILE = 'db/database.json'
TABLES = ['users', 'externals', 'flp', 'requests', 'attendance', 'leave_requests','chat']

def load_data():    
    try:
        with open(DB_FILE, 'r') as f:
            data = json.load(f)
            if data != {}:
                return data
    except:
        return {
            "users": [], 
            "externals": [], 
            "flp": [],
            "requests": [],
            "attendance": [],
            "leave_requests": [],
            "chat": []
        }

def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)