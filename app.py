from flask import Flask, render_template, request
import sqlite3
from datetime import datetime, timedelta
import uuid
import qrcode
import os
import math

app = Flask(__name__)

SUBJECTS = [
    "ML", "EOII", "IPR", "DS", "CD", "OE-I",
    "PSL-Lab", "H/W-Lab", "CD-Lab",
    "Expert Session", "Seminar"
]

def get_db():
    return sqlite3.connect("attendance.db")

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("CREATE TABLE IF NOT EXISTS students (roll_no TEXT PRIMARY KEY, name TEXT, branch TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS sessions (session_id TEXT, subject TEXT, start_time TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS attendance (student_id TEXT, session_id TEXT, time TEXT)")

    conn.commit()
    conn.close()

init_db()

def is_valid(start_time):
    now = datetime.now()
    start = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    return now - start <= timedelta(minutes=5)

def is_in_classroom(lat1, lon1):
    class_lat = 21.1458
    class_lon = 79.0882
    distance = math.sqrt((lat1 - class_lat)**2 + (lon1 - class_lon)**2)
    return distance < 0.01

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/create_session', methods=['GET','POST'])
def create_session():
    if request.method == 'POST':
        subject = request.form['subject']

        session_id = str(uuid.uuid4())[:6]
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO sessions VALUES (?, ?, ?)", (session_id, subject, time))
        conn.commit()
        conn.close()

        if not os.path.exists("static"):
            os.makedirs("static")

        img = qrcode.make(session_id)
        img.save(f"static/{session_id}.png")

        return render_template("session.html", session_id=session_id)

    return render_template("create_session.html", subjects=SUBJECTS)

@app.route('/scan')
def scan():
    return render_template("scan.html")

@app.route('/mark', methods=['POST'])
def mark():
    student_id = request.form['student_id']
    session_id = request.form['session_id']

    lat = request.form.get('lat')
    lon = request.form.get('lon')

    if not lat or not lon:
        return "Location not allowed"

    lat = float(lat)
    lon = float(lon)

    if not is_in_classroom(lat, lon):
        return "You are not in classroom"

    conn = get_db()
    c = conn.cursor()

    c.execute("SELECT start_time FROM sessions WHERE session_id=?", (session_id,))
    result = c.fetchone()

    if not result:
        return "Invalid Session"

    if not is_valid(result[0]):
        return "Session Expired"

    c.execute("SELECT * FROM attendance WHERE student_id=? AND session_id=?", (student_id, session_id))
    if c.fetchone():
        return "Already Marked"

    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO attendance VALUES (?, ?, ?)", (student_id, session_id, time))

    conn.commit()
    conn.close()

    return "Attendance Marked Successfully"

@app.route('/attendance')
def attendance():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    SELECT s.roll_no, s.name, s.branch, se.subject, a.time
    FROM attendance a
    JOIN students s ON a.student_id = s.roll_no
    JOIN sessions se ON a.session_id = se.session_id
    """)

    data = c.fetchall()
    conn.close()
    return render_template("attendance.html", data=data)

@app.route('/add_student', methods=['GET','POST'])
def add_student():
    if request.method == 'POST':
        roll = request.form['roll']
        name = request.form['name']
        branch = request.form['branch']

        conn = get_db()
        c = conn.cursor()
        c.execute("INSERT INTO students VALUES (?, ?, ?)", (roll, name, branch))
        conn.commit()
        conn.close()

        return "Student Added"

    return render_template("add_student.html")

@app.route('/students_report', methods=['GET','POST'])
def students_report():
    conn = get_db()
    c = conn.cursor()

    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    filter_type = request.form.get('filter')

    query = """
    SELECT s.roll_no, s.name, s.branch, COUNT(a.student_id)
    FROM students s
    LEFT JOIN attendance a ON s.roll_no = a.student_id
    """

    if start_date and end_date:
        query += " WHERE date(a.time) BETWEEN ? AND ? GROUP BY s.roll_no"
        c.execute(query, (start_date, end_date))
    else:
        query += " GROUP BY s.roll_no"
        c.execute(query)

    data = c.fetchall()

    final = []
    for row in data:
        roll, name, branch, total = row
        percent = (total / 30) * 100 if total else 0

        if filter_type == "above" and percent < 75:
            continue
        if filter_type == "below" and percent >= 75:
            continue

        final.append((roll, name, branch, total, round(percent,2)))

    conn.close()
    return render_template("students_report.html", data=final)

@app.route('/subject_details')
def subject_details():
    return render_template("subject_details.html")

@app.route('/about')
def about():
    return render_template("about.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)