import os
import sys
import threading
from flask import Flask, render_template, jsonify, request, send_from_directory, Response
import json

import config
import excel_manager
import file_manager
import email_service
import email_parser
import attachment_parser
import doc_generator
import updater
import schema
import applog
import telemetry

app = Flask(__name__, static_folder="templates/static", static_url_path="/static")


# ===== Pages =====
@app.route("/")
def index():
    return render_template("index.html")


def _get_field_overrides():
    """Load field overrides from config."""
    return config.load_config().get("field_overrides", {})


def _full_plaintiff_name(case_or_data):
    """Return the best available full name from a case dict."""
    name = (case_or_data.get("plaintiff_name") or "").strip()
    if name:
        return name
    parts = [
        (case_or_data.get("plaintiff_first_name") or "").strip(),
        (case_or_data.get("plaintiff_last_name") or "").strip(),
    ]
    return " ".join(p for p in parts if p)


def _refresh_custom_fields():
    """Reload custom fields from config into the schema module."""
    custom = config.load_config().get("custom_fields", [])
    schema.set_custom_fields(custom)


# Load custom fields at startup
_refresh_custom_fields()


# ===== Schema API =====
@app.route("/api/schema")
def api_schema():
    return jsonify(schema.to_json(overrides=_get_field_overrides()))


@app.route("/api/schema/overrides", methods=["POST"])
def api_save_field_overrides():
    """Save field visibility/behavior overrides."""
    overrides = request.get_json()
    cfg = config.load_config()
    cfg["field_overrides"] = overrides
    config.save_config(cfg)
    return jsonify({"success": True})


@app.route("/api/schema/custom-fields", methods=["GET"])
def api_get_custom_fields():
    """Return only the user-defined custom fields."""
    return jsonify(schema.get_custom_fields())


@app.route("/api/schema/custom-fields", methods=["POST"])
def api_save_custom_field():
    """Add or update a custom field."""
    field = request.get_json()
    if not field.get("label"):
        return jsonify({"error": "תווית השדה חובה"}), 400

    # Auto-generate key from label if not provided
    key = field.get("key", "").strip()
    if not key:
        # Transliterate label to a safe key
        import re as _re
        # Use a hash of the label for a unique key
        import hashlib
        key = "custom_" + hashlib.md5(field["label"].encode("utf-8")).hexdigest()[:8]
    field["key"] = key

    # Validate key isn't reserved
    base_keys = {f["key"] for f in schema.CASE_FIELDS}
    if key in base_keys:
        return jsonify({"error": "שם השדה תפוס על ידי שדה מערכת"}), 400

    cfg = config.load_config()
    custom = cfg.get("custom_fields", [])

    # Update if exists, else add
    found = False
    for i, f in enumerate(custom):
        if f.get("key") == key:
            custom[i] = field
            found = True
            break
    if not found:
        custom.append(field)

    cfg["custom_fields"] = custom
    config.save_config(cfg)
    _refresh_custom_fields()
    return jsonify({"success": True, "key": key})


@app.route("/api/schema/custom-fields/<key>", methods=["DELETE"])
def api_delete_custom_field(key):
    """Delete a custom field by key."""
    cfg = config.load_config()
    custom = cfg.get("custom_fields", [])
    custom = [f for f in custom if f.get("key") != key]
    cfg["custom_fields"] = custom
    config.save_config(cfg)
    _refresh_custom_fields()
    return jsonify({"success": True})


# ===== Dashboard API =====
@app.route("/api/dashboard")
def api_dashboard():
    stats = excel_manager.get_dashboard_stats()
    return jsonify(stats)


# ===== Cases API =====
@app.route("/api/cases", methods=["GET"])
def api_get_cases():
    cases = excel_manager.get_all_cases()
    # Convert any non-serializable types
    for c in cases:
        for k, v in c.items():
            if v is None:
                c[k] = ""
            elif not isinstance(v, (str, int, float, bool)):
                c[k] = str(v)
    return jsonify(cases)


@app.route("/api/cases", methods=["POST"])
def api_create_case():
    data = request.get_json()
    telemetry.track_event("case_create", {"source": data.get("referral_source", "manual")})

    # Create case in Excel
    case_number = excel_manager.add_case(data)

    # Create folder structure
    folder_path = file_manager.create_case_folder(
        case_number,
        _full_plaintiff_name(data),
        data.get("date_received", ""),
    )

    # Update folder path in Excel
    excel_manager.update_case(case_number, {"folder_path": folder_path})

    # Save metadata
    data["case_number"] = case_number
    file_manager.save_case_metadata(folder_path, data)

    return jsonify({"case_number": case_number, "folder_path": folder_path})


@app.route("/api/cases/<int:case_number>", methods=["GET"])
def api_get_case(case_number):
    case = excel_manager.get_case(case_number)
    if not case:
        return jsonify({"error": "Case not found"}), 404
    for k, v in case.items():
        if v is None:
            case[k] = ""
        elif not isinstance(v, (str, int, float, bool)):
            case[k] = str(v)
    return jsonify(case)


@app.route("/api/cases/<int:case_number>", methods=["PUT"])
def api_update_case(case_number):
    data = request.get_json()
    try:
        excel_manager.update_case(case_number, data)
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 404


@app.route("/api/cases/<int:case_number>", methods=["DELETE"])
def api_delete_case(case_number):
    if excel_manager.delete_case(case_number):
        return jsonify({"success": True})
    return jsonify({"error": "Case not found"}), 404


@app.route("/api/cases/<int:case_number>/files")
def api_case_files(case_number):
    case = excel_manager.get_case(case_number)
    if not case or not case.get("folder_path"):
        return jsonify({"attachments": [], "opinions": []})

    folder_path = str(case["folder_path"])
    if not os.path.exists(folder_path):
        return jsonify({"attachments": [], "opinions": []})

    attachments = file_manager.get_case_attachments(folder_path)
    opinions = file_manager.get_case_opinions(folder_path)

    return jsonify({
        "attachments": [{"name": a["name"], "size": a["size"], "path": a["path"]} for a in attachments],
        "opinions": [{"name": o["name"], "size": o["size"], "path": o["path"]} for o in opinions],
    })


@app.route("/api/cases/<int:case_number>/rescan", methods=["POST"])
def api_rescan_attachments(case_number):
    """Re-scan attachments on disk and extract missing data fields.

    Uses schema.get_extractable_keys() so new extractable fields are
    automatically included without code changes.
    """
    case = excel_manager.get_case(case_number)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    folder_path = str(case.get("folder_path", ""))
    attachments_dir = os.path.join(folder_path, "מצורפים") if folder_path else ""

    if not attachments_dir or not os.path.exists(attachments_dir):
        return jsonify({"error": "No attachments folder found"}), 404

    att_text = attachment_parser.extract_all_from_folder(attachments_dir)
    if not att_text:
        return jsonify({"error": "No text could be extracted from attachments"}), 400

    # Re-parse using the full parser (schema-aware)
    parsed = email_parser.parse_email({
        "subject": str(case.get("subject", "")),
        "sender_name": str(case.get("sender_name", "")),
        "sender_email": str(case.get("sender_email", "")),
        "date": str(case.get("date_received", "")),
        "body_html": "",
        "attachments": [],
    }, attachment_text=att_text)

    # Only fill in fields that are currently empty in the case
    updates = {}
    extractable = schema.get_extractable_keys(overrides=_get_field_overrides())
    for key in extractable:
        if not case.get(key) and parsed.get(key):
            updates[key] = parsed[key]

    # Append notes if they have new info
    if parsed.get("notes") and parsed["notes"] != str(case.get("notes", "")):
        existing = str(case.get("notes", ""))
        new_notes = parsed["notes"]
        if existing:
            # Only add parts not already in notes
            for part in new_notes.split(" | "):
                if part and part not in existing:
                    existing += f" | {part}"
            updates["notes"] = existing
        else:
            updates["notes"] = new_notes

    if notes_parts:
        existing_notes = str(case.get("notes", ""))
        new_notes = " | ".join(notes_parts)
        updates["notes"] = f"{existing_notes} | {new_notes}" if existing_notes else new_notes

    if updates:
        excel_manager.update_case(case_number, updates)
        return jsonify({"success": True, "updated_fields": list(updates.keys()), "values": updates})
    else:
        return jsonify({"success": True, "updated_fields": [], "message": "No new data found in attachments"})


@app.route("/api/cases/<int:case_number>/generate", methods=["POST"])
def api_generate_opinion(case_number):
    telemetry.track_event("opinion_generate", {"case_number": case_number})
    case = excel_manager.get_case(case_number)
    if not case:
        return jsonify({"error": "Case not found"}), 404

    folder_path = str(case.get("folder_path", ""))
    if not folder_path or not os.path.exists(folder_path):
        # Create folder if missing
        folder_path = file_manager.create_case_folder(
            case_number,
            _full_plaintiff_name(case),
            str(case.get("date_received", "")),
        )
        excel_manager.update_case(case_number, {"folder_path": folder_path})

    doc_path = doc_generator.generate_opinion(case, folder_path)

    # Update status
    excel_manager.update_case(case_number, {"opinion_status": "בעבודה"})

    return jsonify({"path": doc_path})


# ===== Email API =====
@app.route("/api/emails/scan")
def api_scan_emails():
    import time as _time
    t0 = _time.time()
    try:
        max_count = int(request.args.get("max", 20))
        days_back_raw = request.args.get("days", "")
        days_back = int(days_back_raw) if days_back_raw and days_back_raw != "0" else None
        unread_only = request.args.get("unread_only", "true").lower() == "true"

        applog.info(f"[scan] START max={max_count} days={days_back} unread_only={unread_only}")
        telemetry.track_event("email_scan", {"max": max_count, "days": days_back, "unread_only": unread_only})

        emails = email_service.fetch_emails(
            max_count=max_count,
            unread_only=unread_only,
            days_back=days_back,
            headers_only=True,
        )
        t1 = _time.time()
        applog.info(f"[scan] fetch took {t1-t0:.2f}s, got {len(emails)} emails")

        for e in emails:
            if "attachments" in e:
                e["attachments"] = [
                    {"filename": a["filename"], "size": a.get("size", 0)}
                    for a in e["attachments"]
                ]
        applog.info(f"[scan] DONE total {_time.time()-t0:.2f}s")
        return jsonify(emails)
    except Exception as e:
        applog.exception(f"[scan] FAILED after {_time.time()-t0:.2f}s")
        return jsonify({"error": str(e)}), 500


@app.route("/api/emails/import", methods=["POST"])
def api_import_email():
    email_data = request.get_json()
    telemetry.track_event("email_import", {"subject_length": len(email_data.get("subject", ""))})

    # Step 1: Re-fetch the full email with binary attachments from server
    full_attachments = []
    try:
        config_data = config.load_config()
        if config_data.get("email_address") and config_data.get("email_password"):
            full_emails = email_service.fetch_emails(max_count=30, unread_only=False)
            matching = [e for e in full_emails if e.get("subject") == email_data.get("subject")
                        and e.get("sender_email") == email_data.get("sender_email")]
            if matching:
                full_attachments = matching[0].get("attachments", [])
    except Exception as e:
        print(f"[import] Could not re-fetch attachments: {e}")

    # Step 2: Extract text from all attachments (PDF, Word, etc.)
    att_text = ""
    if full_attachments:
        try:
            att_text = attachment_parser.extract_all_attachments_text(full_attachments)
        except Exception as e:
            print(f"[import] Error extracting attachment text: {e}")

    # Step 3: Parse email + attachment text together
    email_data_with_content = {**email_data}
    if full_attachments:
        email_data_with_content["attachments"] = full_attachments
    parsed = email_parser.parse_email(email_data_with_content, attachment_text=att_text)

    # Step 4: Create case in Excel
    case_number = excel_manager.add_case(parsed)

    # Step 5: Create folder structure
    folder_path = file_manager.create_case_folder(
        case_number,
        _full_plaintiff_name(parsed),
        parsed.get("date_received", ""),
    )

    # Step 6: Save email to folder
    file_manager.save_email_to_folder(
        folder_path,
        email_data.get("subject", ""),
        f'{email_data.get("sender_name", "")} <{email_data.get("sender_email", "")}>',
        email_data.get("date", ""),
        email_data.get("body_html", ""),
    )

    # Step 7: Save attachments to disk
    for att in full_attachments:
        if att.get("content"):
            file_manager.save_attachment(folder_path, att["filename"], att["content"])

    # Step 8: Update folder path in Excel
    excel_manager.update_case(case_number, {"folder_path": folder_path})

    # Step 9: Save metadata
    parsed["case_number"] = case_number
    file_manager.save_case_metadata(folder_path, parsed)

    # Step 10: Mark email as read
    if email_data.get("message_id"):
        try:
            email_service.mark_as_read(email_data["message_id"])
        except Exception:
            pass

    return jsonify({"case_number": case_number, "parsed_fields": parsed})


def _import_one_email(email_data):
    """Import a single email. Yields progress dicts and finally a result dict."""
    subject = email_data.get("subject", "(ללא נושא)")
    sender_email = email_data.get("sender_email", "")

    # Step 1: Re-fetch full email with binary attachments
    yield {"step": "fetching", "message": f"מוריד מייל ומצורפים: {subject[:40]}"}
    full_attachments = []
    try:
        config_data = config.load_config()
        if config_data.get("email_address") and config_data.get("email_password"):
            full_emails = email_service.fetch_emails(max_count=50, unread_only=False)
            matching = [e for e in full_emails
                        if e.get("subject") == subject and e.get("sender_email") == sender_email]
            if matching:
                full_attachments = matching[0].get("attachments", [])
    except Exception as e:
        print(f"[import] Could not re-fetch attachments: {e}")

    # Step 2: Extract text from attachments
    att_text = ""
    if full_attachments:
        n = len(full_attachments)
        yield {"step": "extracting", "message": f"מחלץ טקסט מ-{n} קבצים מצורפים"}
        try:
            att_text = attachment_parser.extract_all_attachments_text(full_attachments)
        except Exception as e:
            print(f"[import] Error extracting attachment text: {e}")

    # Step 3: Parse email + attachment text
    yield {"step": "parsing", "message": "מחלץ פרטים אוטומטית (שם, ת.ז., צד שכנגד...)"}
    email_data_with_content = {**email_data}
    if full_attachments:
        email_data_with_content["attachments"] = full_attachments
    parsed = email_parser.parse_email(email_data_with_content, attachment_text=att_text)

    # Step 4: Create case in Excel
    yield {"step": "saving", "message": "יוצר תיק במאגר ה-Excel"}
    case_number = excel_manager.add_case(parsed)

    # Step 5: Create folder structure
    yield {"step": "saving", "message": f"יוצר תיקייה לתיק מס׳ {case_number}"}
    folder_path = file_manager.create_case_folder(
        case_number,
        _full_plaintiff_name(parsed),
        parsed.get("date_received", ""),
    )

    # Step 6: Save email to folder
    file_manager.save_email_to_folder(
        folder_path,
        email_data.get("subject", ""),
        f'{email_data.get("sender_name", "")} <{email_data.get("sender_email", "")}>',
        email_data.get("date", ""),
        email_data.get("body_html", ""),
    )

    # Step 7: Save attachments to disk
    if full_attachments:
        yield {"step": "saving", "message": f"שומר {len(full_attachments)} קבצים בתיקייה"}
    for att in full_attachments:
        if att.get("content"):
            file_manager.save_attachment(folder_path, att["filename"], att["content"])

    # Step 8: Update folder path
    excel_manager.update_case(case_number, {"folder_path": folder_path})

    # Step 9: Save metadata
    parsed["case_number"] = case_number
    file_manager.save_case_metadata(folder_path, parsed)

    # Step 10: Mark email as read
    if email_data.get("message_id"):
        try:
            email_service.mark_as_read(email_data["message_id"])
        except Exception:
            pass

    yield {"result": True, "case_number": case_number, "parsed_fields": parsed}


@app.route("/api/emails/import-stream", methods=["POST"])
def api_import_stream():
    """Import multiple emails with live progress via Server-Sent Events."""
    try:
        payload = request.get_json(silent=True) or {}
        emails = payload.get("emails", [])
        total = len(emails)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    def generate():
        import json as _json
        imported = 0
        try:
            for idx, email_data in enumerate(emails):
                try:
                    for event in _import_one_email(email_data):
                        if "result" in event:
                            msg = {
                                "type": "complete",
                                "email_index": idx,
                                "total": total,
                                "case_number": event["case_number"],
                                "parsed_fields": event["parsed_fields"],
                            }
                            imported += 1
                        else:
                            msg = {
                                "type": "progress",
                                "email_index": idx,
                                "total": total,
                                "step": event["step"],
                                "message": event["message"],
                            }
                        yield f"data: {_json.dumps(msg, ensure_ascii=False, default=str)}\n\n"
                except Exception as e:
                    err = {
                        "type": "error",
                        "email_index": idx,
                        "total": total,
                        "message": str(e),
                    }
                    yield f"data: {_json.dumps(err, ensure_ascii=False)}\n\n"
        except Exception as e:
            err = {"type": "error", "message": f"Stream failure: {e}"}
            yield f"data: {_json.dumps(err, ensure_ascii=False)}\n\n"

        done = {"type": "done", "total_imported": imported, "total": total}
        yield f"data: {_json.dumps(done, ensure_ascii=False)}\n\n"

    response = Response(generate(), mimetype="text/event-stream")
    # Disable buffering so events flow to client immediately
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    response.headers["Connection"] = "keep-alive"
    return response


@app.route("/api/emails/test")
def api_test_email():
    success, message = email_service.test_connection()
    return jsonify({"success": success, "message": message})


# ===== Folder Import =====
@app.route("/api/folder/scan", methods=["POST"])
def api_scan_folder():
    """Scan a local folder for PDF/Word files and return their list."""
    data = request.get_json() or {}
    folder_path = data.get("path", "")
    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({"error": "Folder not found"}), 404

    supported = {".pdf", ".docx", ".doc", ".txt", ".html", ".htm", ".rtf", ".csv"}
    files = []
    try:
        for fn in sorted(os.listdir(folder_path)):
            ext = os.path.splitext(fn.lower())[1]
            if ext in supported:
                full = os.path.join(folder_path, fn)
                if os.path.isfile(full):
                    files.append({
                        "name": fn,
                        "size": os.path.getsize(full),
                        "ext": ext,
                    })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"files": files, "count": len(files)})


@app.route("/api/folder/import", methods=["POST"])
def api_import_folder():
    """Create a new case by importing files from a local folder.

    Extracts text from all supported files, parses for case data,
    creates the case, and copies the files into the case folder.
    """
    data = request.get_json() or {}
    folder_path = data.get("path", "")
    telemetry.track_event("folder_import", {"has_path": bool(folder_path)})
    if not folder_path or not os.path.isdir(folder_path):
        return jsonify({"error": "Folder not found"}), 404

    applog.info(f"[folder-import] START folder={folder_path}")

    try:
        # Step 1: Extract text from all files in the folder
        applog.info("[folder-import] extracting text from files")
        att_text = attachment_parser.extract_all_from_folder(folder_path)

        # Step 2: Parse extracted text for case fields
        applog.info("[folder-import] parsing extracted text")
        folder_name = os.path.basename(folder_path)
        parsed = email_parser.parse_email({
            "subject": folder_name,
            "sender_name": "",
            "sender_email": "",
            "date": "",
            "body_html": "",
            "attachments": [],
        }, attachment_text=att_text)

        # Step 3: Create case in Excel
        case_number = excel_manager.add_case(parsed)
        applog.info(f"[folder-import] created case {case_number}")

        # Step 4: Create case folder
        case_folder = file_manager.create_case_folder(
            case_number,
            _full_plaintiff_name(parsed),
            parsed.get("date_received", ""),
        )

        # Step 5: Copy all supported files into the case attachments folder
        import shutil
        supported = {".pdf", ".docx", ".doc", ".txt", ".html", ".htm", ".rtf", ".csv"}
        copied = 0
        for fn in os.listdir(folder_path):
            ext = os.path.splitext(fn.lower())[1]
            if ext in supported and os.path.isfile(os.path.join(folder_path, fn)):
                src = os.path.join(folder_path, fn)
                dst = os.path.join(case_folder, "מצורפים", fn)
                shutil.copy2(src, dst)
                copied += 1

        # Step 6: Update folder path + save metadata
        excel_manager.update_case(case_number, {"folder_path": case_folder})
        parsed["case_number"] = case_number
        file_manager.save_case_metadata(case_folder, parsed)

        applog.info(f"[folder-import] DONE case={case_number} copied={copied} files")
        return jsonify({
            "success": True,
            "case_number": case_number,
            "copied_files": copied,
            "parsed_fields": parsed,
        })

    except Exception as e:
        applog.exception(f"[folder-import] FAILED: {e}")
        return jsonify({"error": str(e)}), 500


# ===== Send Email =====
@app.route("/api/send-email", methods=["POST"])
def api_send_email():
    data = request.get_json()
    to = data.get("to")
    subject = data.get("subject")
    body = data.get("body", "")
    attachment_path = data.get("attachment_path")
    case_number = data.get("case_number")

    if not to or not subject:
        return jsonify({"error": "Missing recipient or subject"}), 400

    attachments = [attachment_path] if attachment_path else None

    try:
        email_service.send_email(to, subject, body, attachments)

        # Update case status
        if case_number:
            from datetime import datetime
            excel_manager.update_case(int(case_number), {
                "opinion_status": "נשלח",
                "date_sent": datetime.now().strftime("%d/%m/%Y"),
            })

        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===== Settings API =====
@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    cfg = config.load_config()
    cfg["data_dir"] = config.get_data_dir()
    return jsonify(cfg)


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    data = request.get_json()

    # Handle data_dir change separately (stored in bootstrap, not in config.json)
    new_data_dir = data.pop("data_dir", None)
    if new_data_dir:
        old_dir = config.get_data_dir()
        if os.path.abspath(new_data_dir) != os.path.abspath(old_dir):
            config.set_data_dir(new_data_dir)
            # Reload custom fields from the new config location
            _refresh_custom_fields()

    current = config.load_config()
    current.update(data)
    config.save_config(current)

    # Regenerate template if professor details changed
    template_path = os.path.join(config.get_data_dir(), "תבנית_חוו״ד.docx")
    if os.path.exists(template_path):
        os.remove(template_path)
    doc_generator.get_template_path()  # Recreate with new details

    return jsonify({"success": True})


@app.route("/api/settings/browse-folder", methods=["POST"])
def api_browse_folder():
    """Open a native folder picker dialog (when using pywebview)."""
    try:
        import webview
        windows = webview.windows
        if windows:
            result = windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=config.get_data_dir(),
            )
            if result and len(result) > 0:
                return jsonify({"path": result[0]})
        return jsonify({"path": ""})
    except Exception:
        # Fallback: no dialog available in browser mode
        return jsonify({"path": "", "error": "Folder dialog only available in desktop mode"})


# ===== Update API =====
@app.route("/api/update/check")
def api_check_update():
    cfg = config.load_config()
    repo = cfg.get("github_repo", "")
    result = updater.check_for_update(repo)
    return jsonify(result)


@app.route("/api/update/apply", methods=["POST"])
def api_apply_update():
    data = request.get_json()
    url = data.get("download_url", "")
    if not url:
        return jsonify({"success": False, "message": "No download URL"}), 400
    result = updater.download_and_apply(url)
    return jsonify(result)


@app.route("/api/update/version")
def api_get_version():
    return jsonify({"version": updater.get_current_version()})


# ===== Open Folder / File =====
@app.route("/api/open-folder", methods=["POST"])
def api_open_folder():
    data = request.get_json()
    path = data.get("path", "")
    if path and os.path.exists(path):
        file_manager.open_folder_in_explorer(path)
        return jsonify({"success": True})
    return jsonify({"error": "Folder not found"}), 404


@app.route("/api/logs")
def api_get_logs():
    """Return the recent application log."""
    lines = int(request.args.get("lines", 500))
    return jsonify({
        "log": applog.read_log(max_lines=lines),
        "path": applog.get_log_path(),
    })


@app.route("/api/logs/open", methods=["POST"])
def api_open_log():
    """Open the log file with the OS default app."""
    path = applog.get_log_path()
    if not os.path.exists(path):
        # Create empty log so it can be opened
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"[{datetime_now()}] [INFO] Log file created\n")
    try:
        file_manager.open_folder_in_explorer(path)
        return jsonify({"success": True, "path": path})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def datetime_now():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ===== Telemetry API =====
@app.route("/api/telemetry/track", methods=["POST"])
def api_track_event():
    """Track a usage event (buffered locally, sent to collector periodically)."""
    data = request.get_json(silent=True) or {}
    event_name = data.get("event", "")
    properties = data.get("properties", {})
    if event_name:
        telemetry.track_event(event_name, properties)
    return jsonify({"ok": True})


@app.route("/api/telemetry/send-logs", methods=["POST"])
def api_send_logs():
    """Send diagnostic bundle (logs + system info + events) to the collector."""
    result = telemetry.send_diagnostic_bundle()
    return jsonify(result)


@app.route("/api/telemetry/send-events", methods=["POST"])
def api_flush_events():
    """Flush buffered usage events to the collector now."""
    telemetry.flush_events_async()
    return jsonify({"ok": True, "message": "אירועים נשלחו ברקע"})


@app.route("/api/open-file", methods=["POST"])
def api_open_file():
    """Open a file with the system default application.

    Accepts EITHER:
      - case_number + filename + kind ("attachment" | "opinion") - server resolves the path
      - path - direct path (legacy/fallback)
    """
    try:
        data = request.get_json(silent=True) or {}
    except Exception as e:
        applog.exception("[open-file] Failed to parse JSON request")
        return jsonify({"error": f"Bad request: {e}"}), 400

    case_number = data.get("case_number")
    filename = data.get("filename", "")
    kind = data.get("kind", "attachment")
    legacy_path = data.get("path", "")

    applog.info(f"[open-file] request case={case_number} filename={filename!r} kind={kind} legacy_path={legacy_path!r}")

    abs_path = None
    try:
        if case_number is not None and filename:
            case = excel_manager.get_case(int(case_number))
            if not case:
                applog.warn(f"[open-file] case {case_number} not found")
                return jsonify({"error": "Case not found"}), 404
            folder_path = str(case.get("folder_path", ""))
            applog.info(f"[open-file] case folder: {folder_path!r}")
            if not folder_path:
                return jsonify({"error": "Case has no folder_path"}), 404
            sub = "מצורפים" if kind == "attachment" else "חוות_דעת"
            candidate = os.path.join(folder_path, sub, filename)
            applog.info(f"[open-file] resolved path: {candidate!r}, exists={os.path.exists(candidate)}")
            if not os.path.exists(candidate):
                # Try fallback: scan the folder for any file matching the name
                folder_dir = os.path.join(folder_path, sub)
                if os.path.exists(folder_dir):
                    files_in_dir = os.listdir(folder_dir)
                    applog.info(f"[open-file] files in {folder_dir}: {files_in_dir}")
                return jsonify({"error": f"File not found: {filename}"}), 404
            abs_path = os.path.abspath(candidate)
        elif legacy_path:
            if not os.path.exists(legacy_path):
                applog.warn(f"[open-file] legacy path not found: {legacy_path}")
                return jsonify({"error": f"File not found: {legacy_path}"}), 404
            abs_path = os.path.abspath(legacy_path)
        else:
            applog.warn("[open-file] missing both case_number+filename and path")
            return jsonify({"error": "Missing case_number+filename or path"}), 400

        data_dir = os.path.abspath(config.get_data_dir())
        if not abs_path.startswith(data_dir):
            applog.warn(f"[open-file] access denied: {abs_path} not under {data_dir}")
            return jsonify({"error": "Access denied: file outside data directory"}), 403

        applog.info(f"[open-file] opening: {abs_path}")
        file_manager.open_folder_in_explorer(abs_path)
        return jsonify({"success": True})
    except Exception as e:
        applog.exception(f"[open-file] FAILED: {e}")
        return jsonify({"error": f"{type(e).__name__}: {e}"}), 500


# ===== Main =====
def get_port():
    return int(os.environ.get("PORT", 5555))


def _start_periodic_flush():
    """Flush telemetry events every 5 minutes in background."""
    import time as _time
    def _flush_loop():
        while True:
            _time.sleep(300)
            try:
                telemetry.flush_events_async()
            except Exception:
                pass
    t = threading.Thread(target=_flush_loop, daemon=True)
    t.start()


def run_flask():
    app.run(host="127.0.0.1", port=get_port(), debug=False, use_reloader=False)


if __name__ == "__main__":
    # Ensure data directory exists
    config.get_data_dir()

    # Track app startup
    telemetry.track_event("app_start")
    _start_periodic_flush()

    port = get_port()

    # Check if pywebview is available
    use_webview = True
    if "--no-gui" in sys.argv:
        use_webview = False

    try:
        import webview
    except ImportError:
        use_webview = False

    if use_webview:
        # Start Flask in background thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # Open in native window
        webview.create_window(
            "ניהול חוות דעת רפואיות",
            f"http://127.0.0.1:{port}",
            width=1200,
            height=800,
            min_size=(900, 600),
        )
        webview.start()
    else:
        print(f"Starting server at http://127.0.0.1:{port}")
        print("Open this URL in your browser.")
        app.run(host="127.0.0.1", port=port, debug=True)
