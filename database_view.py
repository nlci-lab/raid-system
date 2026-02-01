from flask import Blueprint, render_template, jsonify, session, redirect, url_for
import pandas as pd

# Define Blueprint
db_view_bp = Blueprint('database_view', __name__)

# The NEW Google Sheet URL you provided
NEW_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTLMPARFpmMOnVtSDSPJy9OwcXQUy75WK-RG4lCCV-VtdXPNzPUjAV0ka9d9tgUEGd_RNdQgXvS77Qg/pub?gid=1071980127&single=true&output=csv"

@db_view_bp.route('/database_view')
def index():
    # 1. Security Check
    if not session.get("verified"):
        return redirect(url_for("auth.login"))

    try:
        # 2. Fetch Data using Pandas
        df = pd.read_csv(NEW_CSV_URL)
        
        # Clean up: Fill NaNs and remove hidden columns (starting with _)
        df = df.fillna('')
        df = df.loc[:, ~df.columns.str.startswith('_')]
        
        # Convert to list of dicts for the template
        data = df.to_dict(orient='records')
        columns = df.columns.tolist()
        
        message = "Database loaded successfully."
    except Exception as e:
        data = []
        columns = []
        message = f"Error loading database: {e}"

    return render_template('database_view.html', data=data, columns=columns, message=message, username=session.get('username'))