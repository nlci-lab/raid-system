from flask import Flask, json, render_template, session, redirect, url_for, request

# system imports
from auth import auth_bp
from library import lib_bp
from admins import admin_bp
from blog import blog_bp
from chat import chat_bp
from database_view import db_view_bp
from attendance import attendance_bp

with open('db/pass.json') as f:
    config = json.load(f)
    if config == {}:
        print('System will start')
        exit()


app = Flask(__name__)
app.secret_key = json.load(open('db/pass.json', 'r'))['secret_key']

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(lib_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(blog_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(db_view_bp)
app.register_blueprint(attendance_bp)

@app.route("/", methods=['GET'])
def index():
    if not session.get("verified"):
        return redirect(url_for("auth.login"))

    # Determine if user is admin for specific UI elements
    is_admin = session.get('type') in ['admin', 'tester']

    return render_template(
        "index.html",
        username=session.get('username'),
        is_admin=is_admin
    )

# ==========================================
#  GLOBAL DARK MODE INJECTOR
# ==========================================
@app.after_request
def inject_dark_mode(response):
    if response.mimetype == 'text/html':

        dark_mode_code = """
        <style>
            /* 1. Global Defaults */
            html.dark body { background-color: #111827 !important; color: #f3f4f6 !important; }

            /* 2. TAILWIND CLASS OVERRIDES */
            html.dark .bg-white { background-color: #1f2937 !important; border-color: #374151 !important; color: #f3f4f6 !important; }
            html.dark .bg-gray-50, html.dark .bg-gray-100 { background-color: #111827 !important; }
            html.dark .bg-gray-200 { background-color: #374151 !important; }
            html.dark .text-gray-900 { color: #f9fafb !important; }
            html.dark .text-gray-800, html.dark .text-gray-700 { color: #e5e7eb !important; }
            html.dark .text-gray-500 { color: #9ca3af !important; }
            html.dark .border-gray-200, html.dark .border-gray-100 { border-color: #374151 !important; }

            /* 3. LIBRARY & TABLE FIXES */
            html.dark .table-wrapper {
                background-color: #1f2937 !important;
                border-color: #374151 !important;
                box-shadow: none !important;
            }

            html.dark table { background-color: #1f2937 !important; }
            html.dark tr { background-color: #1f2937 !important; color: #e5e7eb !important; }
            html.dark td { border-color: #374151 !important; color: #e5e7eb !important; }
            html.dark tbody tr:hover { background-color: #374151 !important; }

            html.dark input, html.dark select, html.dark textarea {
                background-color: #374151 !important;
                border-color: #4b5563 !important;
                color: white !important;
            }
            html.dark input::placeholder { color: #9ca3af !important; }

            html.dark .modal-content { background-color: #1f2937 !important; color: white !important; }
            html.dark .detail-item { border-bottom-color: #374151 !important; }
            html.dark .detail-value { color: #f3f4f6 !important; }
            html.dark .detail-label { color: #9ca3af !important; }

            #dm-toggle {
                position: fixed; bottom: 20px; right: 20px;
                width: 50px; height: 50px;
                background: #4f46e5; color: white;
                border-radius: 50%;
                display: flex; align-items: center; justify-content: center;
                cursor: pointer;
                box-shadow: 0 4px 10px rgba(0,0,0,0.3);
                z-index: 9999;
                transition: transform 0.2s;
            }
            #dm-toggle:hover { transform: scale(1.1); }
        </style>

        <div id="dm-toggle" onclick="toggleTheme()" title="Toggle Dark Mode">
            <svg id="dm-icon" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></svg>
        </div>

        <script>
            const html = document.documentElement;
            const icon = document.getElementById('dm-icon');
            const moonPath = '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>';
            const sunPath = '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>';

            function applyTheme(isDark) {
                if (isDark) {
                    html.classList.add('dark');
                    icon.innerHTML = sunPath;
                } else {
                    html.classList.remove('dark');
                    icon.innerHTML = moonPath;
                }
            }

            function toggleTheme() {
                const isDark = html.classList.toggle('dark');
                localStorage.setItem('theme', isDark ? 'dark' : 'light');
                applyTheme(isDark);
            }

            const savedTheme = localStorage.getItem('theme');
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

            if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
                applyTheme(true);
            } else {
                applyTheme(false);
            }
        </script>
        """

        data = response.get_data(as_text=True)
        if "</body>" in data:
            data = data.replace("</body>", dark_mode_code + "</body>")
            response.set_data(data)

    return response

if __name__ == "__main__":
    app.run(debug=True)