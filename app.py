from datetime import datetime
from functools import wraps
import json
import os
from pathlib import Path
import sqlite3
from time import perf_counter, sleep

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, session, stream_with_context, url_for
import requests
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("HEARTFOG_SECRET_KEY", "heartfog-master-demo-key")

WORKERS = [
    "http://192.168.1.72:5001",
    "http://192.168.1.94:5002",
    "https://ravinautiyal08-heart.hf.space/"

]
DATABASE = Path(__file__).with_name("master_records.db")
DOCTOR_USERNAME = os.environ.get("HEARTFOG_DOCTOR_USERNAME", "doctor")
DOCTOR_NAME = os.environ.get("HEARTFOG_DOCTOR_NAME", "Doctor")
DOCTOR_PASSWORD_HASH = os.environ.get(
    "HEARTFOG_DOCTOR_PASSWORD_HASH",
    generate_password_hash(os.environ.get("HEARTFOG_DOCTOR_PASSWORD", "heartfog")),
)
CLINICAL_FIELDS = (
    "age",
    "sex",
    "cp",
    "trestbps",
    "chol",
    "fbs",
    "restecg",
    "thalch",
    "exang",
    "oldpeak",
    "slope",
    "ca",
    "thal",
)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("doctor"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_username(username):
    return username.strip().lower()


def valid_username(username):
    return 3 <= len(username) <= 40 and all(
        character.isalnum() or character in "._-" for character in username
    )


def init_db():
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS doctor_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS patient_records (
                patient_id TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                age TEXT NOT NULL,
                phone TEXT,
                sex TEXT NOT NULL,
                cp TEXT NOT NULL,
                trestbps TEXT NOT NULL,
                chol TEXT NOT NULL,
                fbs TEXT NOT NULL,
                restecg TEXT NOT NULL,
                thalch TEXT NOT NULL,
                exang TEXT NOT NULL,
                oldpeak TEXT NOT NULL,
                slope TEXT NOT NULL,
                ca TEXT NOT NULL,
                thal TEXT NOT NULL,
                doctor_notes TEXT,
                last_result TEXT,
                last_probability REAL,
                last_worker TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS route_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT,
                worker TEXT NOT NULL,
                event TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms REAL,
                detail TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO doctor_accounts (
                full_name, username, password_hash, created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                DOCTOR_NAME.strip() or "Doctor",
                normalize_username(DOCTOR_USERNAME) or "doctor",
                DOCTOR_PASSWORD_HASH,
                now_text(),
            ),
        )


def doctor_account(username):
    with get_db() as connection:
        return connection.execute(
            """
            SELECT full_name, username, password_hash
            FROM doctor_accounts
            WHERE username = ?
            """,
            (normalize_username(username),),
        ).fetchone()


def sign_in_doctor(account):
    session.clear()
    session["doctor"] = account["username"]
    session["doctor_name"] = account["full_name"]


def log_route_event(patient_id, worker, event, status, latency_ms=None, detail=None):
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO route_events (
                patient_id, worker, event, status, latency_ms, detail, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (patient_id, worker, event, status, latency_ms, detail, now_text()),
        )


def worker_prediction_count(worker):
    with get_db() as connection:
        row = connection.execute(
            """
            SELECT COUNT(*) AS total
            FROM route_events
            WHERE worker = ? AND event = 'predict' AND status = 'success'
            """,
            (worker,),
        ).fetchone()
    return row["total"]


def get_worker_status(worker, timeout=1):
    checked_at = now_text()
    started = perf_counter()
    try:
        response = requests.get(f"{worker}/load", timeout=timeout)
        response.raise_for_status()
        load_data = response.json()
        return {
            "address": worker,
            "available": True,
            "load": float(load_data["load"]),
            "active_requests": load_data.get("active_requests"),
            "latency_ms": round((perf_counter() - started) * 1000, 1),
            "heartbeat": load_data.get("heartbeat", checked_at),
            "served": load_data.get("predictions_served", worker_prediction_count(worker)),
            "probe": "load",
        }
    except (requests.RequestException, KeyError, TypeError, ValueError):
        pass

    started = perf_counter()
    try:
        response = requests.options(f"{worker}/predict", timeout=timeout)
        response.raise_for_status()
        return {
            "address": worker,
            "available": True,
            "load": None,
            "active_requests": None,
            "latency_ms": round((perf_counter() - started) * 1000, 1),
            "heartbeat": checked_at,
            "served": worker_prediction_count(worker),
            "probe": "predict",
        }
    except requests.RequestException:
        return {
            "address": worker,
            "available": False,
            "load": None,
            "active_requests": None,
            "latency_ms": None,
            "heartbeat": checked_at,
            "served": worker_prediction_count(worker),
            "probe": "offline",
        }


def get_worker_statuses():
    return [get_worker_status(worker, timeout=1) for worker in WORKERS]


def recent_records():
    with get_db() as connection:
        return connection.execute(
            """
            SELECT patient_id, full_name, updated_at, last_result, last_probability
            FROM patient_records
            ORDER BY updated_at DESC
            LIMIT 6
            """
        ).fetchall()


def recent_route_events(limit=8):
    with get_db() as connection:
        return connection.execute(
            """
            SELECT patient_id, worker, event, status, latency_ms, created_at
            FROM route_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()


def dashboard_page(form_data=None, prediction=None, workers=None):
    form_data = form_data or {}
    return render_template(
        "dashboard.html",
        doctor=session.get("doctor_name") or session.get("doctor"),
        form_data=form_data,
        prediction=prediction,
        records=recent_records(),
        workers=workers or get_worker_statuses(),
        route_events=recent_route_events(),
    )


def record_payload(form):
    return {key: form.get(key, "").strip() for key in form}


def save_record(payload, prediction=None):
    prediction = prediction or {}
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO patient_records (
                patient_id, full_name, age, phone, sex, cp, trestbps, chol, fbs,
                restecg, thalch, exang, oldpeak, slope, ca, thal, doctor_notes,
                last_result, last_probability, last_worker, updated_at
            )
            VALUES (
                :patient_id, :full_name, :age, :phone, :sex, :cp, :trestbps, :chol,
                :fbs, :restecg, :thalch, :exang, :oldpeak, :slope, :ca, :thal,
                :doctor_notes, :last_result, :last_probability, :last_worker, :updated_at
            )
            ON CONFLICT(patient_id) DO UPDATE SET
                full_name = excluded.full_name,
                age = excluded.age,
                phone = excluded.phone,
                sex = excluded.sex,
                cp = excluded.cp,
                trestbps = excluded.trestbps,
                chol = excluded.chol,
                fbs = excluded.fbs,
                restecg = excluded.restecg,
                thalch = excluded.thalch,
                exang = excluded.exang,
                oldpeak = excluded.oldpeak,
                slope = excluded.slope,
                ca = excluded.ca,
                thal = excluded.thal,
                doctor_notes = excluded.doctor_notes,
                last_result = COALESCE(excluded.last_result, patient_records.last_result),
                last_probability = COALESCE(
                    excluded.last_probability,
                    patient_records.last_probability
                ),
                last_worker = COALESCE(excluded.last_worker, patient_records.last_worker),
                updated_at = excluded.updated_at
            """,
            {
                **payload,
                "last_result": prediction.get("result"),
                "last_probability": prediction.get("probability"),
                "last_worker": prediction.get("worker"),
                "updated_at": updated_at,
            },
        )
def prediction_payload(payload):
    return {field: payload[field] for field in CLINICAL_FIELDS}


def submitted_worker_statuses(ready_workers):
    configured_ready_workers = {worker for worker in ready_workers if worker in WORKERS}
    return [
        {
            "address": worker,
            "available": worker in configured_ready_workers,
            "load": None,
            "active_requests": None,
            "latency_ms": None,
            "heartbeat": now_text(),
            "served": worker_prediction_count(worker),
            "probe": "displayed",
        }
        for worker in WORKERS
    ]


def predict_from_worker(payload, ready_workers=None):
    if ready_workers is None:
        statuses = [get_worker_status(worker) for worker in WORKERS]
    else:
        displayed_statuses = submitted_worker_statuses(ready_workers)
        statuses = [
            get_worker_status(status["address"])
            if status["available"]
            else status
            for status in displayed_statuses
        ]
    print("Worker statuses:", statuses)
    available_workers = [status for status in statuses if status["available"]]
    available_workers.sort(
        key=lambda status: (
            status["load"] if status["load"] is not None else float("inf"),
            status["latency_ms"] if status["latency_ms"] is not None else float("inf"),
        )
    )

    for status in available_workers:
        worker = status["address"]
        log_route_event(payload.get("patient_id"), worker, "route", "selected")
        try:
            print(f"Trying {worker}")
            started = perf_counter()
            response = requests.post(
                f"{worker}/predict",
                json=prediction_payload(payload),
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            latency_ms = round((perf_counter() - started) * 1000, 1)
            log_route_event(payload.get("patient_id"), worker, "predict", "success", latency_ms)
            return (
                {
                    "ok": True,
                    "result": data.get("result", "Prediction received"),
                    "probability": float(data.get("probability", 0)),
                    "worker": worker,
                    "latency_ms": latency_ms,
                },
                statuses,
            )
        except (requests.RequestException, TypeError, ValueError) as error:
            print(f"Worker failed: {worker}: {error}")
            log_route_event(payload.get("patient_id"), worker, "predict", "failed", detail=str(error))
            status["available"] = False
            status["load"] = None

    return (
        {
            "ok": False,
            "result": "All configured fog workers are unavailable.",
            "probability": None,
            "worker": None,
        },
        statuses,
    )


@app.route("/")
def home():
    if session.get("doctor"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("doctor"):
        return redirect(url_for("dashboard"))
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        account = doctor_account(username)
        if account and check_password_hash(account["password_hash"], password):
            sign_in_doctor(account)
            return redirect(url_for("dashboard"))
        flash("Login failed. Check the doctor username and password.", "error")
    return render_template("login.html", username=username)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if session.get("doctor"):
        return redirect(url_for("dashboard"))

    form_data = {"full_name": "", "username": ""}
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = normalize_username(request.form.get("username", ""))
        password = request.form.get("password", "")
        password_confirmation = request.form.get("password_confirmation", "")
        form_data = {"full_name": full_name, "username": username}

        if not full_name:
            flash("Enter the doctor's name.", "error")
        elif not valid_username(username):
            flash(
                "Use a 3 to 40 character username with letters, numbers, dots, dashes, or underscores.",
                "error",
            )
        elif len(password) < 8:
            flash("Create a password with at least 8 characters.", "error")
        elif password != password_confirmation:
            flash("Password confirmation does not match.", "error")
        else:
            try:
                with get_db() as connection:
                    connection.execute(
                        """
                        INSERT INTO doctor_accounts (
                            full_name, username, password_hash, created_at
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            full_name,
                            username,
                            generate_password_hash(password),
                            now_text(),
                        ),
                    )
            except sqlite3.IntegrityError:
                flash("That doctor username is already registered.", "error")
            else:
                sign_in_doctor({"full_name": full_name, "username": username})
                flash("Doctor account created. The dashboard is ready.", "success")
                return redirect(url_for("dashboard"))

    return render_template("signup.html", form_data=form_data)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    patient_id = request.args.get("patient_id", "").strip()
    form_data = {}
    if patient_id:
        with get_db() as connection:
            record = connection.execute(
                "SELECT * FROM patient_records WHERE patient_id = ?",
                (patient_id,),
            ).fetchone()
        if record:
            form_data = dict(record)
        else:
            flash("That patient record is not on this master node yet.", "error")
    return dashboard_page(form_data=form_data)


@app.route("/api/workers")
@login_required
def worker_status_api():
    return jsonify(worker_status_payload())


@app.route("/api/workers/stream")
@login_required
def worker_status_stream():
    def stream_statuses():
        while True:
            yield f"data: {json.dumps(worker_status_payload())}\n\n"
            sleep(2)

    response = Response(
        stream_with_context(stream_statuses()),
        mimetype="text/event-stream",
    )
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


def worker_status_payload():
    return {
        "workers": get_worker_statuses(),
        "checked_at": now_text(),
    }


@app.route("/records/save", methods=["POST"])
@login_required
def store_record():
    payload = record_payload(request.form)
    save_record(payload)
    flash("Patient record updated on the master node.", "success")
    return redirect(url_for("dashboard", patient_id=payload["patient_id"]))


@app.route("/predict", methods=["POST"])
@login_required
def predict():
    payload = record_payload(request.form)
    prediction, workers = predict_from_worker(
        payload,
        ready_workers=request.form.getlist("ready_workers"),
    )
    save_record(payload, prediction if prediction["ok"] else None)
    if prediction["ok"]:
        flash("Patient record updated and prediction returned.", "success")
    else:
        flash("Patient record updated. Prediction is waiting for an active worker.", "error")
    return dashboard_page(form_data=payload, prediction=prediction, workers=workers)

init_db()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)