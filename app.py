import logging
import sqlite3
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from db import init_db

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"
IMAGE_DIR = BASE_DIR.parent / "static" / "images"

app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")
CORS(app)
logger = logging.getLogger(__name__)

init_db()

# =========================
# 🚨 DATABASE MIGRATION (SAFE)
# =========================
try:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # ETA column
    try:
        c.execute("ALTER TABLE issues ADD COLUMN eta TEXT DEFAULT 'Pending Assignment'")
    except:
        pass

    # IMAGE column (IMPORTANT)
    try:
        c.execute("ALTER TABLE issues ADD COLUMN image_url TEXT")
    except:
        pass

    conn.commit()
    conn.close()
except:
    pass


def _serve_frontend_file(filename):
    if FRONTEND_DIR.exists():
        return send_from_directory(FRONTEND_DIR, filename)
    return jsonify({
        "message": "Backend is running, but frontend files are not deployed with this service."
    }), 404


def _analyze_issue(description):
    try:
        from ai import analyze_issue
        return analyze_issue(description)
    except Exception as exc:
        logger.warning("AI analysis unavailable: %s", exc)
        return "AI analysis processing..."

# =========================
# 📄 ROUTES
# =========================

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/')
def home():
    if FRONTEND_DIR.exists():
        return send_from_directory(FRONTEND_DIR, "index.html")
    return jsonify({
        "service": "smart-kolhapur-backend",
        "status": "ok",
        "message": "Backend is running."
    })

@app.route('/signup-page')
def signup_page():
    return _serve_frontend_file("signup.html")

@app.route('/login-page')
def login_page():
    return _serve_frontend_file("login.html")

@app.route('/dashboard-page')
def dashboard_page():
    return _serve_frontend_file("dashboard.html")

@app.route('/gov-dashboard')
def gov_dashboard_page():
    return _serve_frontend_file("gov-dashboard.html")

@app.route('/static/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(IMAGE_DIR, filename)

# =========================
# 🔐 AUTH
# =========================

@app.route('/signup', methods=['POST'])
def signup():
    data = request.json
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE email=?", (data['email'],))
    if c.fetchone():
        return jsonify({"message": "User already exists ❌"}), 400

    c.execute(
        "INSERT INTO users (name, phone, email, password, points) VALUES (?, ?, ?, ?, ?)",
        (data['name'], data['phone'], data['email'], generate_password_hash(data['password']), 10)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Account created successfully 🚀"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT id, password FROM users WHERE email=?", (data['email'],))
    user = c.fetchone()
    conn.close()

    if user and check_password_hash(user[1], data['password']):
        return jsonify({"message": "Login success", "user_id": user[0]})
    else:
        return jsonify({"message": "Invalid credentials ❌"}), 401

@app.route('/get-user', methods=['GET'])
def get_user():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE id = 1")
    user = c.fetchone()
    conn.close()
    return jsonify({"points": user[0] if user else 10})

@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT name, points FROM users ORDER BY points DESC LIMIT 5")
    leaders = [{"name": row[0], "points": row[1]} for row in c.fetchall()]
    conn.close()
    if not leaders:
        leaders = [{"name": "No citizens registered yet", "points": 0}]
    return jsonify(leaders)

# =========================
# 🤖 ISSUES & GOV MANAGEMENT
# =========================

@app.route('/report-issue', methods=['POST'])
def report_issue():
    data = request.json
    description = data.get("description")
    image_url = data.get("image")  # 🔥 added

    ai_analysis = _analyze_issue(description)

    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute(
        "INSERT INTO issues (user_id, description, ai_analysis, status, eta, image_url) VALUES (?, ?, ?, 'Pending', 'Pending Assignment', ?)",
        (1, description, ai_analysis, image_url)
    )

    c.execute("UPDATE users SET points = points + 5 WHERE id = 1")
    c.execute("SELECT points FROM users WHERE id = 1")
    updated_points = c.fetchone()
    new_points = updated_points[0] if updated_points else 15

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Reported 🚀 (+5 Points)",
        "analysis": ai_analysis,
        "new_points": new_points
    })

@app.route('/get-issues')
def get_issues():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # 🔥 added image_url
    c.execute("""
SELECT issues.id, issues.description, issues.ai_analysis, issues.status, issues.eta, issues.image_url,
       users.name, users.phone, users.email
FROM issues
JOIN users ON issues.user_id = users.id
ORDER BY issues.id DESC
""")

    data = []
    for row in c.fetchall():
       data.append({
    "id": row[0],
    "description": row[1],
    "ai_analysis": row[2],
    "status": row[3],
    "eta": row[4],
    "image_url": row[5],
    "name": row[6],      # ✅ added
    "phone": row[7],     # ✅ added
    "email": row[8]      # ✅ added
})

    conn.close()
    return jsonify(data)

@app.route('/delete-issue/<int:issue_id>', methods=['DELETE'])
def delete_issue(issue_id):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("DELETE FROM issues WHERE id = ?", (issue_id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Issue deleted successfully 🗑️"})

@app.route('/update-issue', methods=['POST'])
def update_issue():
    data = request.json
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE issues SET status = ?, eta = ? WHERE id = ?", (data['status'], data['eta'], data['id']))
    conn.commit()
    conn.close()
    return jsonify({"message": "Issue updated by Gov 🏛️"})

# =========================
# 🏛️ SECURE GOV AUTHENTICATION
# =========================

@app.route('/gov-login-auth', methods=['POST'])
def gov_login_auth():
    data = request.json
    gov_id = data.get("gov_id")
    password = data.get("password")

    if gov_id == "KMC-AUTH-999" and password == "KMC2026":
        return jsonify({"success": True, "message": "Access Granted 🏛️"})
    else:
        return jsonify({"success": False, "message": "Access Denied ❌"}), 401

# =========================
# 🚀 RUN
# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
