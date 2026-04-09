"""
schema.py - THE single source of truth for all case fields.

To add a new field in the future, just add an entry to CASE_FIELDS below.
Everything else (Excel columns, CSV metadata, forms, tables, detail views,
edit modals, filters, status badges) adapts automatically.
"""

SCHEMA_VERSION = 2

# ============================================================
# Field definitions
# ============================================================
# Each field is a dict with:
#   key          - internal name (used in code, Excel keys, API)
#   label        - Hebrew display label
#   type         - "text" | "number" | "select" | "textarea" | "email" | "date"
#   width        - Excel column width
#   group        - UI section: "info" | "status" | "call" | "payment" | "meta"
#   options      - list of allowed values (for "select" type)
#   colors       - dict mapping option value -> color name (success/warning/danger/info)
#   default      - default value for new cases
#   in_table     - show in the cases list table
#   in_dashboard - show in dashboard recent-cases table
#   editable     - show in edit form (false for auto-generated fields like case_number)
#   in_new_form  - show in the "new case" form
#   required     - required in new case form
#   extractable  - can be auto-extracted from emails/attachments
#   is_status    - treat as a status field (for dashboard counters)

CASE_FIELDS = [
    {
        "key": "case_number",
        "label": "מס׳ תיק",
        "type": "number",
        "width": 10,
        "group": "info",
        "default": "",
        "in_table": True,
        "in_dashboard": True,
        "editable": False,
        "in_new_form": False,
        "required": False,
        "extractable": False,
    },
    {
        "key": "date_received",
        "label": "תאריך קבלה",
        "type": "text",
        "width": 14,
        "group": "info",
        "default": "",
        "in_table": True,
        "in_dashboard": True,
        "editable": False,
        "in_new_form": False,
        "required": False,
        "extractable": False,
    },
    {
        "key": "source_type",
        "label": "מקור הפנייה",
        "type": "select",
        "width": 14,
        "group": "info",
        "options": ["עו״ד", "פרטי", "ביהמ״ש", "חברת ביטוח"],
        "default": "פרטי",
        "in_table": True,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": True,
    },
    {
        "key": "sender_name",
        "label": "שם השולח",
        "type": "text",
        "width": 18,
        "group": "info",
        "default": "",
        "in_table": True,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": True,
    },
    {
        "key": "sender_email",
        "label": "אימייל השולח",
        "type": "email",
        "width": 24,
        "group": "info",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": True,
    },
    {
        "key": "plaintiff_name",
        "label": "שם מלא",
        "type": "text",
        "width": 18,
        "group": "info",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": True,
    },
    {
        "key": "plaintiff_first_name",
        "label": "שם פרטי",
        "type": "text",
        "width": 14,
        "group": "info",
        "default": "",
        "in_table": True,
        "in_dashboard": True,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": True,
    },
    {
        "key": "plaintiff_last_name",
        "label": "שם משפחה",
        "type": "text",
        "width": 14,
        "group": "info",
        "default": "",
        "in_table": True,
        "in_dashboard": True,
        "editable": True,
        "in_new_form": True,
        "required": True,
        "extractable": True,
    },
    {
        "key": "plaintiff_id",
        "label": "ת.ז. תובע",
        "type": "text",
        "width": 14,
        "group": "info",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": True,
    },
    {
        "key": "opposing_party",
        "label": "צד שכנגד",
        "type": "text",
        "width": 18,
        "group": "info",
        "default": "",
        "in_table": True,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": True,
    },
    {
        "key": "subject",
        "label": "נושא",
        "type": "text",
        "width": 20,
        "group": "info",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": True,
    },
    {
        "key": "material_status",
        "label": "סטטוס חומר",
        "type": "select",
        "width": 12,
        "group": "status",
        "options": ["מלא", "חלקי", "חסר"],
        "colors": {"מלא": "success", "חלקי": "warning", "חסר": "danger"},
        "default": "חלקי",
        "in_table": True,
        "in_dashboard": True,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": True,
        "is_status": True,
        "dashboard_counter": {"name": "missing_material", "label": "חומר חסר", "count_values": ["חלקי", "חסר"], "color": "red"},
    },
    {
        "key": "missing_material_details",
        "label": "פירוט חומר חסר",
        "type": "text",
        "width": 22,
        "group": "status",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": True,
    },
    {
        "key": "call_required",
        "label": "שיחה נדרשת",
        "type": "select",
        "width": 12,
        "group": "call",
        "options": ["כן", "לא"],
        "colors": {"כן": "warning", "לא": "success"},
        "default": "לא",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": False,
        "is_status": True,
    },
    {
        "key": "call_date",
        "label": "תאריך שיחה",
        "type": "text",
        "width": 14,
        "group": "call",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": False,
    },
    {
        "key": "call_summary",
        "label": "סיכום שיחה",
        "type": "textarea",
        "width": 24,
        "group": "call",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": False,
    },
    {
        "key": "agreed_amount",
        "label": "סכום מוסכם",
        "type": "number",
        "width": 14,
        "group": "payment",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": False,
    },
    {
        "key": "payment_date",
        "label": "תאריך תשלום",
        "type": "text",
        "width": 14,
        "group": "payment",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": False,
    },
    {
        "key": "payment_status",
        "label": "סטטוס תשלום",
        "type": "select",
        "width": 12,
        "group": "payment",
        "options": ["ממתין", "שולם"],
        "colors": {"ממתין": "warning", "שולם": "success"},
        "default": "ממתין",
        "in_table": True,
        "in_dashboard": True,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": False,
        "is_status": True,
        "dashboard_counter": {"name": "pending_payment", "label": "ממתינים לתשלום", "count_values": ["ממתין"], "color": "yellow"},
    },
    {
        "key": "opinion_status",
        "label": "סטטוס חוו״ד",
        "type": "select",
        "width": 14,
        "group": "status",
        "options": ["טרם החל", "בעבודה", "הושלם", "נשלח"],
        "colors": {"טרם החל": "danger", "בעבודה": "warning", "הושלם": "success", "נשלח": "info"},
        "default": "טרם החל",
        "in_table": True,
        "in_dashboard": True,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": False,
        "is_status": True,
        "dashboard_counter_multi": [
            {"name": "new_cases", "label": "ממתינים לטיפול", "count_values": ["טרם החל"], "color": "red"},
            {"name": "in_progress", "label": "בעבודה", "count_values": ["בעבודה"], "color": "yellow"},
            {"name": "completed", "label": "הושלמו", "count_values": ["הושלם", "נשלח"], "color": "green"},
        ],
    },
    {
        "key": "completion_deadline",
        "label": "מועד סיום",
        "type": "text",
        "width": 14,
        "group": "status",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": False,
        "required": False,
        "extractable": False,
    },
    {
        "key": "date_sent",
        "label": "תאריך שליחה",
        "type": "text",
        "width": 14,
        "group": "status",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": False,
        "in_new_form": False,
        "required": False,
        "extractable": False,
    },
    {
        "key": "folder_path",
        "label": "נתיב תיקייה",
        "type": "text",
        "width": 30,
        "group": "meta",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": False,
        "in_new_form": False,
        "required": False,
        "extractable": False,
    },
    {
        "key": "notes",
        "label": "הערות",
        "type": "textarea",
        "width": 24,
        "group": "info",
        "default": "",
        "in_table": False,
        "in_dashboard": False,
        "editable": True,
        "in_new_form": True,
        "required": False,
        "extractable": False,
    },
]


# ============================================================
# Derived helpers (computed from CASE_FIELDS)
# ============================================================

# Module-level storage for user-defined custom fields.
# Set via set_custom_fields() at startup and whenever custom fields change.
_custom_fields = []


def set_custom_fields(custom):
    """Register user-defined custom fields. Called on startup and on changes."""
    global _custom_fields
    # Mark each as custom and ensure required props
    cleaned = []
    for f in (custom or []):
        if not f.get("key") or not f.get("label"):
            continue
        cleaned.append({
            "key": f["key"],
            "label": f["label"],
            "type": f.get("type", "text"),
            "width": f.get("width", 18),
            "group": f.get("group", "info"),
            "options": f.get("options", []) if f.get("type") == "select" else None,
            "default": f.get("default", ""),
            "in_table": bool(f.get("in_table", True)),
            "in_dashboard": bool(f.get("in_dashboard", False)),
            "editable": True,
            "in_new_form": bool(f.get("in_new_form", True)),
            "required": False,
            "extractable": bool(f.get("extractable", False)),
            "is_custom": True,
        })
    _custom_fields = cleaned


def get_all_fields():
    """Return base CASE_FIELDS plus any registered custom fields."""
    return CASE_FIELDS + _custom_fields


def get_custom_fields():
    """Return only the custom fields."""
    return list(_custom_fields)


def get_field(key):
    """Get a field definition by key. Returns None if not found."""
    for f in get_all_fields():
        if f["key"] == key:
            return f
    return None


def get_all_keys():
    """Return list of all field keys in order."""
    return [f["key"] for f in get_all_fields()]


def get_columns():
    """Return list of (label, width) tuples for Excel columns."""
    return [(f["label"], f["width"]) for f in get_all_fields()]


def get_key_to_col():
    """Return dict mapping field key -> 1-based Excel column index."""
    return {f["key"]: i + 1 for i, f in enumerate(get_all_fields())}


def get_labels_map():
    """Return dict mapping field key -> Hebrew label (for CSV, display)."""
    return {f["key"]: f["label"] for f in get_all_fields()}


def get_status_colors():
    """Return combined color map from all fields that define colors."""
    colors = {}
    for f in get_all_fields():
        if f.get("colors"):
            colors.update(f["colors"])
    return colors


def get_status_fields():
    """Return list of field keys that are status fields (have colors)."""
    return [f["key"] for f in get_all_fields() if f.get("is_status")]


def get_defaults():
    """Return dict of field key -> default value."""
    return {f["key"]: f["default"] for f in get_all_fields() if f.get("default")}


def get_dashboard_counters():
    """Return list of dashboard counter definitions.

    Each counter: {name, label, field_key, count_values, color}
    """
    counters = [{"name": "total", "label": "סה\"כ תיקים", "field_key": None, "count_values": None, "color": "blue"}]
    for f in get_all_fields():
        if "dashboard_counter" in f:
            dc = f["dashboard_counter"]
            counters.append({**dc, "field_key": f["key"]})
        if "dashboard_counter_multi" in f:
            for dc in f["dashboard_counter_multi"]:
                counters.append({**dc, "field_key": f["key"]})
    return counters


def get_extractable_keys(overrides=None):
    """Return list of field keys that can be auto-extracted from emails."""
    fields = apply_overrides(get_all_fields(), overrides) if overrides else get_all_fields()
    return [f["key"] for f in fields if f.get("extractable")]


# Properties that the user can override from the UI
OVERRIDABLE_PROPS = ["in_table", "in_dashboard", "in_new_form", "extractable"]


def apply_overrides(fields, overrides):
    """Apply user overrides on top of base schema fields.

    Args:
        fields: list of field dicts (will be deep-copied)
        overrides: dict of {field_key: {prop: value, ...}}

    Returns:
        New list of field dicts with overrides applied.
    """
    if not overrides:
        return fields

    result = []
    for f in fields:
        merged = dict(f)  # shallow copy
        field_overrides = overrides.get(f["key"], {})
        for prop in OVERRIDABLE_PROPS:
            if prop in field_overrides:
                merged[prop] = field_overrides[prop]
        result.append(merged)
    return result


def to_json(overrides=None):
    """Return schema as JSON-serializable dict for the frontend API.

    Args:
        overrides: optional dict from config.json field_overrides
    """
    all_fields = get_all_fields()
    fields = apply_overrides(all_fields, overrides) if overrides else all_fields
    return {
        "version": SCHEMA_VERSION,
        "fields": fields,
        "dashboard_counters": get_dashboard_counters(),
        "status_colors": get_status_colors(),
        "overridable_props": OVERRIDABLE_PROPS,
        "groups": {
            "info": "פרטי הפנייה",
            "status": "סטטוס וחומרים",
            "call": "שיחה עם התובע",
            "payment": "תשלום",
            "meta": "מטא-דאטה",
        },
    }
