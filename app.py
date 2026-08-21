from flask import Flask, redirect, render_template, request, session, url_for

from modules.access import access
from modules.attendance import attendance
from modules.auth import auth
from modules.blog import blog
from modules.chat import chat
from modules.config import SECRET_KEY
from modules.dashboard import dashboard
from modules.ildb import ildb
from modules.languages import languages
from modules.library import library

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.register_blueprint(auth)
app.register_blueprint(library)
app.register_blueprint(dashboard)
app.register_blueprint(languages)
app.register_blueprint(chat)
app.register_blueprint(attendance)
app.register_blueprint(blog)
app.register_blueprint(ildb)
app.register_blueprint(access)


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


PUBLIC_ENDPOINTS = {None, "static", "hello", "blog.index", "blog.view_post", "blog.download_attachment"}


@app.before_request
def require_login():
    if request.endpoint in PUBLIC_ENDPOINTS or request.endpoint.startswith(("auth.", "languages.")):
        return
    if not session.get("logged_in"):
        return redirect(url_for("auth.login"))


@app.route("/")
def hello():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)
