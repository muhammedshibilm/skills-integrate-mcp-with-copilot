"""Mergington High School extracurricular activities API."""

import os
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Mergington High School API",
    description="API for viewing and signing up for extracurricular activities",
)

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount(
    "/static",
    StaticFiles(directory=os.path.join(Path(__file__).parent, "static")),
    name="static",
)

DB_PATH = current_dir / "activities.db"

DEFAULT_ACTIVITIES: dict[str, dict[str, Any]] = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"],
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"],
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"],
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"],
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"],
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"],
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"],
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"],
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"],
    },
}


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_user(conn: sqlite3.Connection, email: str) -> None:
    name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
    conn.execute(
        """
        INSERT OR IGNORE INTO students(email, name, grade_level)
        VALUES (?, ?, ?)
        """,
        (email, name, None),
    )


def seed_default_data(conn: sqlite3.Connection) -> None:
    activity_count = conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    if activity_count > 0:
        return

    for name, details in DEFAULT_ACTIVITIES.items():
        conn.execute(
            """
            INSERT INTO activities(name, description, schedule, max_participants)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                details["description"],
                details["schedule"],
                details["max_participants"],
            ),
        )
        for participant_email in details["participants"]:
            ensure_user(conn, participant_email)
            conn.execute(
                """
                INSERT INTO enrollments(activity_name, student_email)
                VALUES (?, ?)
                """,
                (name, participant_email),
            )


def init_db() -> None:
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                email TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                grade_level INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS activities (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                schedule TEXT NOT NULL,
                max_participants INTEGER NOT NULL CHECK(max_participants > 0)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                activity_name TEXT NOT NULL,
                student_email TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(activity_name, student_email),
                FOREIGN KEY(activity_name) REFERENCES activities(name) ON DELETE CASCADE,
                FOREIGN KEY(student_email) REFERENCES students(email) ON DELETE CASCADE
            )
            """
        )
        seed_default_data(conn)
        conn.commit()


@app.on_event("startup")
def startup_event() -> None:
    init_db()


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                a.name,
                a.description,
                a.schedule,
                a.max_participants,
                COALESCE(GROUP_CONCAT(e.student_email), '') AS participant_emails
            FROM activities a
            LEFT JOIN enrollments e ON e.activity_name = a.name
            GROUP BY a.name
            ORDER BY a.name
            """
        ).fetchall()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        participants = (
            row["participant_emails"].split(",") if row["participant_emails"] else []
        )
        result[row["name"]] = {
            "description": row["description"],
            "schedule": row["schedule"],
            "max_participants": row["max_participants"],
            "participants": participants,
        }
    return result


@app.get("/students")
def get_students():
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT email, name, grade_level
            FROM students
            ORDER BY email
            """
        ).fetchall()
    return [dict(row) for row in rows]


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    with get_db_connection() as conn:
        activity = conn.execute(
            """
            SELECT name, max_participants
            FROM activities
            WHERE name = ?
            """,
            (activity_name,),
        ).fetchone()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        already_signed_up = conn.execute(
            """
            SELECT 1
            FROM enrollments
            WHERE activity_name = ? AND student_email = ?
            """,
            (activity_name, email),
        ).fetchone()
        if already_signed_up:
            raise HTTPException(status_code=400, detail="Student is already signed up")

        participant_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM enrollments
            WHERE activity_name = ?
            """,
            (activity_name,),
        ).fetchone()[0]
        if participant_count >= activity["max_participants"]:
            raise HTTPException(status_code=400, detail="No spots left in this activity")

        ensure_user(conn, email)
        conn.execute(
            """
            INSERT INTO enrollments(activity_name, student_email)
            VALUES (?, ?)
            """,
            (activity_name, email),
        )
        conn.commit()

    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    with get_db_connection() as conn:
        activity = conn.execute(
            """
            SELECT name
            FROM activities
            WHERE name = ?
            """,
            (activity_name,),
        ).fetchone()
        if not activity:
            raise HTTPException(status_code=404, detail="Activity not found")

        enrollment = conn.execute(
            """
            SELECT id
            FROM enrollments
            WHERE activity_name = ? AND student_email = ?
            """,
            (activity_name, email),
        ).fetchone()
        if not enrollment:
            raise HTTPException(
                status_code=400,
                detail="Student is not signed up for this activity",
            )

        conn.execute(
            """
            DELETE FROM enrollments
            WHERE activity_name = ? AND student_email = ?
            """,
            (activity_name, email),
        )
        conn.commit()

    return {"message": f"Unregistered {email} from {activity_name}"}
