from flask import Blueprint, render_template, request, session, redirect, url_for, flash
import json
import os
from datetime import datetime

blog_bp = Blueprint('blog', __name__)
BLOG_FILE = 'blog_posts.json'

def get_posts():
    """Helper to load posts from JSON file"""
    if not os.path.exists(BLOG_FILE):
        return []
    with open(BLOG_FILE, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []

def save_new_post(title, author, content):
    """Helper to save a new post"""
    posts = get_posts()
    new_post = {
        "id": len(posts) + 1,
        "title": title,
        "author": author,
        "content": content,
        "date": datetime.now().strftime("%B %d, %Y")
    }
    # Insert at the beginning (newest first)
    posts.insert(0, new_post)
    with open(BLOG_FILE, 'w') as f:
        json.dump(posts, f, indent=4)

@blog_bp.route('/blog', methods=['GET', 'POST'])
def blog():
    # HANDLE POST CREATION (Admin Only)
    if request.method == 'POST':
        # Security Check
        if session.get('type') != 'admin':
            return "Access Denied", 403
        
        title = request.form.get('title')
        author = request.form.get('author') or session.get('username')
        content = request.form.get('content')
        
        if title and content:
            save_new_post(title, author, content)
            return redirect(url_for('blog.blog'))

    # RENDER PAGE
    posts = get_posts()
    is_admin = session.get('type') == 'admin'
    return render_template('blog.html', posts=posts, is_admin=is_admin)