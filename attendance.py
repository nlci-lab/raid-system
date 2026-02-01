from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from datetime import datetime
import database

attendance_bp = Blueprint('attendance', __name__)

# Leave Configuration
LEAVE_LIMITS = {
    "CL": 10,  # Casual Leave
    "SL": 10,  # Sick Leave
    "AL": 21   # Annual Leave
}

def calculate_days(start_str, end_str):
    """Helper to calculate number of days between two dates (inclusive)"""
    try:
        d1 = datetime.strptime(start_str, "%Y-%m-%d")
        d2 = datetime.strptime(end_str, "%Y-%m-%d")
        return (d2 - d1).days + 1
    except:
        return 0

@attendance_bp.route('/attendance')
def dashboard():
    if not session.get("verified"):
        return redirect(url_for("auth.login"))

    db_data = database.load_data()
    my_email = session.get('email')
    
    # 1. Fetch My Attendance
    all_attendance = db_data.get('attendance', [])
    my_attendance = [a for a in all_attendance if a['email'] == my_email]
    
    # 2. Check Today's Status
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_record = next((a for a in my_attendance if a['date'] == today_str), None)

    # 3. Fetch My Leaves & Calculate Balances
    all_leaves = db_data.get('leave_requests', [])
    my_leaves = [l for l in all_leaves if l['email'] == my_email]
    
    used = {"CL": 0, "SL": 0, "AL": 0}
    for leave in my_leaves:
        if leave['status'] == 'approved':
            l_type = leave.get('type', 'CL')
            days = calculate_days(leave['start_date'], leave['end_date'])
            if l_type in used:
                used[l_type] += days

    balance = {
        "CL": LEAVE_LIMITS["CL"] - used["CL"],
        "SL": LEAVE_LIMITS["SL"] - used["SL"],
        "AL": LEAVE_LIMITS["AL"] - used["AL"]
    }

    return render_template(
        'attendance.html', 
        username=session.get('username'),
        attendance=my_attendance,
        leaves=my_leaves,
        today_record=today_record, # Passing the specific record object
        balance=balance,
        limits=LEAVE_LIMITS,
        today=today_str
    )

@attendance_bp.route('/attendance/mark', methods=['POST'])
def mark_attendance():
    if not session.get("verified"): return redirect(url_for("auth.login"))
    
    db_data = database.load_data()
    my_email = session.get('email')
    today_str = datetime.now().strftime("%Y-%m-%d")
    action = request.form.get('action') # 'check_in' or 'check_out'
    user_time = request.form.get('time_input') # The manual time input
    
    if "attendance" not in db_data: db_data["attendance"] = []
    
    # Find existing record for today
    record_idx = next((i for i, a in enumerate(db_data['attendance']) if a['email'] == my_email and a['date'] == today_str), None)

    if action == 'check_in':
        if record_idx is None:
            # Create new record
            new_entry = {
                "email": my_email,
                "username": session.get('username'),
                "date": today_str,
                "entry_time": user_time,
                "exit_time": None,
                "status": "Working"
            }
            db_data['attendance'].append(new_entry)
            
    elif action == 'check_out':
        if record_idx is not None:
            # Update existing record
            db_data['attendance'][record_idx]['exit_time'] = user_time
            db_data['attendance'][record_idx]['status'] = "Present" # Completed day

    database.save_data(db_data)
    return redirect(url_for('attendance.dashboard'))

@attendance_bp.route('/attendance/leave', methods=['POST'])
def request_leave():
    if not session.get("verified"): return redirect(url_for("auth.login"))
    
    db_data = database.load_data()
    
    leave_type = request.form.get('leave_type')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    reason = request.form.get('reason')
    
    days_requested = calculate_days(start_date, end_date)
    
    if days_requested <= 0:
        return redirect(url_for('attendance.dashboard'))

    new_leave = {
        "id": f"leave_{len(db_data.get('leave_requests', [])) + 1}",
        "email": session.get('email'),
        "username": session.get('username'),
        "type": leave_type,
        "days": days_requested,
        "reason": reason,
        "start_date": start_date,
        "end_date": end_date,
        "applied_on": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending"
    }
    
    if "leave_requests" not in db_data: db_data["leave_requests"] = []
    db_data['leave_requests'].append(new_leave)
    database.save_data(db_data)
    
    return redirect(url_for('attendance.dashboard'))