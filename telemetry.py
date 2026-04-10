"""
Telemetry & Usage Analytics Module.

Collects two types of data:
1. **Usage events** - anonymized feature usage (which pages opened, imports done, etc.)
2. **Diagnostic bundle** - system info + recent logs for troubleshooting

Data is sent to a configurable collector endpoint.
No personally identifiable information is included.
"""

import os
import sys
import json
import platform
import uuid
import threading
from datetime import datetime

import applog


# ─── Installation ID (anonymous, persistent) ───────────────────────────

def _get_installation_id():
    """Return a persistent anonymous installation ID.

    Stored in app_settings.json next to the app binary.
    """
    app_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(app_dir, "app_settings.json")

    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            pass

    inst_id = settings.get("installation_id")
    if not inst_id:
        inst_id = str(uuid.uuid4())
        settings["installation_id"] = inst_id
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return inst_id


# ─── System Info ────────────────────────────────────────────────────────

def get_system_info():
    """Collect non-identifying system diagnostics."""
    try:
        from updater import get_current_version
        version = get_current_version()
    except Exception:
        version = "unknown"

    return {
        "app_version": version,
        "os": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "python_version": platform.python_version(),
        "architecture": platform.machine(),
        "is_frozen": getattr(sys, "frozen", False),
    }


# ─── Usage Events ──────────────────────────────────────────────────────

_events_buffer = []
_events_lock = threading.Lock()


def track_event(event_name, properties=None):
    """Record a usage event (buffered in memory).

    Args:
        event_name: e.g. "email_scan", "case_import", "page_view"
        properties: optional dict with event-specific data (no PII!)
    """
    event = {
        "event": event_name,
        "timestamp": datetime.now().isoformat(),
        "properties": properties or {},
    }
    with _events_lock:
        _events_buffer.append(event)

    # Auto-flush if buffer is large
    if len(_events_buffer) >= 50:
        flush_events_async()


def get_buffered_events():
    """Return and clear buffered events."""
    with _events_lock:
        events = list(_events_buffer)
        _events_buffer.clear()
    return events


def flush_events_async():
    """Send buffered events to collector in background."""
    events = get_buffered_events()
    if not events:
        return
    threading.Thread(target=_send_events, args=(events,), daemon=True).start()


def _send_events(events):
    """Actually send events to the collector."""
    try:
        from config import load_config
        cfg = load_config()
        url = cfg.get("collector_url", "").strip()
        if not url:
            return

        payload = {
            "type": "events",
            "installation_id": _get_installation_id(),
            "system": get_system_info(),
            "events": events,
        }

        _http_post(url + "/api/collect/events", payload)
    except Exception:
        applog.exception("[telemetry] Failed to send events")


# ─── Diagnostic Bundle ──────────────────────────────────────────────────

def build_diagnostic_bundle(include_log_lines=500):
    """Build a full diagnostic bundle for troubleshooting.

    Returns a dict with system info, recent events, and logs.
    """
    bundle = {
        "type": "diagnostic",
        "installation_id": _get_installation_id(),
        "timestamp": datetime.now().isoformat(),
        "system": get_system_info(),
        "events": get_buffered_events(),
        "log": applog.read_log(max_lines=include_log_lines),
        "config_summary": _safe_config_summary(),
    }
    return bundle


def _safe_config_summary():
    """Return config info without sensitive data (no passwords/emails)."""
    try:
        from config import load_config
        cfg = load_config()
        return {
            "has_email_configured": bool(cfg.get("email_address")),
            "imap_server": cfg.get("imap_server", ""),
            "github_repo": cfg.get("github_repo", ""),
            "professor_specialty": cfg.get("professor_specialty", ""),
            "num_custom_fields": len(cfg.get("custom_fields", [])),
            "has_field_overrides": bool(cfg.get("field_overrides")),
            "collector_url": cfg.get("collector_url", ""),
        }
    except Exception:
        return {}


def send_diagnostic_bundle():
    """Send a diagnostic bundle to the collector. Returns result dict."""
    try:
        from config import load_config
        cfg = load_config()
        url = cfg.get("collector_url", "").strip()
        if not url:
            return {"success": False, "message": "לא הוגדר כתובת שרת איסוף לוגים"}

        bundle = build_diagnostic_bundle()
        result = _http_post(url + "/api/collect/diagnostic", bundle)

        applog.info(f"[telemetry] Diagnostic bundle sent successfully")
        return {"success": True, "message": "הלוגים נשלחו בהצלחה לשרת האיסוף"}
    except Exception as e:
        applog.exception(f"[telemetry] Failed to send diagnostic bundle")
        return {"success": False, "message": f"שגיאה בשליחה: {e}"}


# ─── HTTP Helper ────────────────────────────────────────────────────────

def _http_post(url, data, timeout=15):
    """POST JSON data to a URL. Uses urllib to avoid extra dependencies."""
    import urllib.request
    import urllib.error

    payload = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}")
