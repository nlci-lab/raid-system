import json
import os

<<<<<<< Updated upstream
DB_FILE = 'db/database.json'
=======
<<<<<<< HEAD
DB_DIR = 'db'
TABLES = ['users', 'externals', 'flp', 'requests', 'attendance', 'leave_requests']
=======
DB_FILE = 'db/database.json'
>>>>>>> e56d6b9155d0fd95ffd6b4959d1be16fa0bc8ce8
>>>>>>> Stashed changes

def load_data():
    if not os.path.exists(DB_FILE):
        # Updated structure with attendance and leave_requests
        return {
            "users": [], 
            "externals": [], 
            "flp": [{"Mail_ID": "admin@nlife.in"}],
            "requests": [],
            "attendance": [],
            "leave_requests": []
        }
    
    try:
        with open(DB_FILE, 'r') as f:
            data = json.load(f)
            # Ensure new keys exist even in old files
            if "attendance" not in data: data["attendance"] = []
            if "leave_requests" not in data: data["leave_requests"] = []
            return data
    except:
        return {"users": [], "requests": [], "attendance": [], "leave_requests": []}

def save_data(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def get_user(email):
    data = load_data()
    # Check main users, then externals, then FLP list
    user = next((u for u in data['users'] if u['email'] == email), None)
    if user: return user
    
    external = next((e for e in data['externals'] if e['email'] == email), None)
    if external: return {"email": email, "username": external['username'], "type": "user"}
    
    flp = next((f for f in data['flp'] if f['Mail_ID'] == email), None)
    if flp: return {"email": email, "username": email.split('@')[0], "type": "user"}
    
    return None

def sync_user(email, otp):
    data = load_data()
    user = next((u for u in data['users'] if u['email'] == email), None)
    
    if user:
        user['otp'] = otp # Update existing
    else:
        # Add new user to database
        data['users'].append({
            "email": email,
            "username": email.split('@')[0],
            "otp": otp,
            "type": "user",
            "verified": False
        })
    save_data(data)