from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import os, time, hashlib, base64
from collections import defaultdict

app = Flask(__name__)
app.secret_key = "chatapp_secret_sus"

USERS_FILE    = "data/users.txt"
MESSAGES_FILE = "data/messages.txt"
AVATARS_DIR   = "data/avatars"
DM_DIR        = "data/dms"

os.makedirs(AVATARS_DIR, exist_ok=True)
os.makedirs(DM_DIR,      exist_ok=True)

# In-memory signaling store: {username: [signals]}
call_signals = defaultdict(list)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_users():
    users = {}
    if not os.path.exists(USERS_FILE):
        return users
    with open(USERS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if ":" in line:
                u, p = line.split(":", 1)
                users[u] = p
    return users

def save_user(username, password):
    with open(USERS_FILE, "a") as f:
        f.write(f"{username}:{hash_pw(password)}\n")

AVATAR_COLORS = ["#f59e0b","#10b981","#3b82f6","#ef4444","#8b5cf6","#ec4899","#14b8a6","#f97316","#06b6d4"]

def get_user_color(username):
    users = list(get_users().keys())
    if username in users:
        return AVATAR_COLORS[users.index(username) % len(AVATAR_COLORS)]
    return AVATAR_COLORS[0]

def has_avatar(username):
    return os.path.exists(os.path.join(AVATARS_DIR, f"{username}.jpg"))

def read_file_messages(filepath, since=0):
    msgs = []
    if not os.path.exists(filepath):
        return msgs
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) == 4:
                ts, sender, color, text = parts
                if float(ts) > since:
                    msgs.append({"ts": float(ts), "sender": sender, "color": color, "text": text})
    return msgs

def write_message(filepath, sender, text):
    color = get_user_color(sender)
    ts    = time.time()
    safe  = text.replace("|", "｜").replace("\n", " ")
    with open(filepath, "a") as f:
        f.write(f"{ts}|{sender}|{color}|{safe}\n")

def dm_path(u1, u2):
    key = "_".join(sorted([u1, u2]))
    return os.path.join(DM_DIR, f"{key}.txt")

@app.route("/")
def index():
    return redirect(url_for("chat") if "user" in session else url_for("login"))

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        users = get_users()
        if u in users and users[u] == hash_pw(p):
            session["user"] = u
            return redirect(url_for("chat"))
        error = "Invalid credentials"
    return render_template("login.html", error=error)

@app.route("/register", methods=["GET","POST"])
def register():
    error = None
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        if not u or not p:
            error = "All fields required"
        elif len(u) < 3:
            error = "Username must be 3+ characters"
        elif "|" in u or ":" in u:
            error = "No | or : in username"
        else:
            if u in get_users():
                error = "Username taken"
            else:
                save_user(u, p)
                session["user"] = u
                return redirect(url_for("chat"))
    return render_template("register.html", error=error)

@app.route("/chat")
def chat():
    if "user" not in session:
        return redirect(url_for("login"))
    me = session["user"]
    return render_template("chat.html",
        username=me,
        color=get_user_color(me),
        has_avatar=has_avatar(me)
    )

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/avatar/<username>")
def avatar(username):
    path = os.path.join(AVATARS_DIR, f"{username}.jpg")
    if os.path.exists(path):
        return send_file(path, mimetype="image/jpeg")
    return "", 404

@app.route("/upload_avatar", methods=["POST"])
def upload_avatar():
    if "user" not in session:
        return jsonify({"ok": False}), 401
    data = request.json.get("data", "")
    if not data:
        return jsonify({"ok": False})
    try:
        raw  = base64.b64decode(data.split(",")[-1])
        path = os.path.join(AVATARS_DIR, f"{session['user']}.jpg")
        with open(path, "wb") as f:
            f.write(raw)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "err": str(e)})

@app.route("/users")
def users_list():
    if "user" not in session:
        return jsonify([])
    me    = session["user"]
    users = list(get_users().keys())
    result = []
    for u in users:
        if u == me:
            continue
        result.append({
            "username":   u,
            "color":      get_user_color(u),
            "has_avatar": has_avatar(u)
        })
    return jsonify(result)

@app.route("/send", methods=["POST"])
def send():
    if "user" not in session:
        return jsonify({"ok": False}), 401
    text = request.json.get("text","").strip()
    if text:
        write_message(MESSAGES_FILE, session["user"], text)
    return jsonify({"ok": True})

@app.route("/messages")
def messages():
    if "user" not in session:
        return jsonify([]), 401
    since = float(request.args.get("since", 0))
    return jsonify(read_file_messages(MESSAGES_FILE, since))

@app.route("/dm/send", methods=["POST"])
def dm_send():
    if "user" not in session:
        return jsonify({"ok": False}), 401
    to   = request.json.get("to","").strip()
    text = request.json.get("text","").strip()
    if to and text and to in get_users():
        write_message(dm_path(session["user"], to), session["user"], text)
    return jsonify({"ok": True})

@app.route("/dm/messages/<other>")
def dm_messages(other):
    if "user" not in session:
        return jsonify([]), 401
    since = float(request.args.get("since", 0))
    return jsonify(read_file_messages(dm_path(session["user"], other), since))

# ─── WebRTC Signaling ──────────────────────────────────────

@app.route("/call/signal", methods=["POST"])
def call_signal():
    if "user" not in session:
        return jsonify({"ok": False}), 401
    data = request.json
    to   = data.get("to", "")
    if not to or to not in get_users():
        return jsonify({"ok": False, "err": "unknown user"})
    signal = {
        "from": session["user"],
        "type": data.get("type"),
        "payload": data.get("payload"),
        "ts": time.time()
    }
    call_signals[to].append(signal)
    call_signals[to] = [s for s in call_signals[to] if time.time() - s["ts"] < 60]
    return jsonify({"ok": True})

@app.route("/call/poll")
def call_poll():
    if "user" not in session:
        return jsonify([]), 401
    me = session["user"]
    signals = list(call_signals.get(me, []))
    call_signals[me] = []
    return jsonify(signals)

if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
