from flask import Flask, request, redirect, url_for, session, render_template_string, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date
import sqlite3
import csv
import io

app = Flask(__name__)
app.secret_key = "change-this-secret-key"
DB_NAME = "attendance.db"
SCHOOL_NAME = "Knight Gale University"
SCHOOL_LOGO = "🎓"

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
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
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
            FOREIGN KEY(student_id) REFERENCES students(id),
            FOREIGN KEY(marked_by) REFERENCES teachers(id),
            UNIQUE(student_id, attendance_date)
        )
        """
    )

    teacher = cur.execute("SELECT * FROM teachers WHERE username = ?", ("admin",)).fetchone()
    if not teacher:
        cur.execute(
            "INSERT INTO teachers (full_name, username, password_hash) VALUES (?, ?, ?)",
            ("Default Teacher", "admin", generate_password_hash("admin123"))
        )

    conn.commit()
    conn.close()


# -----------------------------
# UI helpers
# -----------------------------
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
            background: linear-gradient(135deg, #fff1f7, #ffe4ef, #fff8fb);
            color: #3f2a37;
        }
        .navbar {
            background: linear-gradient(90deg, #d63384, #c2185b);
            color: white;
            padding: 15px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
            box-shadow: 0 6px 18px rgba(194, 24, 91, 0.25);
        }
        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .brand-logo {
            width: 42px;
            height: 42px;
            border-radius: 50%;
            background: rgba(255,255,255,0.22);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 22px;
        }
        .brand-text strong { display: block; font-size: 18px; }
        .brand-text span { font-size: 12px; opacity: 0.92; }
        .navbar a {
            color: white;
            text-decoration: none;
            margin-right: 14px;
            font-weight: bold;
            font-size: 14px;
        }
        .container {
            max-width: 1180px;
            margin: 24px auto;
            padding: 0 16px 30px;
        }
        .card {
            background: rgba(255,255,255,0.95);
            border-radius: 22px;
            padding: 22px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            margin-bottom: 20px;
            border: 1px solid #ffd1e3;
        }
        h1, h2, h3 { margin-top: 0; }
        .hero-title { font-size: 28px; margin-bottom: 6px; }
        .muted { color: #7c5a69; font-size: 13px; }
        .subtle { color: #8b6b79; }
        input, select, textarea, button {
            width: 100%;
            padding: 12px;
            margin-top: 8px;
            margin-bottom: 14px;
            border-radius: 12px;
            border: 1px solid #f3bfd2;
            font-size: 14px;
            background: white;
        }
        input:focus, select:focus, textarea:focus {
            outline: none;
            border-color: #d63384;
            box-shadow: 0 0 0 3px rgba(214, 51, 132, 0.12);
        }
        button {
            background: linear-gradient(90deg, #d63384, #c2185b);
            color: white;
            border: none;
            cursor: pointer;
            font-weight: bold;
        }
        button:hover { opacity: 0.95; }
        .btn-link {
            display: inline-block;
            text-decoration: none;
            color: white;
            background: linear-gradient(90deg, #d63384, #c2185b);
            padding: 11px 16px;
            border-radius: 12px;
            font-weight: bold;
            margin-right: 8px;
            margin-top: 6px;
        }
        .btn-gray {
            background: #7a6270;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            overflow: hidden;
        }
        th, td {
            border-bottom: 1px solid #f7d5e3;
            padding: 12px 10px;
            text-align: left;
            vertical-align: top;
        }
        th {
            background: #fff0f6;
            color: #8c2459;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 18px;
        }
        .flash {
            padding: 12px 14px;
            border-radius: 12px;
            margin-bottom: 14px;
            background: #ffe3f0;
            color: #8c2459;
            border: 1px solid #ffc2dd;
        }
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
        .actions a {
            text-decoration: none;
            color: #c2185b;
            font-weight: bold;
            margin-right: 10px;
        }
        .stats-number {
            font-size: 34px;
            margin: 8px 0 0;
            color: #c2185b;
        }
        .login-wrap {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .login-card {
            max-width: 470px;
            width: 100%;
            background: rgba(255,255,255,0.97);
            border-radius: 26px;
            padding: 28px;
            box-shadow: 0 14px 40px rgba(194, 24, 91, 0.16);
            border: 1px solid #ffd1e3;
        }
        .logo-big {
            width: 76px;
            height: 76px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 14px;
            background: linear-gradient(135deg, #ffd6e8, #fff);
            font-size: 38px;
            box-shadow: inset 0 0 0 2px #ffd1e3;
        }
        .center { text-align: center; }
        @media (max-width: 700px) {
            .navbar { flex-direction: column; align-items: flex-start; }
            table, thead, tbody, th, td, tr { display: block; }
            thead { display: none; }
            tr {
                background: white;
                border: 1px solid #f7d5e3;
                border-radius: 14px;
                margin-bottom: 12px;
                padding: 10px;
            }
            td { border: none; padding: 8px 0; }
        }
    </style>
</head>
<body>
    {% if session.get('teacher_id') %}
    <div class=\"navbar\">
        <div class=\"brand\">
            <div class=\"brand-logo\">{{ school_logo }}</div>
            <div class=\"brand-text\">
                <strong>{{ school_name }}</strong>
                <span>Teacher Attendance System</span>
            </div>
        </div>
        <div>
            <a href=\"{{ url_for('dashboard') }}\">Dashboard</a>
            <a href=\"{{ url_for('students') }}\">Students</a>
            <a href=\"{{ url_for('mark_attendance') }}\">Attendance</a>
            <a href=\"{{ url_for('reports') }}\">Reports</a>
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


def render_page(title, content):
    return render_template_string(BASE_HTML, title=title, content=content, school_name=SCHOOL_NAME, school_logo=SCHOOL_LOGO)


def login_required():
    return session.get("teacher_id") is not None


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


# -----------------------------
# Auth routes
# -----------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if login_required():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = get_db_connection()
        teacher = conn.execute("SELECT * FROM teachers WHERE username = ?", (username,)).fetchone()
        conn.close()

        if teacher and check_password_hash(teacher["password_hash"], password):
            session["teacher_id"] = teacher["id"]
            session["teacher_name"] = teacher["full_name"]
            flash("Login successful.")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.")

    content = f"""
    <div class=\"login-wrap\">
        <div class=\"login-card\">
            <div class=\"logo-big\">{SCHOOL_LOGO}</div>
            <div class=\"center\">
                <h1>{SCHOOL_NAME}</h1>
                <p class=\"subtle\">Teacher Attendance Website</p>
                <p class=\"muted\">Default account: <strong>admin</strong> / <strong>admin123</strong></p>
            </div>
            <form method=\"POST\">
                <label>Username</label>
                <input type=\"text\" name=\"username\" placeholder=\"Enter username\" required>

                <label>Password</label>
                <input type=\"password\" name=\"password\" placeholder=\"Enter password\" required>

                <button type=\"submit\">Login</button>
            </form>
        </div>
    </div>
    """
    return render_page("Teacher Login", content)


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
    total_students = conn.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    today = str(date.today())
    present_count = conn.execute("SELECT COUNT(*) AS count FROM attendance WHERE attendance_date = ? AND status = 'Present'", (today,)).fetchone()["count"]
    late_count = conn.execute("SELECT COUNT(*) AS count FROM attendance WHERE attendance_date = ? AND status = 'Late'", (today,)).fetchone()["count"]
    absent_count = conn.execute("SELECT COUNT(*) AS count FROM attendance WHERE attendance_date = ? AND status = 'Absent'", (today,)).fetchone()["count"]
    recent = conn.execute(
        """
        SELECT a.attendance_date, a.status, s.student_id, s.full_name, s.grade_section
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        ORDER BY a.attendance_date DESC, s.full_name ASC
        LIMIT 10
        """
    ).fetchall()
    conn.close()

    recent_rows = "".join(
        f"<tr><td>{escape_html(row['attendance_date'])}</td><td>{escape_html(row['student_id'])}</td><td>{escape_html(row['full_name'])}</td><td>{escape_html(row['grade_section'])}</td><td><span class='badge {'present' if row['status']=='Present' else 'late' if row['status']=='Late' else 'absent'}'>{escape_html(row['status'])}</span></td></tr>"
        for row in recent
    )
    if not recent_rows:
        recent_rows = "<tr><td colspan='5'>No attendance records yet.</td></tr>"

    content = f"""
    <div class=\"card\">
        <h1 class=\"hero-title\">Welcome, {escape_html(session.get('teacher_name'))}</h1>
        <p class=\"muted\">Today: {today}</p>
        <a class=\"btn-link\" href=\"{url_for('mark_attendance')}\">Mark Attendance</a>
        <a class=\"btn-link btn-gray\" href=\"{url_for('students')}\">Manage Students</a>
    </div>

    <div class=\"grid\">
        <div class=\"card\"><h3>Total Students</h3><div class=\"stats-number\">{total_students}</div></div>
        <div class=\"card\"><h3>Present Today</h3><div class=\"stats-number\">{present_count}</div></div>
        <div class=\"card\"><h3>Late Today</h3><div class=\"stats-number\">{late_count}</div></div>
        <div class=\"card\"><h3>Absent Today</h3><div class=\"stats-number\">{absent_count}</div></div>
    </div>

    <div class=\"card\">
        <h2>Recent Attendance</h2>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Student ID</th>
                    <th>Name</th>
                    <th>Grade/Section</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>{recent_rows}</tbody>
        </table>
    </div>
    """
    return render_page("Dashboard", content)


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

    student_rows = "".join(
        f"<tr><td>{escape_html(s['student_id'])}</td><td>{escape_html(s['full_name'])}</td><td>{escape_html(s['grade_section'])}</td><td class='actions'><a href='/delete_student/{s['id']}' onclick=\"return confirm('Delete this student?')\">Delete</a></td></tr>"
        for s in all_students
    )
    if not student_rows:
        student_rows = "<tr><td colspan='4'>No students added yet.</td></tr>"

    content = f"""
    <div class=\"grid\">
        <div class=\"card\">
            <h2>Add Student</h2>
            <form method=\"POST\">
                <label>Student ID</label>
                <input type=\"text\" name=\"student_id\" placeholder=\"e.g. 2026-0001\" required>

                <label>Full Name</label>
                <input type=\"text\" name=\"full_name\" placeholder=\"Enter full name\" required>

                <label>Grade / Section</label>
                <input type=\"text\" name=\"grade_section\" placeholder=\"e.g. Grade 10 - Rizal\" required>

                <button type=\"submit\">Add Student</button>
            </form>
        </div>

        <div class=\"card\">
            <h2>Student List</h2>
            <table>
                <thead>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Grade / Section</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>{student_rows}</tbody>
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
# Attendance
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
        teacher_id = session.get("teacher_id")
        students = conn.execute("SELECT * FROM students ORDER BY full_name ASC").fetchall()

        for student in students:
            status = request.form.get(f"status_{student['id']}", "Absent")
            remarks = request.form.get(f"remarks_{student['id']}", "").strip()

            existing = conn.execute(
                "SELECT id FROM attendance WHERE student_id = ? AND attendance_date = ?",
                (student["id"], selected_date)
            ).fetchone()

            if existing:
                conn.execute(
                    "UPDATE attendance SET status = ?, remarks = ?, marked_by = ? WHERE student_id = ? AND attendance_date = ?",
                    (status, remarks, teacher_id, student["id"], selected_date)
                )
            else:
                conn.execute(
                    "INSERT INTO attendance (student_id, attendance_date, status, remarks, marked_by) VALUES (?, ?, ?, ?, ?)",
                    (student["id"], selected_date, status, remarks, teacher_id)
                )

        conn.commit()
        flash(f"Attendance saved for {selected_date}.")

    students = conn.execute("SELECT * FROM students ORDER BY full_name ASC").fetchall()
    attendance_map = {}
    existing_records = conn.execute(
        "SELECT * FROM attendance WHERE attendance_date = ?",
        (selected_date,)
    ).fetchall()
    for rec in existing_records:
        attendance_map[rec["student_id"]] = rec
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

    if not rows:
        rows = "<tr><td colspan='5'>No students found. Please add students first.</td></tr>"

    content = f"""
    <div class=\"card\">
        <h2>Mark Attendance</h2>
        <form method=\"POST\">
            <label>Select Date</label>
            <input type=\"date\" name=\"attendance_date\" value=\"{selected_date}\" required>

            <table>
                <thead>
                    <tr>
                        <th>Student ID</th>
                        <th>Name</th>
                        <th>Grade / Section</th>
                        <th>Status</th>
                        <th>Remarks</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <button type=\"submit\">Save Attendance</button>
        </form>
    </div>
    """
    return render_page("Attendance", content)


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
        SELECT a.attendance_date, a.status, a.remarks, s.student_id, s.full_name, s.grade_section
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.attendance_date = ?
        ORDER BY s.full_name ASC
        """,
        (report_date,)
    ).fetchall()
    conn.close()

    rows = "".join(
        f"<tr><td>{escape_html(r['student_id'])}</td><td>{escape_html(r['full_name'])}</td><td>{escape_html(r['grade_section'])}</td><td><span class='badge {'present' if r['status']=='Present' else 'late' if r['status']=='Late' else 'absent'}'>{escape_html(r['status'])}</span></td><td>{escape_html(r['remarks'] or '')}</td></tr>"
        for r in records
    )
    if not rows:
        rows = "<tr><td colspan='5'>No attendance records found for this date.</td></tr>"

    export_link = url_for('export_csv', report_date=report_date)

    content = f"""
    <div class=\"card\">
        <h2>Attendance Reports</h2>
        <form method=\"GET\">
            <label>Select Date</label>
            <input type=\"date\" name=\"report_date\" value=\"{report_date}\">
            <button type=\"submit\">View Report</button>
        </form>
        <a class=\"btn-link\" href=\"{export_link}\">Export CSV</a>
    </div>

    <div class=\"card\">
        <h3>Attendance Report for {report_date}</h3>
        <table>
            <thead>
                <tr>
                    <th>Student ID</th>
                    <th>Name</th>
                    <th>Grade / Section</th>
                    <th>Status</th>
                    <th>Remarks</th>
                </tr>
            </thead>
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
        SELECT a.attendance_date, s.student_id, s.full_name, s.grade_section, a.status, a.remarks
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
    writer.writerow(["Attendance Date", "Student ID", "Full Name", "Grade/Section", "Status", "Remarks"])
    for row in records:
        writer.writerow([
            row["attendance_date"],
            row["student_id"],
            row["full_name"],
            row["grade_section"],
            row["status"],
            row["remarks"] or ""
        ])

    memory_file = io.BytesIO()
    memory_file.write(output.getvalue().encode("utf-8"))
    memory_file.seek(0)
    output.close()

    filename = f"attendance_{report_date}.csv"
    return send_file(memory_file, mimetype="text/csv", as_attachment=True, download_name=filename)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
