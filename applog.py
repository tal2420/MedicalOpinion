"""
Centralized application logging.

Writes timestamped entries to <data_dir>/app.log so the user can easily find
and share the log file when reporting issues.
"""

import os
import sys
import traceback
from datetime import datetime


_LOG_FILE_NAME = "app.log"
_MAX_LOG_SIZE = 2 * 1024 * 1024  # 2MB - rotate when exceeded


def _get_log_path():
    """Get the path to the log file in the data directory."""
    try:
        from config import get_data_dir
        return os.path.join(get_data_dir(), _LOG_FILE_NAME)
    except Exception:
        # Fallback: log next to the app
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), _LOG_FILE_NAME)


def _rotate_if_needed(path):
    """Rotate log file if it grows too large."""
    try:
        if os.path.exists(path) and os.path.getsize(path) > _MAX_LOG_SIZE:
            old = path + ".old"
            if os.path.exists(old):
                os.remove(old)
            os.rename(path, old)
    except Exception:
        pass


def log(level, *args):
    """Write a log entry. Level: INFO/WARN/ERROR/DEBUG."""
    try:
        path = _get_log_path()
        _rotate_if_needed(path)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = " ".join(str(a) for a in args)
        line = f"[{ts}] [{level}] {msg}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
        # Also print to stdout for live debugging
        try:
            print(line.rstrip(), flush=True)
        except Exception:
            pass
    except Exception:
        pass  # never let logging break the app


def info(*args):
    log("INFO", *args)


def warn(*args):
    log("WARN", *args)


def error(*args):
    log("ERROR", *args)


def exception(prefix=""):
    """Log a full exception traceback."""
    try:
        path = _get_log_path()
        _rotate_if_needed(path)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] [ERROR] {prefix}\n")
            traceback.print_exc(file=f)
            f.write("\n")
        traceback.print_exc()
    except Exception:
        pass


def get_log_path():
    """Public accessor for the log file path."""
    return _get_log_path()


def read_log(max_lines=500):
    """Read the most recent N lines from the log."""
    path = _get_log_path()
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-max_lines:])
    except Exception as e:
        return f"Error reading log: {e}"
