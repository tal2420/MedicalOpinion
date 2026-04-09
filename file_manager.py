import os
import csv
import json
import re
from datetime import datetime
from config import get_data_dir


def sanitize_folder_name(name):
    """Remove characters that are invalid in Windows folder names."""
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = name.strip('. ')
    return name or "unnamed"


def create_case_folder(case_number, plaintiff_name, date_received=None):
    """Create the folder structure for a new case. Returns the folder path."""
    if not date_received:
        date_received = datetime.now().strftime("%Y-%m-%d")
    elif "/" in date_received:
        # Convert from DD/MM/YYYY to YYYY-MM-DD
        parts = date_received.split("/")
        if len(parts) == 3:
            date_received = f"{parts[2]}-{parts[1]}-{parts[0]}"

    safe_name = sanitize_folder_name(plaintiff_name or "ללא_שם")
    folder_name = f"{date_received}_{safe_name}_תיק_{case_number}"

    cases_dir = os.path.join(get_data_dir(), "תיקים")
    os.makedirs(cases_dir, exist_ok=True)

    case_path = os.path.join(cases_dir, folder_name)
    os.makedirs(case_path, exist_ok=True)
    os.makedirs(os.path.join(case_path, "מצורפים"), exist_ok=True)
    os.makedirs(os.path.join(case_path, "חוות_דעת"), exist_ok=True)

    return case_path


def save_email_to_folder(case_path, subject, sender, date, body_html):
    """Save the original email as HTML file."""
    email_html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="UTF-8"><title>{subject}</title>
<style>body {{ font-family: Arial; direction: rtl; padding: 20px; }}
.header {{ background: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 20px; }}
.header p {{ margin: 5px 0; }}</style></head>
<body>
<div class="header">
<p><strong>מאת:</strong> {sender}</p>
<p><strong>תאריך:</strong> {date}</p>
<p><strong>נושא:</strong> {subject}</p>
</div>
<div class="body">{body_html}</div>
</body></html>"""

    path = os.path.join(case_path, "מייל_מקורי.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(email_html)
    return path


def save_attachment(case_path, filename, content_bytes):
    """Save an attachment to the case folder."""
    safe_name = sanitize_folder_name(filename)
    attachments_dir = os.path.join(case_path, "מצורפים")
    path = os.path.join(attachments_dir, safe_name)

    # Handle duplicate filenames
    base, ext = os.path.splitext(path)
    counter = 1
    while os.path.exists(path):
        path = f"{base}_{counter}{ext}"
        counter += 1

    with open(path, "wb") as f:
        f.write(content_bytes)
    return path


def save_case_metadata(case_path, metadata):
    """Save case metadata as CSV (openable in Excel without the app).

    Labels are read from schema.py so new fields automatically get Hebrew labels.
    """
    import schema
    labels = schema.get_labels_map()

    path = os.path.join(case_path, "פרטי_תיק.csv")
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["שדה", "ערך"])
        for key, value in metadata.items():
            hebrew_label = labels.get(key, key)
            writer.writerow([hebrew_label, str(value) if value else ""])
    return path


def get_case_attachments(case_path):
    """List all attachments in a case folder."""
    attachments_dir = os.path.join(case_path, "מצורפים")
    if not os.path.exists(attachments_dir):
        return []
    return [
        {"name": f, "path": os.path.join(attachments_dir, f),
         "size": os.path.getsize(os.path.join(attachments_dir, f))}
        for f in os.listdir(attachments_dir)
        if os.path.isfile(os.path.join(attachments_dir, f))
    ]


def get_case_opinions(case_path):
    """List all opinion documents in a case folder."""
    opinions_dir = os.path.join(case_path, "חוות_דעת")
    if not os.path.exists(opinions_dir):
        return []
    return [
        {"name": f, "path": os.path.join(opinions_dir, f),
         "size": os.path.getsize(os.path.join(opinions_dir, f))}
        for f in os.listdir(opinions_dir)
        if os.path.isfile(os.path.join(opinions_dir, f))
    ]


def open_folder_in_explorer(path):
    """Open a folder in the system file explorer."""
    import subprocess
    import sys
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])
