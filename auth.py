from flask import Blueprint, render_template, request, redirect, url_for, session
import secrets
import smtplib
import time,json

import database

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    data = database.load_data()
    email_id = json.load(open('db/pass.json', 'r'))['email_id']
    passcode = json.load(open('db/pass.json', 'r'))['passcode']

    step = session.get('login_step', 'email')

    if request.method == "POST":
        if step == 'email':
            # Step 1: User enters the email
            email = request.form.get("email", "").strip().lower()

            # Step 2 & 3: Check if it ends with @nlife.in. If not, bye!
            if (not email.endswith("@nlife.in") and email not in data['externals'] and email not in data['flp']):
                error = "Access Denied: Only NLCI Staffs are allowed."
            else:
                # Step 4: Send OTP, ask for it, and add email/OTP to database
                otp = f"{secrets.randbelow(1_000_000):06d}"

                # find USER
                user = next((u for u in data['users'] if u.get("email") == email), [])

                # OLD USER: update OTP and reset verification. NEW USER: create with OTP and unverified status
                if user:
                    user["otp"] = otp
                    user["verified"] = False # Force re-verification on every login attempt

                # New user flow
                else:
                    user = {
                        "email": email,
                        "username": email.split("@")[0],
                        "type": "user",
                        "otp": otp,
                        "verified": False
                    }
                    data['users'].append(user)

                database.save_data(data) # Save the new OTP/User to database

                # Send the OTP email
                count=0
                max_try = 6
                while count< max_try:
                    try:
                        count+=1
                        msg = f"Subject: RAID SYSTEM OTP\n\nYour login code is: {otp}"
                        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
                            s.login(email_id, passcode)
                            s.sendmail(email_id, email, msg)

                        session['temp_email'] = email
                        session['login_step'] = 'otp' # Move to OTP step
                        return redirect(url_for('auth.login'))
                        break
                    except Exception as e:
                        error = f"Mail error: {e} try:{count}"
                        time.sleep(1)

        elif step == 'otp':
            # Step 5: Verify it (in database make it verify)
            otp_input = request.form.get("otp", "").strip()
            temp_email = session.get('temp_email')

            user = next((u for u in data['users'] if u.get("email") == temp_email), [])

            if user and user.get('otp') == otp_input:
                # Update database: mark as verified and clear the used OTP
                user["verified"] = True
                user["otp"] = None
                database.save_data(data)

                # Update Flask session to log the user in
                session.update({
                    "verified": True,
                    "username": user['username'],
                    "email": user['email'],
                    "type": user.get('type', 'user')
                })

                session.pop('login_step', None)
                session.pop('temp_email', None)
                return redirect(url_for('index'))

            error = "Invalid OTP. Please try again."

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
    data = database.load_data()
    all_requests = data.get("requests", [])

    # 2. Filter for THIS user only
    my_email = session.get("email")
    my_activity = [r for r in all_requests if r.get("email") == my_email]

    # 3. Categorize based on status
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