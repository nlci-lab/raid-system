from flask import Blueprint, render_template, jsonify, session, request
import pandas as pd
from datetime import datetime

import database 

lib_bp = Blueprint('library', __name__)

# Your specific Google Sheet URL
CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vQ77xps4Ww4PvnNXBNyZLRgfXPJpcigxsF6zV99J-hI9vAmVXHWaCjZJ0nEKtAz9ymUipKqv51HoH45/pub?gid=1154456721&single=true&output=csv"

@lib_bp.route('/library')
def home():
    # 1. Security Check: Ensure user is logged in
    if not session.get("verified"):
         return jsonify({"success": False, "message": "User not authorized"}), 403

    try:
        # Read the CSV directly from the URL
        df = pd.read_csv(CSV_URL)
        
        # specific clean up: fill empty cells with an empty string so they don't show as "NaN"
        df = df.fillna('')

        # Remove columns starting with "_"
        df = df.loc[:, ~df.columns.str.startswith('_')]
        
        # Convert the data to a list of dictionaries
        data = df.to_dict(orient='records')
        
        # Get the column names for the table header
        columns = df.columns.tolist()
        
        message = "Data fetched successfully!"
    except Exception as e:
        data = []
        columns = []
        message = f"Error reading sheet: {e}"

    return render_template('library.html', data=data, columns=columns, message=message)


@lib_bp.route("/request_book", methods=["POST"])
def request_book():
    # 1. Security Check: Ensure user is logged in
    if not session.get("verified"):
         return jsonify({"success": False, "message": "User not authorized"}), 403

    try:
        # 2. Get data from the frontend
        req_data = request.get_json()
        book_title = req_data.get("book_title", "Unknown Title")
        
        # 3. Prepare the request record
        new_request = {
            "username": session.get("username"),
            "email": session.get("email"),
            "book_title": book_title,
            "request_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "pending"
        }

        # 4. Save to database.json using the existing database module
        db_data = database.load_data()
        
        # Initialize 'requests' list if it doesn't exist
        if "requests" not in db_data:
            db_data["requests"] = []
            
        db_data["requests"].append(new_request)
        database.save_data(db_data)

        return jsonify({"success": True, "message": "Book requested successfully!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Server Error: {str(e)}"}), 500
    