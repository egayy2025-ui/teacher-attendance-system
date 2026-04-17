from flask import Flask, request, redirect, url_for, session, render_template_string, flash, send_file, abort
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import sqlite3
import csv
import io
import os
import qrcode

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")
DB_NAME = "attendance.db"
SCHOOL_NAME = "Knight Gale University"
SCHOOL_LOGO_PATH = "/static/logo.png"  # put your real logo here


# -----------------------------
# Database helpers
# -----------------------------
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'teacher'))
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            grade_section TEXT NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL,
            remarks TEXT,
            marked_by INTEGER NOT NULL,
            method TEXT NOT NULL DEFAULT 'manual',
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(marked_by) REFERENCES users(id),
            UNIQUE(student_id, attendance_date)
        )
        """
    )

    admin = cur.execute("SELECT * FROM users WHERE username = ?", ("admin",)).fetchone()
    if not admin:
        cur.execute(
            "INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
            ("System Admin", "admin", generate_password_hash("admin123"), "admin")
        )

    teacher = cur.execute("SELECT * FROM users WHERE username = ?", ("teacher",)).fetchone()
    if not teacher:
        cur.execute(
            "INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
            ("Default Teacher", "teacher", generate_password_hash("teacher123"), "teacher")
        )

    conn.commit()
    conn.close()


# -----------------------------
# Helpers
# -----------------------------
def login_required():
    return session.get("user_id") is not None


def admin_required():
    return session.get("role") == "admin"


def escape_html(value):
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def status_badge(status):
    css = "present" if status == "Present" else "late" if status == "Late" else "absent"
    return f"<span class='badge {css}'>{escape_html(status)}</span>"


def render_page(title, content, extra_head=""):
    return render_template_string(
        BASE_HTML,
        title=title,
        content=content,
        school_name=SCHOOL_NAME,
        school_logo_path=SCHOOL_LOGO_PATH,
        extra_head=extra_head,
    )


BASE_HTML = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>{{ title }}</title>
    <style>
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: Arial, Helvetica, sans-serif;
            background: linear-gradient(135deg, #fff0f7, #ffd9eb, #fff8fc);
            color: #412432;
        }
        .navbar {
            background: linear-gradient(90deg, #ff4fa1, #d81b77);
            color: white;
            padding: 14px 22px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
            box-shadow: 0 8px 20px rgba(216, 27, 119, 0.25);
        }
        .brand { display: flex; align-items: center; gap: 12px; }
        .brand img {
            width: 46px;
            height: 46px;
            object-fit: cover;
            border-radius: 50%;
            background: white;
            padding: 4px;
        }
        .brand strong { display: block; font-size: 18px; }
        .brand span { font-size: 12px; opacity: 0.95; }
        .nav-links a {
            color: white;
            text-decoration: none;
            font-weight: bold;
            margin-right: 12px;
            font-size: 14px;
        }
        .container {
            max-width: 1200px;
            margin: 22px auto;
            padding: 0 16px 30px;
        }
        .card {
            background: rgba(255,255,255,0.97);
            border: 1px solid #ffc4dd;
            border-radius: 24px;
            padding: 22px;
            box-shadow: 0 12px 30px rgba(0,0,0,0.08);
            margin-bottom: 20px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 18px;
        }
        .stats-number {
            font-size: 34px;
            color: #d81b77;
            font-weight: bold;
        }
        .login-wrap {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-card {
            max-width: 480px;
            width: 100%;
            background: rgba(255,255,255,0.98);
            border-radius: 28px;
            padding: 30px;
            border: 1px solid #ffc4dd;
            box-shadow: 0 16px 40px rgba(216, 27, 119, 0.15);
        }
        .center { text-align: center; }
        .logo-big {
            width: 86px; height: 86px; object-fit: cover; border-radius: 50%;
            background: white; padding: 6px; margin: 0 auto 14px; display: block;
            box-shadow: 0 8px 20px rgba(216, 27, 119, 0.15);
        }
        h1, h2, h3 { margin-top: 0; }
        .muted { color: #8f6175; font-size: 13px; }
        input, select, textarea, button {
            width: 100%;
            padding: 12px;
            margin-top: 8px;
            margin-bottom: 14px;
            border-radius: 12px;
            border: 1px solid #f5bdd7;
            font-size: 14px;
            background: white;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #ff4fa1;
            box-shadow: 0 0 0 3px rgba(255, 79, 161, 0.14);
        }
        button, .btn-link {
            background: linear-gradient(90deg, #ff4fa1, #d81b77);
            color: white;
            border: none;
            text-decoration: none;
            font-weight: bold;
            cursor: pointer;
            display: inline-block;
            padding: 12px 16px;
            border-radius: 12px;
        }
        .btn-gray { background: #7f5a6a; }
        .btn-link { margin-right: 8px; margin-top: 6px; }
        .flash {
            background: #ffe3f0;
            border: 1px solid #ffc4dd;
            color: #a11357;
            border-radius: 12px;
            padding: 12px 14px;
            margin-bottom: 14px;
        }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px 10px; border-bottom: 1px solid #f6d4e3; text-align: left; }
        th { background: #fff0f7; color: #a11357; }
        .badge {
            display: inline-block;
            padding: 7px 11px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: bold;
        }
        .present { background: #dcfce7; color: #166534; }
        .late { background: #fef3c7; color: #92400e; }
        .absent { background: #fee2e2; color: #991b1b; }
        .actions a { color: #d81b77; text-decoration: none; font-weight: bold; margin-right: 10px; }
        .qr-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 16px;
        }
        .qr-card {
            background: white;
            border: 1px solid #ffd5e6;
            border-radius: 18px;
            padding: 16px;
            text-align: center;
        }
        .qr-card img { max-width: 180px; width: 100%; }
        @media (max-width: 700px) {
            .navbar { flex-direction: column; align-items: flex-start; }
            table, thead, tbody, th, td, tr { display: block; }
            thead { display: none; }
            tr { background: white; border: 1px solid #f6d4e3; border-radius: 14px; margin-bottom: 12px; padding: 10px; }
            td { border: none; padding: 8px 0; }
        }
    </style>
    {{ extra_head|safe }}
</head>
<body>
    {% if session.get('user_id') %}
    <div class=\"navbar\">
        <div class=\"brand\">
            <img src=\"{{ school_logo_path }}\" alt=\"School Logo\" onerror=\"this.style.display='none'\">
            <div>
                <strong>{{ school_name }}</strong>
                <span>{{ session.get('role','').title() }} Portal</span>
            </div>
        </div>
        <div class=\"nav-links\">
            <a href=\"{{ url_for('dashboard') }}\">Dashboard</a>
            <a href=\"{{ url_for('students') }}\">Students</a>
            <a href=\"{{ url_for('mark_attendance') }}\">Manual Attendance</a>
            <a href=\"{{ url_for('qr_attendance') }}\">QR Attendance</a>
            <a href=\"{{ url_for('reports') }}\">Reports</a>
            {% if session.get('role') == 'admin' %}
            <a href=\"{{ url_for('admin_panel') }}\">Admin Panel</a>
            {% endif %}
            <a href=\"{{ url_for('logout') }}\">Logout</a>
        </div>
    </div>
    {% endif %}

    <div class=\"container\">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class=\"flash\">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {{ content|safe }}
    </div>
</body>
</html>
"""


# -----------------------------
# Auth
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if login_required():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            flash("Login successful.")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.")

    content = f"""
    <div class=\"login-wrap\">
        <div class=\"login-card\">
            <img class=\"logo-big\" src=\"{SCHOOL_LOGO_PATH}\" alt=\"School Logo\" onerror=\"this.style.display='none'\">
            <div class=\"center\">
                <h1>{SCHOOL_NAME}</h1>
                <p class=\"muted\">Pink Attendance System with Admin Panel and QR Attendance</p>
                <p class=\"muted\"><strong>Admin:</strong> admin / admin123</p>
                <p class=\"muted\"><strong>Teacher:</strong> teacher / teacher123</p>
            </div>
            <form method=\"POST\">
                <label>Username</label>
                <input type=\"text\" name=\"username\" required>
                <label>Password</label>
                <input type=\"password\" name=\"password\" required>
                <button type=\"submit\">Login</button>
            </form>
        </div>
    </div>
    """
    return render_page("Login", content)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


# -----------------------------
# Dashboard
# -----------------------------
@app.route("/dashboard")
def dashboard():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    today = str(date.today())
    total_students = conn.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    total_teachers = conn.execute("SELECT COUNT(*) AS count FROM users WHERE role = 'teacher'").fetchone()["count"]
    present_count = conn.execute("SELECT COUNT(*) AS count FROM attendance WHERE attendance_date = ? AND status = 'Present'", (today,)).fetchone()["count"]
    late_count = conn.execute("SELECT COUNT(*) AS count FROM attendance WHERE attendance_date = ? AND status = 'Late'", (today,)).fetchone()["count"]
    absent_count = conn.execute("SELECT COUNT(*) AS count FROM attendance WHERE attendance_date = ? AND status = 'Absent'", (today,)).fetchone()["count"]
    recent = conn.execute(
        """
        SELECT a.attendance_date, a.status, a.method, s.student_id, s.full_name, s.grade_section
        FROM attendance a
        JOIN students s ON s.id = a.student_id
        ORDER BY a.attendance_date DESC, a.id DESC
        LIMIT 10
        """
    ).fetchall()
    conn.close()

    recent_rows = "".join(
        f"<tr><td>{escape_html(r['attendance_date'])}</td><td>{escape_html(r['student_id'])}</td><td>{escape_html(r['full_name'])}</td><td>{escape_html(r['grade_section'])}</td><td>{status_badge(r['status'])}</td><td>{escape_html(r['method'])}</td></tr>"
        for r in recent
    ) or "<tr><td colspan='6'>No attendance records yet.</td></tr>"

    admin_btn = ""
    if session.get("role") == "admin":
        admin_btn = f'<a class="btn-link btn-gray" href="{url_for("admin_panel")}">Open Admin Panel</a>'

    content = f"""
    <div class=\"card\">
        <h1>Welcome, {escape_html(session.get('full_name'))}</h1>
        <p class=\"muted\">Today: {today}</p>
        <a class=\"btn-link\" href=\"{url_for('mark_attendance')}\">Manual Attendance</a>
        <a class=\"btn-link\" href=\"{url_for('qr_attendance')}\">QR Attendance</a>
        <a class=\"btn-link btn-gray\" href=\"{url_for('student_qr_cards')}\">Student QR Cards</a>
        {admin_btn}
    </div>

    <div class=\"grid\">
        <div class=\"card\"><h3>Total Students</h3><div class=\"stats-number\">{total_students}</div></div>
        <div class=\"card\"><h3>Total Teachers</h3><div class=\"stats-number\">{total_teachers}</div></div>
        <div class=\"card\"><h3>Present Today</h3><div class=\"stats-number\">{present_count}</div></div>
        <div class=\"card\"><h3>Late Today</h3><div class=\"stats-number\">{late_count}</div></div>
        <div class=\"card\"><h3>Absent Today</h3><div class=\"stats-number\">{absent_count}</div></div>
    </div>

    <div class=\"card\">
        <h2>Recent Records</h2>
        <table>
            <thead><tr><th>Date</th><th>Student ID</th><th>Name</th><th>Grade/Section</th><th>Status</th><th>Method</th></tr></thead>
            <tbody>{recent_rows}</tbody>
        </table>
    </div>
    """
    return render_page("Dashboard", content)


# -----------------------------
# Admin panel
# -----------------------------
@app.route("/admin", methods=["GET", "POST"])
def admin_panel():
    if not login_required() or not admin_required():
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "teacher")

        if not full_name or not username or not password:
            flash("Please fill in all user fields.")
        else:
            try:
                conn.execute(
                    "INSERT INTO users (full_name, username, password_hash, role) VALUES (?, ?, ?, ?)",
                    (full_name, username, generate_password_hash(password), role)
                )
                conn.commit()
                flash("User account created successfully.")
            except sqlite3.IntegrityError:
                flash("Username already exists.")

    users = conn.execute("SELECT * FROM users ORDER BY role ASC, full_name ASC").fetchall()
    conn.close()

    user_rows = "".join(
        f"<tr><td>{escape_html(u['full_name'])}</td><td>{escape_html(u['username'])}</td><td>{escape_html(u['role'])}</td><td class='actions'>{'' if u['username']=='admin' else f'<a href="/delete_user/{u['id']}" onclick="return confirm(\'Delete this user?\')">Delete</a>'}</td></tr>"
        for u in users
    )

    content = f"""
    <div class=\"grid\">
        <div class=\"card\">
            <h2>Create User</h2>
            <form method=\"POST\">
                <label>Full Name</label>
                <input type=\"text\" name=\"full_name\" required>
                <label>Username</label>
                <input type=\"text\" name=\"username\" required>
                <label>Password</label>
                <input type=\"password\" name=\"password\" required>
                <label>Role</label>
                <select name=\"role\">
                    <option value=\"teacher\">Teacher</option>
                    <option value=\"admin\">Admin</option>
                </select>
                <button type=\"submit\">Create User</button>
            </form>
        </div>
        <div class=\"card\">
            <h2>System Users</h2>
            <table>
                <thead><tr><th>Name</th><th>Username</th><th>Role</th><th>Action</th></tr></thead>
                <tbody>{user_rows}</tbody>
            </table>
        </div>
    </div>
    """
    return render_page("Admin Panel", content)


@app.route("/delete_user/<int:user_id>")
def delete_user(user_id):
    if not login_required() or not admin_required():
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user and user["username"] != "admin":
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        flash("User deleted successfully.")
    conn.close()
    return redirect(url_for("admin_panel"))


# -----------------------------
# Students
# -----------------------------
@app.route("/students", methods=["GET", "POST"])
def students():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        full_name = request.form.get("full_name", "").strip()
        grade_section = request.form.get("grade_section", "").strip()
        if not student_id or not full_name or not grade_section:
            flash("Please fill in all student fields.")
        else:
            try:
                conn.execute(
                    "INSERT INTO students (student_id, full_name, grade_section) VALUES (?, ?, ?)",
                    (student_id, full_name, grade_section)
                )
                conn.commit()
                flash("Student added successfully.")
            except sqlite3.IntegrityError:
                flash("Student ID already exists.")

    all_students = conn.execute("SELECT * FROM students ORDER BY full_name ASC").fetchall()
    conn.close()

    rows = "".join(
        f"<tr><td>{escape_html(s['student_id'])}</td><td>{escape_html(s['full_name'])}</td><td>{escape_html(s['grade_section'])}</td><td class='actions'><a href='/student_qr/{s['id']}' target='_blank'>QR</a><a href='/delete_student/{s['id']}' onclick=\"return confirm('Delete this student?')\">Delete</a></td></tr>"
        for s in all_students
    ) or "<tr><td colspan='4'>No students added yet.</td></tr>"

    content = f"""
    <div class=\"grid\">
        <div class=\"card\">
            <h2>Add Student</h2>
            <form method=\"POST\">
                <label>Student ID</label>
                <input type=\"text\" name=\"student_id\" required>
                <label>Full Name</label>
                <input type=\"text\" name=\"full_name\" required>
                <label>Grade / Section</label>
                <input type=\"text\" name=\"grade_section\" required>
                <button type=\"submit\">Add Student</button>
            </form>
        </div>
        <div class=\"card\">
            <h2>Student List</h2>
            <table>
                <thead><tr><th>Student ID</th><th>Name</th><th>Grade / Section</th><th>Action</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </div>
    """
    return render_page("Students", content)


@app.route("/delete_student/<int:student_row_id>")
def delete_student(student_row_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_row_id,))
    conn.execute("DELETE FROM students WHERE id = ?", (student_row_id,))
    conn.commit()
    conn.close()
    flash("Student deleted successfully.")
    return redirect(url_for("students"))


# -----------------------------
# Manual attendance
# -----------------------------
@app.route("/attendance", methods=["GET", "POST"])
def mark_attendance():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    selected_date = request.form.get("attendance_date") if request.method == "POST" else str(date.today())
    if not selected_date:
        selected_date = str(date.today())

    if request.method == "POST":
        for student in conn.execute("SELECT * FROM students ORDER BY full_name ASC").fetchall():
            status = request.form.get(f"status_{student['id']}", "Absent")
            remarks = request.form.get(f"remarks_{student['id']}", "").strip()
            existing = conn.execute(
                "SELECT id FROM attendance WHERE student_id = ? AND attendance_date = ?",
                (student["id"], selected_date)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE attendance SET status = ?, remarks = ?, marked_by = ?, method = 'manual' WHERE student_id = ? AND attendance_date = ?",
                    (status, remarks, session["user_id"], student["id"], selected_date)
                )
            else:
                conn.execute(
                    "INSERT INTO attendance (student_id, attendance_date, status, remarks, marked_by, method) VALUES (?, ?, ?, ?, ?, 'manual')",
                    (student["id"], selected_date, status, remarks, session["user_id"])
                )
        conn.commit()
        flash(f"Attendance saved for {selected_date}.")

    students = conn.execute("SELECT * FROM students ORDER BY full_name ASC").fetchall()
    existing_records = conn.execute("SELECT * FROM attendance WHERE attendance_date = ?", (selected_date,)).fetchall()
    attendance_map = {r['student_id']: r for r in existing_records}
    conn.close()

    rows = ""
    for student in students:
        current = attendance_map.get(student["id"])
        current_status = current["status"] if current else "Present"
        current_remarks = current["remarks"] if current else ""
        rows += f"""
        <tr>
            <td>{escape_html(student['student_id'])}</td>
            <td>{escape_html(student['full_name'])}</td>
            <td>{escape_html(student['grade_section'])}</td>
            <td>
                <select name=\"status_{student['id']}\">
                    <option value=\"Present\" {'selected' if current_status == 'Present' else ''}>Present</option>
                    <option value=\"Late\" {'selected' if current_status == 'Late' else ''}>Late</option>
                    <option value=\"Absent\" {'selected' if current_status == 'Absent' else ''}>Absent</option>
                </select>
            </td>
            <td><input type=\"text\" name=\"remarks_{student['id']}\" value=\"{escape_html(current_remarks)}\"></td>
        </tr>
        """
    rows = rows or "<tr><td colspan='5'>No students found.</td></tr>"

    content = f"""
    <div class=\"card\">
        <h2>Manual Attendance</h2>
        <form method=\"POST\">
            <label>Select Date</label>
            <input type=\"date\" name=\"attendance_date\" value=\"{selected_date}\" required>
            <table>
                <thead><tr><th>Student ID</th><th>Name</th><th>Grade / Section</th><th>Status</th><th>Remarks</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
            <button type=\"submit\">Save Attendance</button>
        </form>
    </div>
    """
    return render_page("Manual Attendance", content)


# -----------------------------
# QR attendance
# -----------------------------
@app.route("/qr-attendance")
def qr_attendance():
    if not login_required():
        return redirect(url_for("login"))

    extra_head = '<script src="https://unpkg.com/html5-qrcode" type="text/javascript"></script>'
    mark_url = url_for('qr_mark')

    content = f"""
    <div class=\"card\">
        <h2>QR Attendance Scanner</h2>
        <p class=\"muted\">Scan the student's QR code. It will mark the student as Present for today.</p>
        <div id=\"reader\" style=\"width: 100%; max-width: 500px; margin: auto;\"></div>
        <p id=\"scan-result\" class=\"muted center\">Waiting for QR scan...</p>
    </div>

    <script>
        function onScanSuccess(decodedText) {{
            fetch('{mark_url}', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                body: 'student_code=' + encodeURIComponent(decodedText)
            }})
            .then(response => response.text())
            .then(text => {{
                document.getElementById('scan-result').innerText = text;
            }})
            .catch(() => {{
                document.getElementById('scan-result').innerText = 'Scan failed. Please try again.';
            }});
        }}

        const html5QrCode = new Html5Qrcode("reader");
        Html5Qrcode.getCameras().then(devices => {{
            if (devices && devices.length) {{
                html5QrCode.start(
                    {{ facingMode: 'environment' }},
                    {{ fps: 10, qrbox: 250 }},
                    onScanSuccess
                );
            }}
        }}).catch(() => {{
            document.getElementById('scan-result').innerText = 'Camera access failed.';
        }});
    </script>
    """
    return render_page("QR Attendance", content, extra_head=extra_head)


@app.route("/qr-mark", methods=["POST"])
def qr_mark():
    if not login_required():
        abort(403)

    student_code = request.form.get("student_code", "").strip()
    if not student_code:
        return "Invalid QR code."

    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE student_id = ?", (student_code,)).fetchone()
    if not student:
        conn.close()
        return "Student not found."

    today = str(date.today())
    existing = conn.execute(
        "SELECT id FROM attendance WHERE student_id = ? AND attendance_date = ?",
        (student["id"], today)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE attendance SET status = 'Present', marked_by = ?, method = 'qr' WHERE student_id = ? AND attendance_date = ?",
            (session["user_id"], student["id"], today)
        )
    else:
        conn.execute(
            "INSERT INTO attendance (student_id, attendance_date, status, remarks, marked_by, method) VALUES (?, ?, 'Present', '', ?, 'qr')",
            (student["id"], today, session["user_id"])
        )
    conn.commit()
    conn.close()
    return f"Attendance recorded: {student['full_name']} ({student['student_id']})"


@app.route("/student_qr/<int:student_row_id>")
def student_qr(student_row_id):
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (student_row_id,)).fetchone()
    conn.close()
    if not student:
        abort(404)

    qr = qrcode.QRCode(box_size=10, border=4)
    qr.add_data(student["student_id"])
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


@app.route("/student-qr-cards")
def student_qr_cards():
    if not login_required():
        return redirect(url_for("login"))

    conn = get_db_connection()
    students = conn.execute("SELECT * FROM students ORDER BY full_name ASC").fetchall()
    conn.close()

    cards = "".join(
        f"<div class='qr-card'><img src='/student_qr/{s['id']}' alt='QR'><h3>{escape_html(s['full_name'])}</h3><p>{escape_html(s['student_id'])}</p><p class='muted'>{escape_html(s['grade_section'])}</p></div>"
        for s in students
    ) or "<p>No students added yet.</p>"

    content = f"""
    <div class=\"card\">
        <h2>Student QR Cards</h2>
        <p class=\"muted\">Each QR contains the student's ID code. Print these cards for QR attendance.</p>
        <div class=\"qr-grid\">{cards}</div>
    </div>
    """
    return render_page("Student QR Cards", content)


# -----------------------------
# Reports + CSV Export
# -----------------------------
@app.route("/reports", methods=["GET"])
def reports():
    if not login_required():
        return redirect(url_for("login"))

    report_date = request.args.get("report_date", str(date.today()))
    conn = get_db_connection()
    records = conn.execute(
        """
        SELECT a.attendance_date, a.status, a.remarks, a.method, s.student_id, s.full_name, s.grade_section, u.full_name AS marker_name
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        JOIN users u ON a.marked_by = u.id
        WHERE a.attendance_date = ?
        ORDER BY s.full_name ASC
        """,
        (report_date,)
    ).fetchall()
    conn.close()

    rows = "".join(
        f"<tr><td>{escape_html(r['student_id'])}</td><td>{escape_html(r['full_name'])}</td><td>{escape_html(r['grade_section'])}</td><td>{status_badge(r['status'])}</td><td>{escape_html(r['remarks'] or '')}</td><td>{escape_html(r['method'])}</td><td>{escape_html(r['marker_name'])}</td></tr>"
        for r in records
    ) or "<tr><td colspan='7'>No attendance records found for this date.</td></tr>"

    content = f"""
    <div class=\"card\">
        <h2>Attendance Reports</h2>
        <form method=\"GET\">
            <label>Select Date</label>
            <input type=\"date\" name=\"report_date\" value=\"{report_date}\">
            <button type=\"submit\">View Report</button>
        </form>
        <a class=\"btn-link\" href=\"{url_for('export_csv', report_date=report_date)}\">Export CSV</a>
    </div>
    <div class=\"card\">
        <h3>Attendance Report for {report_date}</h3>
        <table>
            <thead><tr><th>Student ID</th><th>Name</th><th>Grade / Section</th><th>Status</th><th>Remarks</th><th>Method</th><th>Marked By</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>
    </div>
    """
    return render_page("Reports", content)


@app.route("/export_csv")
def export_csv():
    if not login_required():
        return redirect(url_for("login"))

    report_date = request.args.get("report_date", str(date.today()))
    conn = get_db_connection()
    records = conn.execute(
        """
        SELECT a.attendance_date, s.student_id, s.full_name, s.grade_section, a.status, a.remarks, a.method
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.attendance_date = ?
        ORDER BY s.full_name ASC
        """,
        (report_date,)
    ).fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Attendance Date", "Student ID", "Full Name", "Grade/Section", "Status", "Remarks", "Method"])
    for row in records:
        writer.writerow([row["attendance_date"], row["student_id"], row["full_name"], row["grade_section"], row["status"], row["remarks"] or "", row["method"]])

    memory_file = io.BytesIO(output.getvalue().encode("utf-8"))
    memory_file.seek(0)
    output.close()
    return send_file(memory_file, mimetype="text/csv", as_attachment=True, download_name=f"attendance_{report_date}.csv")


init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
