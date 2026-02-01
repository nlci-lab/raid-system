from flask import Blueprint, render_template, request, redirect, url_for, session
from database import get_user, sync_user, load_data
import secrets
import smtplib

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    step = session.get('login_step', 'email') # Track if we are asking for Email or OTP

    if request.method == "POST":
        if step == 'email':
            email = request.form.get("email", "").strip().lower()
            if not email.endswith("@nlife.in") and not get_user(email):
                error = "Access Denied: Email not authorized."
            else:
                otp = f"{secrets.randbelow(1_000_000):06d}"
                sync_user(email, otp)
                
                # Send Email
                try:
                    msg = f"Subject: OTP\n\nYour code: {otp}"
                    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                        s.login("nlci_raidadmin@nlife.in", "asgb jkjf vzef wbnx")
                        s.sendmail("nlci_raidadmin@nlife.in", email, msg)
                    
                    session['temp_email'] = email
                    session['login_step'] = 'otp'
                    return redirect(url_for('auth.login'))
                except Exception as e:
                    error = f"Mail error: {e}"

        elif step == 'otp':
            otp_input = request.form.get("otp", "").strip()
            user = get_user(session.get('temp_email'))
            
            # ... inside the elif step == 'otp': block
            if user and user.get('otp') == otp_input:
                # ADD "type": user.get('type', 'user') HERE
                session.update({
                    "verified": True, 
                    "username": user['username'], 
                    "email": user['email'],
                    "type": user.get('type', 'user')  # <--- Critical Fix
                })
                session.pop('login_step', None)
                return redirect(url_for('index'))
            error = "Invalid OTP"

    return render_template("auth.html", step=session.get('login_step', 'email'), error=error)

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/profile")
def profile():
    if not session.get("verified"):
        return redirect(url_for("auth.login"))
    
    # 1. Load all data
    db_data = load_data()
    all_requests = db_data.get("requests", [])
    
    # 2. Filter for THIS user only
    my_email = session.get("email")
    my_activity = [r for r in all_requests if r.get("email") == my_email]
    
    # 3. Categorize based on status
    # Note: These statuses ('issued', 'returned') depend on the Admin updating them later.
    pending_requests = [r for r in my_activity if r.get("status") == "pending"]
    books_in_hand = [r for r in my_activity if r.get("status") == "issued"]
    history = [r for r in my_activity if r.get("status") == "returned"]
    
    return render_template(
        "profile.html", 
        user=session, 
        pending=pending_requests,
        in_hand=books_in_hand,
        history=history
    )