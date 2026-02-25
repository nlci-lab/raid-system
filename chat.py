from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for
from datetime import datetime

import database

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat')
def index():
    if not session.get("verified"):
        return redirect(url_for("auth.login"))
    return render_template('chat.html', username=session.get('username'))

@chat_bp.route('/chat/api/init')
def get_contacts():
    """Returns list of Users (Direct Messages) and Groups"""
    if not session.get("verified"): return jsonify({}), 403

    # 1. Get Users from main DB
    db_data = database.load_data()
    users = [{"id": u['email'], "name": u['username'], "type": "user"} for u in db_data.get('users', []) if u['email'] != session.get('email')]
    
    # 2. Get Groups from Chat DB
    chat_data = load_chat_data()
    groups = [{"id": g['id'], "name": g['name'], "type": "group"} for g in chat_data.get('groups', [])]
    
    return jsonify({"users": users, "groups": groups})

@chat_bp.route('/chat/api/messages')
def get_messages():
    """Get messages for a specific conversation"""
    target_id = request.args.get('target_id') # Can be a group_id or user_email
    chat_data = load_chat_data()
    my_email = session.get('email')
    
    filtered_msgs = []
    for m in chat_data.get('messages', []):
        # Logic for Group Chat
        if m.get('to_type') == 'group' and m.get('to') == target_id:
            filtered_msgs.append(m)
        # Logic for Direct Message (DM)
        elif m.get('to_type') == 'user':
            # Show if I sent it to Target OR Target sent it to Me
            if (m['from_email'] == my_email and m['to'] == target_id) or \
               (m['from_email'] == target_id and m['to'] == my_email):
                filtered_msgs.append(m)
                
    return jsonify(filtered_msgs)

@chat_bp.route('/chat/api/send', methods=['POST'])
def send_message():
    if not session.get("verified"): return jsonify({"success": False}), 403
    
    data = request.json
    chat_data = load_chat_data()
    
    new_msg = {
        "text": data.get('text'),
        "from": session.get('username'),
        "from_email": session.get('email'),
        "to": data.get('target_id'),
        "to_type": data.get('target_type'), # 'group' or 'user'
        "timestamp": datetime.now().strftime("%H:%M")
    }
    
    chat_data['messages'].append(new_msg)
    save_chat_data(chat_data)
    
    return jsonify({"success": True})

@chat_bp.route('/chat/api/create_group', methods=['POST'])
def create_group():
    data = request.json
    group_name = data.get('name')
    if not group_name: return jsonify({"success": False})
    
    chat_data = load_chat_data()
    new_group = {
        "id": f"group_{len(chat_data['groups'])+1}",
        "name": group_name,
        "members": ["all"] # Simplified: Everyone can join public groups
    }
    chat_data['groups'].append(new_group)
    save_chat_data(chat_data)
    
    return jsonify({"success": True})