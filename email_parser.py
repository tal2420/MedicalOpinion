import re


# ============================================================
# Source type detection - keywords and domain patterns
# ============================================================
SOURCE_PATTERNS = {
    "עו״ד": {
        "keywords": [
            r"עו[\"״\']ד", r"עורך[- ]?דין", r"עורכת[- ]?דין", r"משרד\s+עו",
            r"law[\s-]?office", r"law[\s-]?firm", r"attorney", r"advocate",
            r"ייצוג\s+משפטי", r"תביע", r"ב\"כ\s+ה",
        ],
        "domains": [
            r"law\.co\.il", r"advocate", r"lawyer", r"legal",
            r"din\.co\.il", r"mishpat",
        ],
    },
    "ביהמ״ש": {
        "keywords": [
            r"בי[ת]?[- ]?ה?משפט", r"בי[ת]?[- ]?ה?דין", r"ביהמ[\"״]ש",
            r"court", r"שופט", r"רשם", r"מזכירות\s+בית",
            r"ת\.?א\.?\s*\d", r"ת\.?ק\.?\s*\d",  # תיק אזרחי / תיק קטן
        ],
        "domains": [r"court\.gov\.il", r"judiciary"],
    },
    "חברת ביטוח": {
        "keywords": [
            r"ביטוח", r"insurance", r"מגדל", r"הראל", r"כלל\s+ביטוח",
            r"הפניקס", r"מנורה", r"איילון", r"שומרה", r"הכשרה",
            r"ביט[וו]ח\s+לאומי", r"מבטחים", r"פוליס[הת]",
            r"תביעת?\s+ביטוח", r"מספר\s+פוליסה", r"מספר\s+תביעה",
            r"AIG", r"Clal", r"Harel", r"Phoenix", r"Migdal",
        ],
        "domains": [
            r"migdal\.co\.il", r"harel-group", r"clalbit", r"fnx\.co\.il",
            r"menora\.co\.il", r"ayalon-ins", r"shumra", r"hashkara",
        ],
    },
}


def identify_source_type(sender_name, sender_email, subject, body=""):
    """Identify the source type of the email based on keywords and email domain.

    Priority order:
    1. Domain match (highest confidence)
    2. Keywords in sender name (high confidence)
    3. Keywords in subject/body (lower confidence)
    """
    email_lower = (sender_email or "").lower()
    sender_lower = (sender_name or "")
    text_combined = f"{subject} {body[:1000]}"

    # Pass 1: domain matching (highest confidence)
    for source_type, patterns in SOURCE_PATTERNS.items():
        for domain_pattern in patterns.get("domains", []):
            if re.search(domain_pattern, email_lower, re.IGNORECASE):
                return source_type

    # Pass 2: keywords in sender name (high confidence)
    for source_type, patterns in SOURCE_PATTERNS.items():
        for kw_pattern in patterns.get("keywords", []):
            if re.search(kw_pattern, sender_lower, re.IGNORECASE):
                return source_type

    # Pass 3: keywords in subject + body (lower confidence)
    for source_type, patterns in SOURCE_PATTERNS.items():
        for kw_pattern in patterns.get("keywords", []):
            if re.search(kw_pattern, text_combined, re.IGNORECASE):
                return source_type

    return "פרטי"


# ============================================================
# Key-value line extractor
# ============================================================

# Maps Hebrew labels found in emails/documents to our internal field keys
# Includes patterns for both normal and medical record formats
FIELD_LABEL_MAP = {
    # Plaintiff name - multiple formats from real medical docs
    "plaintiff_name": [
        r"שם\s*(?:ה?תובע|ה?נפגע|ה?מבוטח|ה?לקוח|ה?נבדק|ה?נפגע|ה?חולה|ה?מטופל|ה?פונה)",
        r"שם\s*מלא",
        r"שם\s*פרטי\s*(?:ו?משפחה)?",
        r"שם\s*משפחה\s*ופרטי",       # Medical record format
        r"שםמשפחהופרטי",              # Reversed PDF concatenated format
        r"פרטי\s*ומשפחה\s*שם",        # Reversed: שם משפחה ופרטי
        r"הנדון",
        r"בעניין",
        r"שם\s+:",                    # "שם :" in medical records (require space before colon)
        r"פרטי\s*ה?מטופל",
        r"re:",
        r"subject\s*name",
        r"patient\s*name",
        r"claimant",
    ],
    # Plaintiff ID - including medical record formats
    "plaintiff_id": [
        r"ת\.?ז\.?",
        r"תעודת\s*זהות",
        r"מספר\s*זהות",
        r"ת\.?זהות",
        r"מ\.?ז\.?",
        r"זהות\s*מס",          # "זהות מס" format from medical records
        r"תוהז\s*סמ",          # Reversed Hebrew from PDFs: "מס זהות"
        r"ID",
        r"identity",
    ],
    # Opposing party
    "opposing_party": [
        r"צד\s*שכנגד",
        r"(?:ה?)נתבע(?:ת|ים)?",
        r"(?:ה?)משיב(?:ה|ים)?",
        r"חברת?\s*ה?ביטוח(?:\s*ה?נתבעת)?",
        r"נגד",
        r"vs\.?",
        r"defendant",
        r"respondent",
    ],
    # Case / claim number
    "claim_number": [
        r"מספר\s*תיק",
        r"מס['\.]?\s*תיק",
        r"ת\.?א\.?",
        r"ת\.?ק\.?",
        r"מספר\s*תביעה",
        r"מס['\.]?\s*תביעה",
        r"מספר\s*אסמכתא",
        r"מספר\s*פוליסה",
        r"case\s*(?:no|number|#)",
        r"claim\s*(?:no|number|#)",
        r"file\s*(?:no|number|#)",
        r"ref(?:erence)?\.?\s*(?:no|number|#)?",
    ],
    # Date of incident
    "incident_date": [
        r"תאריך\s*(?:ה?)(?:אירוע|תאונה|פגיעה|אשפוז|ניתוח)",
        r"מועד\s*(?:ה?)(?:אירוע|תאונה|פגיעה)",
        r"date\s*of\s*(?:incident|accident|injury)",
    ],
    # Birth date
    "birth_date": [
        r"תאריך\s*לידה",
        r"ת\.?\s*לידה",
        r"יליד(?:ת)?",
        r"date\s*of\s*birth",
        r"DOB",
    ],
    # Phone
    "plaintiff_phone": [
        r"טלפון(?:\s*ה?(?:תובע|נפגע|לקוח|מטופל))?",
        r"נייד",
        r"סלולרי",
        r"טל\.?",
        r"phone",
        r"mobile",
        r"cell",
    ],
    # Address
    "plaintiff_address": [
        r"כתובת(?:\s*ה?(?:תובע|נפגע|לקוח|מטופל))?",
        r"מען",
        r"address",
    ],
    # Requested opinion type
    "opinion_type": [
        r"סוג\s*(?:ה?)חוו[\"״\']?ד",
        r"תחום\s*(?:ה?)חוו",
        r"סוג\s*(?:ה?)חוות\s*(?:ה?)דעת",
        r"תחום",
        r"specialty",
        r"type\s*of\s*opinion",
    ],
}


def _extract_field_value(text, patterns):
    """Try to extract a value from text using label:value patterns.

    Handles multiple formats from medical/legal documents:
      - "label: value"
      - "label - value"
      - "label   value"  (tab or multiple spaces after label)
      - Inline: "שם : רונן אלעד"
      - Table: "שם התובע | ערך"

    Stops extraction at the next label to avoid grabbing too much.
    """
    # Common labels that signal "end of current value"
    STOP_LABELS = (
        r'(?:ת\.?ז\.?|מס\s*זהות|תוהז\s*סמ|גיל|מין|ליג|ןימ|'
        r'שם|םש|כתובת|תבותכ|טלפון|ןופלט|תאריך|ךיראת|'
        r'ת\.?לידה|הדיל\.ת|סיבת|תביס|רופא|אפור|'
        r'מספר|רפסמ|סטטוס|תחום|ID)'
    )

    for pattern in patterns:
        # Pattern: label followed by separator then value
        regex = (
            r'(?:^|\n|\r|>|;|\|)\s*'           # line start or after separator
            + pattern                            # the label
            + r'\s*[:;\-–—\t]\s*'                # separator
            + r'([^\n\r<]{2,80})'                # value (2-80 chars, not crossing line)
        )
        match = re.search(regex, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()

            # Truncate at the next field label (prevents grabbing "שם: X מס זהות: Y")
            stop_match = re.search(STOP_LABELS + r'\s*[:;\-–—\t]', value, re.IGNORECASE)
            if stop_match:
                value = value[:stop_match.start()]

            # Clean trailing punctuation and whitespace
            value = re.sub(r'[\s,;:.\-–—]+$', '', value)
            # Remove HTML remnants
            value = re.sub(r'<[^>]+>', '', value)
            value = value.strip()
            if value and len(value) >= 2:
                return value

    return ""


def _extract_key_value_pairs(text):
    """Extract all recognized fields from the email text."""
    results = {}
    for field_key, patterns in FIELD_LABEL_MAP.items():
        value = _extract_field_value(text, patterns)
        if value:
            results[field_key] = value
    return results


# ============================================================
# Specialized extractors (fallbacks when key-value parsing fails)
# ============================================================

def extract_id_number(text):
    """Extract Israeli ID number (9 digits) from text.

    Handles various formats found in medical/legal documents:
    - 012345678
    - 1-03440437/6  (medical system format: check-digit/formatted)
    - 987654321
    - 00098765432   (zero-padded 11 digits)
    - 123-456-789
    """
    # Look for ID near a label first (highest confidence)
    label_patterns = [
        r'(?:ת\.?ז\.?|תעודת\s*זהות|מספר\s*זהות|מס\s*זהות|תוהז\s*סמ|ID)',
    ]
    for lp in label_patterns:
        # Format: "ת.ז. 1-03440437/6" (medical HMO format)
        labeled = re.search(
            lp + r'\s*[:;\-–—\s]\s*(\d[\d\-/]{7,14}\d)',
            text, re.IGNORECASE
        )
        if labeled:
            raw_id = labeled.group(1)
            # Extract just the digits
            digits = re.sub(r'[^\d]', '', raw_id)
            # Take last 9 digits (handles zero-padded and check-digit prefix)
            if len(digits) >= 9:
                return digits[-9:]
            return digits

    # 11-digit zero-padded format: 00098765432 -> 987654321
    matches = re.findall(r'\b(0{1,2}\d{9})\b', text)
    if matches:
        digits = matches[0].lstrip('0')
        digits = digits.zfill(9)  # Ensure 9 digits
        return digits

    # Standalone 9-digit number
    matches = re.findall(r'\b(\d{9})\b', text)
    for m in matches:
        if _validate_israeli_id(m):
            return m

    # With dashes: 123-456-789
    matches = re.findall(r'\b(\d{3}-\d{3}-\d{3})\b', text)
    if matches:
        clean = matches[0].replace("-", "")
        return clean

    # Any 9-digit number (less strict - no validation)
    if matches := re.findall(r'\b(\d{9})\b', text):
        return matches[0]

    return ""


def _validate_israeli_id(id_str):
    """Validate an Israeli ID number using the check digit algorithm."""
    if len(id_str) != 9 or not id_str.isdigit():
        return False
    total = 0
    for i, digit in enumerate(id_str):
        val = int(digit) * ((i % 2) + 1)
        if val > 9:
            val -= 9
        total += val
    return total % 10 == 0


# Common Hebrew first names for splitting concatenated text like "דןמשה" → "דן", "משה"
# Sorted by length descending so longer matches are preferred (e.g., "אילן" before "אי")
COMMON_HEBREW_FIRST_NAMES = {
    # Male names
    "אבי", "אביב", "אביה", "אביעד", "אבישי", "אביתר", "אברהם", "אבנר",
    "אדם", "אדיר", "אהוד", "אהרון", "אהרן", "אופיר", "אופק", "אור",
    "אורי", "אוריה", "אורן", "אחיה", "איתי", "איתם", "איתמר", "איתן",
    "אילן", "אילי", "אילון", "אלון", "אלי", "אליאב", "אליאל", "אליהו",
    "אליה", "אליחי", "אלימלך", "אליעזר", "אליצור", "אלישע", "אלישיב",
    "אלעד", "אלקנה", "אלרון", "אסא", "אסף", "אפרים", "אראל", "ארז",
    "ארי", "אריאל", "אריה", "אריק", "אשר", "אתי", "בועז", "בן",
    "בני", "בנימין", "ברוך", "ברק", "גבריאל", "גד", "גדעון", "גיא",
    "גיל", "גילי", "גילעד", "גלעד", "גרשון", "דב", "דביר", "דוד", "דור",
    "דודי", "דולב", "דן", "דני", "דניאל", "דקל", "דר", "דרור",
    "האני", "הדר", "הוד", "הראל", "זאב", "זוהר", "זיו", "חזי",
    "חי", "חיים", "חנן", "חנניה", "טל", "טום", "טוביה", "יאיר",
    "יבגני", "יגאל", "יגל", "יהב", "יהוד", "יהודה", "יהונתן", "יהושע",
    "יואב", "יואל", "יוחאי", "יואש", "יוחנן", "יוני", "יונתן",
    "יוסי", "יוסף", "יורם", "יותם", "יזהר", "יחיאל", "ינאי", "יניב",
    "יסי", "יעקב", "יפתח", "יצחק", "יקיר", "יקותיאל", "ירדן", "ירון",
    "יריב", "ישי", "ישראל", "כפיר", "לאון", "לב", "ליאם", "ליאור",
    "ליאון", "ליעם", "מאור", "מאיר", "מאיה", "מהאר", "מוטי", "מוסי",
    "מוטל", "מולי", "מורדכי", "מורן", "מורי", "מושיק", "מטר",
    "מיכאל", "מירון", "מנחם", "מנשה", "מסעוד", "מתן", "מתי", "מתניה",
    "משה", "נדב", "נהוראי", "נהיר", "נוח", "נוי", "נחום", "נחמן",
    "נחשון", "נטע", "ניב", "ניל", "ניצן", "ניר", "נמרוד", "נסים",
    "נפתלי", "נתן", "נתנאל", "סיני", "סער", "עדי", "עוז", "עוזי",
    "עומר", "עוז", "עידו", "עידן", "עינב", "עמוס", "עמיר", "עמית",
    "עציון", "פלג", "פנחס", "פסח", "פרי", "פרץ", "צבי", "צביקה",
    "צוק", "צח", "צחי", "צליל", "ציון", "צפניה", "קובי", "קלמן",
    "קרן", "ראובן", "רביב", "רגב", "רובי", "רומי", "רון", "רוני",
    "רוי", "רועי", "רותם", "רחמים", "רחבעם", "ריאן", "ריצ'רד", "רן",
    "רני", "רפי", "רפאל", "רפאלי", "רענן", "רפאל", "שאול", "שגב",
    "שגיא", "שובל", "שי", "שיר", "שלום", "שלמה", "שלו", "שלהבת",
    "שמואל", "שמעון", "שמרי", "שמעיה", "שמשון", "שניר", "שניאור",
    "שריאל", "תאום", "תהילה", "תום", "תומר", "תקווה",
    # Female names
    "אביגיל", "אביה", "אביטל", "אבישג", "אדוה", "אהובה", "איילת",
    "איילה", "אילנה", "אילנית", "אירית", "אלה", "אליאן", "אליאנה",
    "אליה", "אליסף", "אלישבע", "אלמוג", "אסתר", "אפרת", "אריאלה",
    "ארנה", "אתי", "באלי", "ביינה", "בילי", "בלהה", "בני", "בת",
    "בתאל", "בתיה", "גאיה", "גאל", "גאלית", "גוני", "גלית", "דנה",
    "דבורה", "דורית", "דליה", "דליה", "דנייאלה", "הגר", "הדס",
    "הדסה", "הילה", "הילי", "הלל", "ויקי", "ויקטוריה", "ורד",
    "ורדה", "זהבה", "זוהר", "זמירה", "חביבה", "חוה", "חולדה",
    "חניתה", "חנה", "טליה", "טלי", "יהודית", "יאילה", "יעל",
    "יעלה", "יערה", "יפה", "ירדן", "ירדנה", "כרמית", "כרמלה",
    "לאה", "לי", "ליאת", "ליבי", "לימור", "ליעת", "מאי", "מאיה",
    "מאשה", "מיכל", "מירב", "מירה", "מלכה", "מנוחה", "מרגלית",
    "מרים", "משכית", "נאוה", "נאומי", "נעמה", "נטלי", "ניבה",
    "ניצן", "נירית", "נעמי", "נופר", "נוית", "נוף", "סיגל",
    "סיון", "ספיר", "עדינה", "עדן", "ענב", "ענת", "עפרה", "פנינה",
    "פנינית", "פרידה", "פאני", "פסיה", "צביה", "צילה", "צופית",
    "ציפי", "ציפורה", "קרן", "רהל", "רחל", "רחלי", "ריקה", "רימון",
    "רינה", "רונית", "רותי", "רותם", "רקפת", "שגית", "שולמית",
    "שושנה", "שירה", "שירלי", "שלומית", "שני", "שרה", "שרי",
    "שרית", "שלי", "תהילה", "תאיר", "תמי", "תמר", "תקווה",
    # Arabic / non-Jewish names common in Israel
    "מוחמד", "מחמוד", "אחמד", "עומר", "עלי", "חסן", "חוסיין",
    "אבראהים", "אברהים", "אדם", "אסלאם", "אמיר", "אנואר", "באסל",
    "ג'מאל", "האני", "ויסאם", "זיאד", "חאלד", "טארק", "טאלב",
    "כרים", "ליית", "מאהר", "מאלכ", "מוסטפא", "מוניר", "מועתז",
    "מנסור", "סאלם", "סאמי", "סאמר", "סלאח", "סלים", "סלימאן",
    "פאדי", "פאיז", "צאלח", "קארם", "ראאד", "רמזי", "שאדי",
    "שריף", "תאמר", "אסמא", "ולאא", "ימאמה", "מאיסה", "מהא",
    "מנאר", "סמאח", "פאטמה", "פדואא", "ראניה", "רים", "רנא",
    "ריהאם", "ראויה", "סארה", "סאלי", "ריטה", "תמרה",
    # Western names sometimes used
    "אלכס", "אלכסנדר", "אלברט", "אנדריי", "ארווין", "ארתור",
    "בוריס", "ויקטור", "ולדימיר", "ויטלי", "ויליאם", "טוני",
    "ג'ון", "ג'ק", "ג'ורג'", "כריס", "מארק", "מייקל", "סטיב",
    "סטפן", "פול", "פיטר", "פיליפ", "רוברט", "רומן", "סם",
}


def _split_name(full_name):
    """Split a full name into (first_name, last_name).

    Handles:
    - "אבי כהן" → ("אבי", "כהן")
    - "דןמשה" → ("דן", "משה") via known first names
    - "ישראל ישראלי" → ("ישראל", "ישראלי")
    - "" or None → ("", "")
    """
    if not full_name:
        return "", ""
    name = full_name.strip()

    # Case 1: has space - split on first space
    if " " in name:
        parts = name.split(None, 1)
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""

    # Case 2: concatenated Hebrew - try matching against known first names
    for first in sorted(COMMON_HEBREW_FIRST_NAMES, key=len, reverse=True):
        if name.startswith(first) and len(name) > len(first):
            rest = name[len(first):].strip()
            if rest and re.search(r'[א-ת]', rest):
                return first, rest

    # Case 3: single word - put it in first_name
    return name, ""


def extract_person_name(text):
    """Extract a Hebrew person name from the email body."""
    # Try labeled patterns first (with separator like : or -)
    name_patterns = [
        r'(?:שם\s*(?:ה?תובע|ה?נפגע|ה?מבוטח|ה?לקוח|ה?נבדק|ה?מטופל|ה?חולה))\s*[:;–\-]\s*([^\n,<]{2,40})',
        r'(?:שם\s*מלא|שם\s*פרטי\s*ומשפחה)\s*[:;–\-]\s*([^\n,<]{2,40})',
        r'(?:הנדון|בעניין)\s*[:;–\-]\s*([^\n,<]{2,40})',
    ]
    # Also try without separator: "את התובע שם שם" / "מייצג את שם שם"
    name_patterns_no_sep = [
        r'(?:את\s+ה?תובע(?:ת)?|מייצג(?:ים)?\s+את)\s+([א-ת]{2,15}\s+[א-ת]{2,15})',
        r'(?:לבדוק\s+את|בעניינ(?:ו|ה)\s+של)\s+([א-ת]{2,15}\s+[א-ת]{2,15})',
    ]
    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            name = re.sub(r'<[^>]+>', '', name).strip()
            name = re.sub(r'\s+', ' ', name)
            # Remove trailing numbers / IDs
            name = re.sub(r'\s*\d{5,}.*$', '', name)
            if len(name) >= 3 and re.search(r'[א-ת]', name):
                return name

    # Try no-separator patterns: "את התובע שם שם"
    for pattern in name_patterns_no_sep:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            if len(name) >= 3:
                return name

    # Pattern: "מר/גב' FirstName LastName" in running text
    honorific = re.search(
        r'(?:מר|גב[\'׳]?|גברת|ד[\"״]ר|פרופ[\'׳]?)\s+([א-ת]{2,15}\s+[א-ת]{2,15})',
        text
    )
    if honorific:
        return honorific.group(1).strip()

    # Subject line: "חוו"ד ... - שם" or "חוות דעת בעניין שם"
    subject_match = re.search(
        r'חוו[\"״\']?ד.*?[-–—]\s*([א-ת]{2,15}\s+[א-ת]{2,15})',
        text
    )
    if subject_match:
        return subject_match.group(1).strip()

    # "התובע: שם" pattern
    plaintiff_label = re.search(
        r'(?:ה?תובע(?:ת)?)\s*[:;–\-]\s*([^\n,<]{2,40})',
        text, re.IGNORECASE
    )
    if plaintiff_label:
        name = plaintiff_label.group(1).strip()
        name = re.sub(r'\s*,?\s*ת\.?ז\.?.*$', '', name)
        name = re.sub(r'<[^>]+>', '', name).strip()
        if len(name) >= 3 and re.search(r'[א-ת]', name):
            return name

    # "שמי X Y" pattern (self-introduction)
    self_intro = re.search(
        r'שמי\s+([א-ת]{2,15}\s+[א-ת]{2,15})',
        text
    )
    if self_intro:
        return self_intro.group(1).strip()

    # "לוי נגד ישראלי" pattern in subject (court cases)
    vs_match = re.search(
        r'([א-ת]{2,15}(?:\s+[א-ת]{2,15})?)\s+נגד\s+',
        text
    )
    if vs_match:
        return vs_match.group(1).strip()

    return ""


def extract_opposing_party(text):
    """Extract the opposing party from the email."""
    patterns = [
        r'(?:צד\s*שכנגד)\s*[:;–\-]\s*([^\n,<]{2,60})',
        r'(?:ה?נתבע(?:ת|ים)?)\s*[:;–\-]\s*([^\n,<]{2,60})',
        r'(?:ה?משיב(?:ה|ים)?)\s*[:;–\-]\s*([^\n,<]{2,60})',
        r'(?:נגד|vs\.?|versus)\s+([^\n,<]{2,60})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.sub(r'<[^>]+>', '', value).strip()
            value = re.sub(r'\s+', ' ', value)
            if len(value) >= 2:
                return value
    return ""


def extract_phone_number(text):
    """Extract an Israeli phone number from text."""
    # Mobile: 05X-XXXXXXX
    match = re.search(r'\b(05\d[\-\s]?\d{3}[\-\s]?\d{4})\b', text)
    if match:
        return match.group(1).strip()
    # Landline: 0X-XXXXXXX
    match = re.search(r'\b(0[2-9][\-\s]?\d{3}[\-\s]?\d{4})\b', text)
    if match:
        return match.group(1).strip()
    return ""


def extract_date(text, patterns):
    """Extract a date near specific label patterns."""
    for pattern in patterns:
        regex = pattern + r'\s*[:;–\-]?\s*(\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4})'
        match = re.search(regex, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


# ============================================================
# Material completeness assessment
# ============================================================

def assess_material_completeness(attachments, body_text):
    """Assess whether the submitted material is complete or partial."""
    if not attachments:
        return "חסר", "לא צורפו מסמכים"

    all_names = " ".join(a.get("filename", "").lower() for a in attachments)
    body_lower = (body_text or "").lower()
    combined = all_names + " " + body_lower

    has_medical = any(kw in combined for kw in [
        "רפואי", "אפיכריז", "סיכום", "מכתב שחרור", "medical",
        "תיק רפואי", "גיליון", "אנמנזה", "בדיקה",
    ])
    has_imaging = any(kw in combined for kw in [
        "הדמיה", "ct", "mri", "אולטרסאונד", "צילום", "רנטגן",
        "סונר", "ultrasound", "x-ray", "scan",
    ])
    has_records = any(kw in combined for kw in [
        "תיעוד", "רישום", "מרשם", "הפניה", "מכתב",
    ])

    found = sum([has_medical, has_imaging, has_records])
    total_files = len(attachments)

    if found >= 2 or (has_medical and total_files >= 3):
        return "מלא", ""
    elif found >= 1 or total_files >= 2:
        missing = []
        if not has_medical:
            missing.append("מסמכים רפואיים")
        if not has_imaging:
            missing.append("בדיקות הדמיה")
        return "חלקי", ", ".join(missing) if missing else ""
    else:
        return "חלקי", "יש לבדוק את המסמכים המצורפים"


# ============================================================
# Main parser
# ============================================================

def parse_email(email_data, attachment_text=""):
    """Parse an email and extract all structured data.

    Uses a multi-layered approach:
    1. Key-value pair extraction from email body (label: value patterns)
    2. Key-value pair extraction from attachments (PDF, Word, etc.)
    3. Specialized regex extractors (fallback)
    4. Source type detection from keywords + sender domain

    Args:
        email_data: dict with subject, sender_name, sender_email, date, body_html, attachments
        attachment_text: pre-extracted text from all attachments (from attachment_parser)

    Returns dict with extracted fields ready for Excel insertion.
    """
    body_html = email_data.get("body_html", "")
    # Strip HTML tags for text analysis
    body_text = re.sub(r'<[^>]+>', ' ', body_html)
    # Normalize whitespace but keep newlines for line-based parsing
    body_text = re.sub(r'[ \t]+', ' ', body_text)
    body_text = re.sub(r'\n\s*\n', '\n', body_text)

    # If attachment_text not provided, try extracting from attachment bytes
    if not attachment_text:
        attachments_with_content = [
            a for a in email_data.get("attachments", []) if a.get("content")
        ]
        if attachments_with_content:
            try:
                from attachment_parser import extract_all_attachments_text
                attachment_text = extract_all_attachments_text(attachments_with_content)
            except Exception as e:
                print(f"[parse_email] Error extracting attachments: {e}")
                attachment_text = ""

    subject = email_data.get("subject", "")
    sender_name = email_data.get("sender_name", "")
    sender_email = email_data.get("sender_email", "")

    # Email text (highest priority for extraction)
    email_text = f"{subject}\n{body_text}"

    # Combined text: email + attachments (for fallback extraction)
    combined_text = email_text
    if attachment_text:
        combined_text = f"{email_text}\n{attachment_text}"

    # --- Layer 1: key-value extraction from email body first ---
    kv_email = _extract_key_value_pairs(email_text)

    # --- Layer 2: key-value extraction from attachments (fill gaps) ---
    kv_attachments = {}
    if attachment_text:
        kv_attachments = _extract_key_value_pairs(attachment_text)

    # Merge: email values take priority, attachment values fill gaps
    kv_pairs = {**kv_attachments, **{k: v for k, v in kv_email.items() if v}}

    # --- Layer 3: Try to extract name from email subject FIRST (highest confidence) ---
    subject_name = ""
    subj_name_patterns = [
        # "... - שם משפחה" at end of subject
        r'[-–—]\s*([א-ת]{2,15}\s+[א-ת]{2,15}(?:\s+[א-ת]{2,15})?)\s*$',
        # "... - שם משפחה NNN" (name followed by case number)
        r'[-–—]\s*([א-ת]{2,15}\s+[א-ת]{2,15}(?:\s+[א-ת]{2,15})?)\s+\d',
        # "מסמכים/חוו"ד ... - שם"
        r'(?:מסמכים|חוו[\"״\']?ד|חוות\s*דעת).*[-–—]\s*([א-ת]{2,15}\s+[א-ת]{2,15})',
        # "מינוי מומחה- שם"
        r'מ[יו][ני]+וי\s+מומחה\s*[-–—]\s*([א-ת]{2,15}\s+[א-ת]{2,15})',
        # "עבור/בעניין/הנדון: שם"
        r'(?:עבור|בעניין|הנדון)\s*:?\s*([א-ת]{2,15}\s+[א-ת]{2,15})',
    ]
    for sp in subj_name_patterns:
        match = re.search(sp, subject)
        if match:
            subject_name = match.group(1).strip()
            break

    # --- Layer 4: key-value and specialized extractors ---
    plaintiff_name = subject_name or kv_pairs.get("plaintiff_name", "") or extract_person_name(combined_text)
    plaintiff_id = kv_pairs.get("plaintiff_id", "") or extract_id_number(combined_text)
    opposing_party = kv_pairs.get("opposing_party", "") or extract_opposing_party(combined_text)

    # --- Clean up extracted values ---

    # Clean plaintiff name: remove trailing IDs, numbers, labels
    if plaintiff_name:
        # Remove "ת.ז. XXXX" from end of name
        plaintiff_name = re.sub(r',?\s*ת\.?ז\.?\s*[\d\-/]+.*$', '', plaintiff_name)
        # Remove trailing numbers (IDs etc)
        plaintiff_name = re.sub(r'\s+\d{5,}.*$', '', plaintiff_name)
        # Remove other field labels that may have leaked in
        plaintiff_name = re.sub(r'\s*(?:מס\s*זהות|תוהז\s*סמ|גיל|ליג|מין|ןימ|תאריך|כתובת|טלפון).*$', '', plaintiff_name, flags=re.IGNORECASE)
        # Remove concatenated reversed labels
        plaintiff_name = re.sub(r'^.*(?:יטרפו|ופרטי)\s*:?\s*', '', plaintiff_name)
        plaintiff_name = plaintiff_name.strip(' ,;:-–—')

    # If name is still too short or garbage, try from subject
    if not plaintiff_name or len(plaintiff_name) < 3 or not re.search(r'[א-ת]', plaintiff_name):
        plaintiff_name = subject_name

    # Split into first/last name
    plaintiff_first_name, plaintiff_last_name = _split_name(plaintiff_name)

    # Clean plaintiff_id: extract 9 digits
    if plaintiff_id:
        digits = re.sub(r'[^\d]', '', plaintiff_id)
        if len(digits) > 9:
            plaintiff_id = digits[-9:]  # Take last 9 digits
        elif len(digits) == 9:
            plaintiff_id = digits
        else:
            plaintiff_id = digits  # Keep whatever we have

    # Source type detection
    source_type = identify_source_type(sender_name, sender_email, subject, body_text)

    # Attachments analysis
    attachments = email_data.get("attachments", [])
    material_status, missing_details = assess_material_completeness(attachments, body_text)

    # Additional fields from kv extraction
    claim_number = kv_pairs.get("claim_number", "")
    # Filter out false positives (bibliography references, long strings)
    if claim_number and (len(claim_number) > 30 or re.search(r'[A-Z][a-z]+\s+[A-Z]', claim_number)):
        claim_number = ""
    incident_date = kv_pairs.get("incident_date", "") or extract_date(
        combined_text,
        [r"תאריך\s*(?:ה?)(?:אירוע|תאונה|פגיעה)", r"מועד\s*(?:ה?)אירוע"]
    )
    birth_date = kv_pairs.get("birth_date", "") or extract_date(
        combined_text,
        [r"תאריך\s*לידה", r"ת\.?\s*לידה", r"יליד(?:ת)?"]
    )
    phone = kv_pairs.get("plaintiff_phone", "") or extract_phone_number(body_text)

    # Map of pre-extracted values available for custom-field matching
    extracted_values = {
        "claim_number": claim_number,
        "incident_date": incident_date,
        "birth_date": birth_date,
        "plaintiff_phone": phone,
        "plaintiff_address": kv_pairs.get("plaintiff_address", ""),
        "opinion_type": kv_pairs.get("opinion_type", ""),
    }

    # Build result starting from schema defaults, then overlay extracted data
    import schema
    result = {key: "" for key in schema.get_all_keys()}
    defaults = schema.get_defaults()
    result.update(defaults)

    # Overlay standard extracted fields
    result.update({
        "date_received": email_data.get("date", "").split(" ")[0],
        "source_type": source_type,
        "sender_name": sender_name,
        "sender_email": sender_email,
        "plaintiff_name": plaintiff_name,
        "plaintiff_first_name": plaintiff_first_name,
        "plaintiff_last_name": plaintiff_last_name,
        "plaintiff_id": plaintiff_id,
        "opposing_party": opposing_party,
        "subject": subject,
        "material_status": material_status,
        "missing_material_details": missing_details,
    })

    # ----- Populate CUSTOM extractable fields by matching their label -----
    # When a user creates a custom field like "תאריך לידה" and marks it
    # extractable, we look at the field's label and try to find matching
    # content in the parsed text or kv_pairs.
    populated_via_custom = set()  # Track which values ended up in dedicated fields

    try:
        all_fields = schema.get_all_fields()
    except Exception:
        all_fields = []

    for f in all_fields:
        if not f.get("extractable"):
            continue
        key = f.get("key", "")
        label = (f.get("label") or "").strip()

        # Skip built-in fields (already populated above)
        if key in ("plaintiff_name", "plaintiff_first_name", "plaintiff_last_name",
                   "plaintiff_id", "opposing_party", "source_type", "sender_name",
                   "sender_email", "subject", "material_status", "missing_material_details"):
            continue

        # Already has a value from the standard extraction
        if result.get(key):
            continue

        # Try to match the label against known extractable info
        value = ""
        norm_label = label.replace(" ", "").replace("\"", "").replace("״", "")

        # 1. Direct kv_pairs lookup by label patterns
        label_patterns_for_label = {
            "תאריךלידה": "birth_date",
            "ת.לידה": "birth_date",
            "יליד": "birth_date",
            "תאריךאירוע": "incident_date",
            "תאריךהאירוע": "incident_date",
            "תאריךתאונה": "incident_date",
            "מועדהאירוע": "incident_date",
            "טלפון": "plaintiff_phone",
            "נייד": "plaintiff_phone",
            "סלולרי": "plaintiff_phone",
            "כתובת": "plaintiff_address",
            "מען": "plaintiff_address",
            "מספרתיק": "claim_number",
            "מספרתביעה": "claim_number",
            "מספרפוליסה": "claim_number",
            "תיק": "claim_number",
            "תביעה": "claim_number",
            "סוגחווד": "opinion_type",
            "תחוםחווד": "opinion_type",
        }
        matched_source = None
        for pat, src in label_patterns_for_label.items():
            if pat in norm_label:
                matched_source = src
                break

        if matched_source and extracted_values.get(matched_source):
            value = extracted_values[matched_source]
            populated_via_custom.add(matched_source)
        elif matched_source == "birth_date":
            # Try extraction directly from text as a last resort
            value = extract_date(combined_text, [r"תאריך\s*לידה", r"ת\.?\s*לידה", r"יליד(?:ת)?"])
            if value:
                populated_via_custom.add("birth_date")

        if value:
            result[key] = value

    # ----- Build notes from extra extracted info NOT already in dedicated fields -----
    notes_parts = []
    if claim_number and "claim_number" not in populated_via_custom:
        notes_parts.append(f"מספר תיק/תביעה: {claim_number}")
    if incident_date and "incident_date" not in populated_via_custom:
        notes_parts.append(f"תאריך אירוע: {incident_date}")
    if birth_date and "birth_date" not in populated_via_custom:
        notes_parts.append(f"תאריך לידה: {birth_date}")
    if phone and "plaintiff_phone" not in populated_via_custom:
        notes_parts.append(f"טלפון: {phone}")
    if kv_pairs.get("plaintiff_address") and "plaintiff_address" not in populated_via_custom:
        notes_parts.append(f"כתובת: {kv_pairs['plaintiff_address']}")
    if kv_pairs.get("opinion_type") and "opinion_type" not in populated_via_custom:
        notes_parts.append(f"סוג חוו\"ד: {kv_pairs['opinion_type']}")

    result["notes"] = " | ".join(notes_parts) if notes_parts else ""

    return result
