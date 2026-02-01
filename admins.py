from flask import Blueprint, render_template, session, abort, request, redirect, url_for, flash
import database

admin_bp = Blueprint('admin', __name__)

@admin_bp.route("/admins")
def dashboard():
    if session.get("type") not in ["admin", "tester"]: abort(403)
        
    db_data = database.load_data()
    requests = db_data.get("requests", [])
    users = db_data.get("users", [])
    # NEW: Fetch leave requests
    leaves = db_data.get("leave_requests", [])
    
    return render_template("admins.html", requests=requests, users=users, leaves=leaves)

@admin_bp.route("/admin/update_status", methods=["POST"])
def update_status():
    if session.get("type") not in ["admin", "tester"]: abort(403)

    # ... (Existing code for books remains unchanged) ...
    # [Use existing code from source: 11]
    
    user_email = request.form.get('email')
    book_title = request.form.get('book_title')
    new_status = request.form.get('status') 

    db_data = database.load_data()
    requests = db_data.get("requests", [])
    
    updated = False
    for req in requests:
        if req['email'] == user_email and req['book_title'] == book_title:
            req['status'] = new_status
            updated = True
            break 
    
    if updated: database.save_data(db_data)
    return redirect(url_for('admin.dashboard'))

@admin_bp.route("/admin/update_role", methods=["POST"])
def update_role():
    # ... (Existing code for roles remains unchanged) ...
    # [Use existing code from source: 19]
    if session.get("type") != "admin":
        flash("Only Admins can change user roles.")
        return redirect(url_for('admin.dashboard'))

    target_email = request.form.get('email')
    new_role = request.form.get('role')
    db_data = database.load_data()
    users = db_data.get("users", [])

    for user in users:
        if user['email'] == target_email:
            user['type'] = new_role
            database.save_data(db_data)
            break
    
    return redirect(url_for('admin.dashboard'))

# --- NEW ROUTE: LEAVE MANAGEMENT ---
@admin_bp.route("/admin/update_leave", methods=["POST"])
def update_leave():
    if session.get("type") not in ["admin", "tester"]: abort(403)
    
    leave_id = request.form.get('leave_id')
    new_status = request.form.get('status') # approved/rejected
    
    db_data = database.load_data()
    leaves = db_data.get("leave_requests", [])
    
    for leave in leaves:
        if leave['id'] == leave_id:
            leave['status'] = new_status
            database.save_data(db_data)
            break
            
    return redirect(url_for('admin.dashboard'))