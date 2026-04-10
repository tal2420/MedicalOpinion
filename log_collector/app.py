"""
Log Collector Server - Receives, stores, and displays logs from MedicalOpinion installations.

Run with: python app.py
Dashboard at: http://localhost:5600
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, g

app = Flask(__name__)
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.db"))


# ─── Database ───────────────────────────────────────────────────────────

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db:
        db.close()


def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS installations (
            id TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            app_version TEXT DEFAULT '',
            os TEXT DEFAULT '',
            os_version TEXT DEFAULT '',
            python_version TEXT DEFAULT '',
            architecture TEXT DEFAULT '',
            is_frozen INTEGER DEFAULT 0,
            config_summary TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            installation_id TEXT NOT NULL,
            event_name TEXT NOT NULL,
            properties TEXT DEFAULT '{}',
            event_timestamp TEXT NOT NULL,
            received_at TEXT NOT NULL,
            FOREIGN KEY (installation_id) REFERENCES installations(id)
        );

        CREATE TABLE IF NOT EXISTS diagnostics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            installation_id TEXT NOT NULL,
            received_at TEXT NOT NULL,
            system_info TEXT DEFAULT '{}',
            config_summary TEXT DEFAULT '{}',
            log_text TEXT DEFAULT '',
            events_snapshot TEXT DEFAULT '[]',
            FOREIGN KEY (installation_id) REFERENCES installations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_events_installation ON events(installation_id);
        CREATE INDEX IF NOT EXISTS idx_events_name ON events(event_name);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(event_timestamp);
        CREATE INDEX IF NOT EXISTS idx_diagnostics_installation ON diagnostics(installation_id);
        CREATE INDEX IF NOT EXISTS idx_diagnostics_received ON diagnostics(received_at);
    """)
    conn.commit()
    conn.close()


def _upsert_installation(db, installation_id, system_info, config_summary=None):
    """Insert or update installation record."""
    now = datetime.now().isoformat()
    existing = db.execute(
        "SELECT id FROM installations WHERE id = ?", (installation_id,)
    ).fetchone()

    if existing:
        db.execute("""
            UPDATE installations SET
                last_seen = ?,
                app_version = ?,
                os = ?,
                os_version = ?,
                python_version = ?,
                architecture = ?,
                is_frozen = ?,
                config_summary = ?
            WHERE id = ?
        """, (
            now,
            system_info.get("app_version", ""),
            system_info.get("os", ""),
            system_info.get("os_version", ""),
            system_info.get("python_version", ""),
            system_info.get("architecture", ""),
            1 if system_info.get("is_frozen") else 0,
            json.dumps(config_summary or {}, ensure_ascii=False),
            installation_id,
        ))
    else:
        db.execute("""
            INSERT INTO installations (id, first_seen, last_seen, app_version, os, os_version, python_version, architecture, is_frozen, config_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            installation_id, now, now,
            system_info.get("app_version", ""),
            system_info.get("os", ""),
            system_info.get("os_version", ""),
            system_info.get("python_version", ""),
            system_info.get("architecture", ""),
            1 if system_info.get("is_frozen") else 0,
            json.dumps(config_summary or {}, ensure_ascii=False),
        ))


# ─── Collection Endpoints ───────────────────────────────────────────────

@app.route("/api/collect/events", methods=["POST"])
def collect_events():
    """Receive usage events from an installation."""
    data = request.get_json(force=True)
    installation_id = data.get("installation_id", "unknown")
    system_info = data.get("system", {})
    events = data.get("events", [])

    db = get_db()
    _upsert_installation(db, installation_id, system_info)

    now = datetime.now().isoformat()
    for ev in events:
        db.execute("""
            INSERT INTO events (installation_id, event_name, properties, event_timestamp, received_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            installation_id,
            ev.get("event", "unknown"),
            json.dumps(ev.get("properties", {}), ensure_ascii=False),
            ev.get("timestamp", now),
            now,
        ))

    db.commit()
    return jsonify({"ok": True, "received": len(events)})


@app.route("/api/collect/diagnostic", methods=["POST"])
def collect_diagnostic():
    """Receive a full diagnostic bundle."""
    data = request.get_json(force=True)
    installation_id = data.get("installation_id", "unknown")
    system_info = data.get("system", {})
    config_summary = data.get("config_summary", {})
    log_text = data.get("log", "")
    events_snapshot = data.get("events", [])

    db = get_db()
    _upsert_installation(db, installation_id, system_info, config_summary)

    now = datetime.now().isoformat()

    # Store events from the snapshot
    for ev in events_snapshot:
        db.execute("""
            INSERT INTO events (installation_id, event_name, properties, event_timestamp, received_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            installation_id,
            ev.get("event", "unknown"),
            json.dumps(ev.get("properties", {}), ensure_ascii=False),
            ev.get("timestamp", now),
            now,
        ))

    # Store diagnostic bundle
    db.execute("""
        INSERT INTO diagnostics (installation_id, received_at, system_info, config_summary, log_text, events_snapshot)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        installation_id,
        now,
        json.dumps(system_info, ensure_ascii=False),
        json.dumps(config_summary, ensure_ascii=False),
        log_text,
        json.dumps(events_snapshot, ensure_ascii=False),
    ))

    db.commit()
    return jsonify({"ok": True, "diagnostic_id": db.execute("SELECT last_insert_rowid()").fetchone()[0]})


# ─── Dashboard API ──────────────────────────────────────────────────────

@app.route("/api/dashboard/summary")
def api_summary():
    """High-level stats for the dashboard."""
    db = get_db()

    total_installations = db.execute("SELECT COUNT(*) FROM installations").fetchone()[0]

    # Active in last 7 days
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    active_7d = db.execute(
        "SELECT COUNT(*) FROM installations WHERE last_seen > ?", (week_ago,)
    ).fetchone()[0]

    total_events = db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    total_diagnostics = db.execute("SELECT COUNT(*) FROM diagnostics").fetchone()[0]

    # Error count in last 24h
    day_ago = (datetime.now() - timedelta(days=1)).isoformat()
    recent_errors = db.execute(
        "SELECT COUNT(*) FROM events WHERE event_name LIKE '%error%' AND event_timestamp > ?",
        (day_ago,)
    ).fetchone()[0]

    return jsonify({
        "total_installations": total_installations,
        "active_7d": active_7d,
        "total_events": total_events,
        "total_diagnostics": total_diagnostics,
        "recent_errors": recent_errors,
    })


@app.route("/api/dashboard/installations")
def api_installations():
    """List all installations."""
    db = get_db()
    rows = db.execute("""
        SELECT i.*,
               (SELECT COUNT(*) FROM events e WHERE e.installation_id = i.id) as event_count,
               (SELECT COUNT(*) FROM diagnostics d WHERE d.installation_id = i.id) as diagnostic_count
        FROM installations i
        ORDER BY i.last_seen DESC
    """).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/api/dashboard/events")
def api_events():
    """List events with optional filters."""
    installation_id = request.args.get("installation_id")
    event_name = request.args.get("event_name")
    days = int(request.args.get("days", 7))
    limit = min(int(request.args.get("limit", 200)), 1000)

    since = (datetime.now() - timedelta(days=days)).isoformat()

    query = "SELECT * FROM events WHERE event_timestamp > ?"
    params = [since]

    if installation_id:
        query += " AND installation_id = ?"
        params.append(installation_id)
    if event_name:
        query += " AND event_name LIKE ?"
        params.append(f"%{event_name}%")

    query += " ORDER BY event_timestamp DESC LIMIT ?"
    params.append(limit)

    rows = get_db().execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/dashboard/event-stats")
def api_event_stats():
    """Aggregate event counts by name."""
    days = int(request.args.get("days", 30))
    since = (datetime.now() - timedelta(days=days)).isoformat()

    rows = get_db().execute("""
        SELECT event_name, COUNT(*) as count
        FROM events
        WHERE event_timestamp > ?
        GROUP BY event_name
        ORDER BY count DESC
    """, (since,)).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/api/dashboard/diagnostics")
def api_diagnostics():
    """List diagnostic bundles."""
    installation_id = request.args.get("installation_id")
    limit = min(int(request.args.get("limit", 50)), 200)

    if installation_id:
        rows = get_db().execute(
            "SELECT id, installation_id, received_at, system_info, config_summary FROM diagnostics WHERE installation_id = ? ORDER BY received_at DESC LIMIT ?",
            (installation_id, limit)
        ).fetchall()
    else:
        rows = get_db().execute(
            "SELECT id, installation_id, received_at, system_info, config_summary FROM diagnostics ORDER BY received_at DESC LIMIT ?",
            (limit,)
        ).fetchall()

    return jsonify([dict(r) for r in rows])


@app.route("/api/dashboard/diagnostics/<int:diag_id>")
def api_diagnostic_detail(diag_id):
    """Get full diagnostic bundle including log text."""
    row = get_db().execute(
        "SELECT * FROM diagnostics WHERE id = ?", (diag_id,)
    ).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(row))


@app.route("/api/dashboard/errors")
def api_errors():
    """Extract ERROR lines from recent diagnostic logs."""
    days = int(request.args.get("days", 7))
    limit = int(request.args.get("limit", 50))

    since = (datetime.now() - timedelta(days=days)).isoformat()
    rows = get_db().execute("""
        SELECT id, installation_id, received_at, log_text
        FROM diagnostics
        WHERE received_at > ?
        ORDER BY received_at DESC
        LIMIT ?
    """, (since, limit)).fetchall()

    errors = []
    for row in rows:
        log_text = row["log_text"] or ""
        for line in log_text.split("\n"):
            if "[ERROR]" in line or "[WARN]" in line:
                errors.append({
                    "diagnostic_id": row["id"],
                    "installation_id": row["installation_id"],
                    "received_at": row["received_at"],
                    "line": line.strip(),
                })

    return jsonify(errors[:200])


@app.route("/api/dashboard/timeline")
def api_timeline():
    """Daily event counts for charting."""
    days = int(request.args.get("days", 30))
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    rows = get_db().execute("""
        SELECT DATE(event_timestamp) as day, COUNT(*) as count
        FROM events
        WHERE DATE(event_timestamp) >= ?
        GROUP BY day
        ORDER BY day
    """, (since,)).fetchall()

    return jsonify([dict(r) for r in rows])


# ─── Dashboard Pages ────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# ─── Main ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("COLLECTOR_PORT", 5600))
    print(f"Log Collector running at http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
