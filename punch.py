from flask import Flask, render_template, request, jsonify, g
import sqlite3
from datetime import datetime, date, timedelta, timezone
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'duty.db')
DAILY_SECONDS = int(8.5 * 3600)  # 8.5 hours in seconds

app = Flask(__name__)
app.config['DATABASE'] = DB_PATH
app.config['SECRET_KEY'] = 'change-this-in-production'


# -------------------- DATABASE SETUP --------------------
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    cur = db.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS records (
            day TEXT PRIMARY KEY,
            seconds INTEGER DEFAULT 0
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_iso TEXT NOT NULL,
            end_iso TEXT NOT NULL,
            seconds INTEGER NOT NULL,
            day TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ongoing (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            start_iso TEXT NOT NULL
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    db.commit()


# -------------------- UTILITIES --------------------
def iso_now():
    """Return local timezone-aware ISO timestamp."""
    return datetime.now().astimezone().isoformat()


def parse_iso(iso):
    """Parse ISO string into tz-aware datetime."""
    dt = datetime.fromisoformat(iso)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def to_local_time_only(iso):
    if not iso:
        return None
    dt = parse_iso(iso).astimezone()
    return dt.strftime('%I:%M %p').lstrip('0')
    
    
def to_local_str(iso, fmt='%Y-%m-%d %H:%M:%S %Z'):
    if not iso:
        return None
    dt = parse_iso(iso).astimezone()
    return dt.strftime(fmt)


def seconds_to_hms(sec):
    sec = int(sec)
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}h {m}m {s}s"


def late_status(punch_in_iso, expected_hour=8, expected_min=0):
    if not punch_in_iso:
        return None

    dt = parse_iso(punch_in_iso).astimezone()
    expected = dt.replace(
        hour=expected_hour,
        minute=expected_min,
        second=0,
        microsecond=0
    )

    delay_minutes = int((dt - expected).total_seconds() / 60)

    if delay_minutes <= 0:
        return {"label": "On time", "level": "ok"}

    # ---- format delay nicely ----
    if delay_minutes < 60:
        delay_label = f"{delay_minutes}m"
    else:
        h = delay_minutes // 60
        m = delay_minutes % 60
        delay_label = f"{h}h {m}m" if m else f"{h}h"

    if delay_minutes <= 30:
        return {"label": f"Late ({delay_label})", "level": "warn"}
    else:
        return {"label": f"Very Late ({delay_label})", "level": "danger"}
            

def is_sunday_from_date_str(day_str):
    """Return True if the given date (YYYY-MM-DD) is a Sunday."""
    try:
        d = datetime.fromisoformat(day_str).date()
        # Monday=0 ... Sunday=6
        return d.weekday() == 6
    except Exception:
        return False


# -------------------- FLASK ROUTES --------------------
db_initialized = False


@app.before_request
def prepare():
    global db_initialized
    if not db_initialized:
        init_db()
        db_initialized = True


@app.route('/')
def index():
    db = get_db()
    today = date.today().isoformat()

    # ---- Today total seconds ----
    cur = db.execute('SELECT seconds FROM records WHERE day = ?', (today,))
    row = cur.fetchone()
    today_seconds = row['seconds'] if row else 0

    # ---- Ongoing session ----
    cur = db.execute('SELECT start_iso FROM ongoing WHERE id = 1')
    ongoing_row = cur.fetchone()
    ongoing_start = ongoing_row['start_iso'] if ongoing_row else None
    ongoing_start_local = to_local_str(ongoing_start) if ongoing_start else None

    # ---- History (last 30 days) ----
    cur = db.execute('SELECT day, seconds FROM records ORDER BY day DESC LIMIT 30')
    records = cur.fetchall()

    history = []

    for r in records:
        day = r['day']
        worked = r['seconds']

        # ---- Punch In & Punch Out (from sessions) ----
        cur2 = db.execute(
            '''
            SELECT
                MIN(start_iso) AS punch_in,
                MAX(end_iso)   AS punch_out
            FROM sessions
            WHERE day = ?
            ''',
            (day,)
        )
        srow = cur2.fetchone()

        punch_in = to_local_time_only(srow['punch_in']) if srow and srow['punch_in'] else None
        punch_out = to_local_time_only(srow['punch_out']) if srow and srow['punch_out'] else None
        late_info = late_status(srow['punch_in']) if srow and srow['punch_in'] else None
        
        # ---- Overtime calculation ----
        if is_sunday_from_date_str(day):
            overtime = worked
        else:
            overtime = max(0, worked - DAILY_SECONDS)

        history.append({
            'day': day,
            'worked': worked,
            'overtime': overtime,
            'seconds': worked,
            'punch_in': punch_in,
            'punch_out': punch_out,
            'late': late_info
        })

    return render_template(
        'index.html',
        today_seconds=today_seconds,
        today_overtime=(today_seconds if is_sunday_from_date_str(today)
                        else max(0, today_seconds - DAILY_SECONDS)),
        daily_seconds=DAILY_SECONDS,
        ongoing_start_local=ongoing_start_local,
        ongoing_start_iso=ongoing_start,
        seconds_to_hms=seconds_to_hms,
        history=history
    )


@app.route('/start', methods=['POST'])
def start():
    db = get_db()
    cur = db.execute('SELECT start_iso FROM ongoing WHERE id = 1')
    if cur.fetchone():
        return jsonify({'ok': False, 'error': 'Already started'}), 400
    start_iso = iso_now()
    db.execute('INSERT OR REPLACE INTO ongoing (id, start_iso) VALUES (1, ?)', (start_iso,))
    db.commit()
    return jsonify({'ok': True, 'start_iso': start_iso, 'start_local': to_local_str(start_iso)})


@app.route('/done', methods=['POST'])
def done():
    db = get_db()
    cur = db.execute('SELECT start_iso FROM ongoing WHERE id = 1')
    row = cur.fetchone()
    if not row:
        return jsonify({'ok': False, 'error': 'No ongoing session'}), 400

    start_iso = row['start_iso']
    start_dt = parse_iso(start_iso)
    end_dt = datetime.now().astimezone()
    delta = end_dt - start_dt
    seconds = int(delta.total_seconds())
    day = start_dt.astimezone().date().isoformat()

    # update daily record
    cur = db.execute('SELECT seconds FROM records WHERE day = ?', (day,))
    existing = cur.fetchone()
    if existing:
        new_seconds = existing['seconds'] + seconds
        db.execute('UPDATE records SET seconds = ? WHERE day = ?', (new_seconds, day))
    else:
        db.execute('INSERT INTO records (day, seconds) VALUES (?, ?)', (day, seconds))

    # add session
    db.execute(
        'INSERT INTO sessions (start_iso, end_iso, seconds, day) VALUES (?, ?, ?, ?)',
        (start_iso, end_dt.isoformat(), seconds, day)
    )
    db.execute('DELETE FROM ongoing WHERE id = 1')
    db.commit()

    # get total and compute overtime (Sunday = full)
    cur = db.execute('SELECT seconds FROM records WHERE day = ?', (day,))
    total_seconds = cur.fetchone()['seconds']

    if is_sunday_from_date_str(day):
        overtime_amount = total_seconds
    else:
        overtime_amount = max(0, total_seconds - DAILY_SECONDS)

    return jsonify({
        'ok': True,
        'seconds': seconds,
        'total_seconds': total_seconds,
        'overtime': overtime_amount,
        'start_local': to_local_str(start_iso),
        'end_local': to_local_str(end_dt.isoformat())
    })


@app.route('/reset', methods=['POST'])
def reset_all():
    db = get_db()
    db.execute('DELETE FROM sessions')
    db.execute('DELETE FROM records')
    db.execute('DELETE FROM ongoing')
    db.commit()
    return jsonify({'ok': True})


@app.route('/history')
def history():
    db = get_db()
    cur = db.execute('SELECT id, start_iso, end_iso, seconds, day FROM sessions ORDER BY id DESC LIMIT 200')
    sessions = cur.fetchall()
    out = []
    for s in sessions:
        out.append({
            'id': s['id'],
            'start_iso': s['start_iso'],
            'end_iso': s['end_iso'],
            'start_local': to_local_str(s['start_iso']),
            'end_local': to_local_str(s['end_iso']),
            'seconds': s['seconds'],
            'day': s['day']
        })
    return jsonify(out)


@app.route('/overtime_total')
def overtime_total():
    db = get_db()
    day = request.args.get('day')
    if day:
        cur = db.execute('SELECT seconds FROM records WHERE day = ?', (day,))
        row = cur.fetchone()
        seconds = row['seconds'] if row else 0
        if is_sunday_from_date_str(day):
            overtime = seconds
        else:
            overtime = max(0, seconds - DAILY_SECONDS)
        return jsonify({'day': day, 'seconds': seconds, 'overtime': overtime})
    else:
        # total overtime with Sunday rule
        cur = db.execute('SELECT day, seconds FROM records')
        rows = cur.fetchall()
        total_ot = 0
        for r in rows:
            day_str = r['day']
            secs = r['seconds']
            if is_sunday_from_date_str(day_str):
                total_ot += secs
            else:
                total_ot += max(0, secs - DAILY_SECONDS)
        return jsonify({'total_overtime_seconds': total_ot})

@app.route('/is_on_duty')
def is_on_duty():
    db = get_db()
    cur = db.execute("SELECT start_iso FROM ongoing WHERE id = 1")
    row = cur.fetchone()
    return jsonify({"on_duty": bool(row)})
        
@app.route('/has_history')
def has_history():
    db = get_db()
    cur = db.execute("SELECT COUNT(*) AS c FROM records")
    row = cur.fetchone()
    return jsonify({"has_history": row["c"] > 0})
        
@app.route('/overtime_earnings')
def overtime_earnings():
    """
    Query params:
      - rate : hourly rate (float). Required.
      - day  : optional, YYYY-MM-DD to get only that day.
    Returns JSON:
      { "rows": [{day, overtime_seconds, overtime_hours, earning}], "total_earning": float }
    """
    db = get_db()
    rate_str = request.args.get('rate', None)
    if rate_str is None:
        return jsonify({"error": "Missing rate parameter"}), 400
    try:
        rate = float(rate_str)
    except ValueError:
        return jsonify({"error": "Invalid rate parameter"}), 400

    day = request.args.get('day')

    rows = []
    total_earning = 0.0

    if day:
        cur = db.execute('SELECT seconds FROM records WHERE day = ?', (day,))
        r = cur.fetchone()
        secs = r['seconds'] if r else 0
        if is_sunday_from_date_str(day):
            ot_secs = secs
        else:
            ot_secs = max(0, secs - DAILY_SECONDS)
        ot_hours = ot_secs / 3600.0
        earning = round(ot_hours * rate, 2)
        rows.append({
            "day": day,
            "overtime_seconds": ot_secs,
            "overtime_hours": round(ot_hours, 4),
            "earning": earning
        })
        total_earning = earning
    else:
        cur = db.execute('SELECT day, seconds FROM records ORDER BY day DESC LIMIT 30')
        allrows = cur.fetchall()
        for r in allrows:
            day_str = r['day']
            secs = r['seconds']
            if is_sunday_from_date_str(day_str):
                ot_secs = secs
            else:
                ot_secs = max(0, secs - DAILY_SECONDS)
            ot_hours = ot_secs / 3600.0
            earning = round(ot_hours * rate, 2)
            rows.append({
                "day": day_str,
                "overtime_seconds": ot_secs,
                "overtime_hours": round(ot_hours, 4),
                "earning": earning
            })
            total_earning += earning

    total_earning = round(total_earning, 2)
    return jsonify({"rows": rows, "total_earning": total_earning})
        
@app.route('/overtime_from_salary')
def overtime_from_salary():
    db = get_db()
    salary_str = request.args.get('salary')
    if not salary_str:
        return jsonify({"error": "Missing salary parameter"}), 400
    try:
        salary = float(salary_str)
    except ValueError:
        return jsonify({"error": "Invalid salary"}), 400

    # optional params
    day = request.args.get('day')
    days_limit = int(request.args.get('days', 30))
    working_days_per_month = int(request.args.get('wdpm', 26))  # change if you prefer 22

    # compute hourly rate and OT rate (130% of hourly)
    monthly_hours = 8 * working_days_per_month
    hourly_rate = salary / monthly_hours if monthly_hours > 0 else 0.0
    ot_rate_hour = round(1.3 * hourly_rate, 2)

    rows = []
    total_earning = 0.0

    if day:
        cur = db.execute('SELECT seconds FROM records WHERE day = ?', (day,))
        r = cur.fetchone()
        secs = r['seconds'] if r else 0
        if is_sunday_from_date_str(day):
            ot_secs = secs
        else:
            ot_secs = max(0, secs - DAILY_SECONDS)
        ot_hours = ot_secs / 3600.0
        earning = round(ot_hours * ot_rate_hour, 2)
        rows.append({
            "day": day,
            "overtime_seconds": ot_secs,
            "overtime_hours": round(ot_hours,4),
            "earning": earning
        })
        total_earning = earning
    else:
        cur = db.execute('SELECT day, seconds FROM records ORDER BY day DESC LIMIT ?', (days_limit,))
        allrows = cur.fetchall()
        for r in allrows:
            day_str = r['day']
            secs = r['seconds']
            if is_sunday_from_date_str(day_str):
                ot_secs = secs
            else:
                ot_secs = max(0, secs - DAILY_SECONDS)
            ot_hours = ot_secs / 3600.0
            earning = round(ot_hours * ot_rate_hour, 2)
            rows.append({
                "day": day_str,
                "overtime_seconds": ot_secs,
                "overtime_hours": round(ot_hours,4),
                "earning": earning
            })
            total_earning += earning

    total_earning = round(total_earning, 2)
    return jsonify({
        "rows": rows,
        "total_earning": total_earning,
        "ot_rate_hour": ot_rate_hour,
        "hourly_rate": round(hourly_rate,2),
        "monthly_hours_used": monthly_hours
    })
    
@app.route('/get_salary')
def get_salary():
    """
    Returns the stored monthly salary if present:
      { has_salary: bool, salary: float or null }
    """
    db = get_db()
    cur = db.execute("SELECT value FROM settings WHERE key = 'salary'")
    row = cur.fetchone()
    if not row:
        return jsonify({"has_salary": False, "salary": None})
    try:
        s = float(row['value'])
    except Exception:
        return jsonify({"has_salary": False, "salary": None})
    return jsonify({"has_salary": True, "salary": round(s, 2)})


@app.route('/set_salary', methods=['POST'])
def set_salary():
    """
    JSON body: { salary: 13000 }
    Stores salary as string in settings and returns success.
    """
    data = {}
    try:
        data = request.get_json() or {}
    except Exception:
        return jsonify({"ok": False, "error": "Invalid JSON"}), 400

    if 'salary' not in data:
        return jsonify({"ok": False, "error": "Missing salary"}), 400
    try:
        salary = float(data['salary'])
    except Exception:
        return jsonify({"ok": False, "error": "Invalid salary"}), 400

    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('salary', ?)", (str(salary),))
    db.commit()
    return jsonify({"ok": True, "salary": round(salary, 2)})
        



if __name__ == '__main__':
    app.run(host="0.0.0.0")