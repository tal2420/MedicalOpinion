// Medical Opinion Management - Schema-Driven Frontend
// All UI is generated dynamically from /api/schema - no hardcoded field lists.

let appSchema = null;  // Loaded once from server
let allCases = [];
let currentCase = null;
let scannedEmails = [];

// ===== Schema Loading =====
async function loadSchema() {
    if (appSchema) return appSchema;
    appSchema = await api('/api/schema');
    buildStaticUI();
    return appSchema;
}

function getFields(filter) {
    if (!appSchema) return [];
    return appSchema.fields.filter(filter || (() => true));
}

// ===== Build static UI elements from schema (once) =====
function buildStaticUI() {
    buildDashboardCards();
    buildDashboardTableHead();
    buildCasesTableHead();
    buildFilterDropdowns();
    buildNewCaseForm();
}

function buildDashboardCards() {
    const container = document.getElementById('dashboard-cards');
    container.innerHTML = appSchema.dashboard_counters.map(c =>
        `<div class="stat-card ${c.color}" onclick="showPage('cases')">
            <div class="number" id="stat-${c.name}">0</div>
            <div class="label">${c.label}</div>
        </div>`
    ).join('');
}

function buildDashboardTableHead() {
    const tr = document.getElementById('dashboard-table-head');
    tr.innerHTML = getFields(f => f.in_dashboard).map(f => `<th>${f.label}</th>`).join('');
}

function buildCasesTableHead() {
    const tr = document.getElementById('cases-table-head');
    const cols = getFields(f => f.in_table);
    tr.innerHTML = cols.map(f => `<th>${f.label}</th>`).join('') + '<th>פעולות</th>';
}

function buildFilterDropdowns() {
    const container = document.getElementById('filter-dropdowns');
    // Create a filter dropdown for each select-type field shown in table
    const filterFields = getFields(f => f.in_table && f.type === 'select' && f.options);
    container.innerHTML = filterFields.map(f =>
        `<select class="filter-select" data-filter-key="${f.key}" onchange="filterCases()">
            <option value="">${f.label} - הכל</option>
            ${f.options.map(o => `<option value="${o}">${o}</option>`).join('')}
        </select>`
    ).join('');
}

function buildNewCaseForm() {
    const container = document.getElementById('new-case-fields');
    const fields = getFields(f => f.in_new_form);
    let html = '<div class="form-row">';
    fields.forEach((f, i) => {
        if (i > 0 && i % 2 === 0) html += '</div><div class="form-row">';
        html += `<div class="form-group">`;
        html += `<label>${f.label}${f.required ? ' *' : ''}</label>`;
        html += renderFormInput(f, '', `new-${f.key}`, f.required);
        html += '</div>';
    });
    html += '</div>';
    container.innerHTML = html;
}

// ===== Form Input Renderer =====
function renderFormInput(field, value, idPrefix, required) {
    const id = idPrefix || `field-${field.key}`;
    const val = value || '';
    const req = required ? 'required' : '';

    if (field.type === 'select' && field.options) {
        return `<select name="${field.key}" id="${id}" ${req}>
            ${field.options.map(o => `<option value="${o}" ${val == o ? 'selected' : ''}>${o}</option>`).join('')}
        </select>`;
    } else if (field.type === 'textarea') {
        return `<textarea name="${field.key}" id="${id}" ${req}>${val}</textarea>`;
    } else {
        return `<input type="${field.type === 'number' ? 'number' : field.type === 'email' ? 'email' : 'text'}" name="${field.key}" id="${id}" value="${val}" ${req}>`;
    }
}

// ===== Navigation =====
function showPage(pageId) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + pageId).classList.add('active');
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const navItems = document.querySelectorAll('.nav-item');
    const pageMap = { 'dashboard': 0, 'cases': 1, 'email-scan': 2, 'new-case': 3, 'settings': 4 };
    if (pageMap[pageId] !== undefined) navItems[pageMap[pageId]].classList.add('active');

    if (pageId === 'dashboard') loadDashboard();
    if (pageId === 'cases') loadCases();
    if (pageId === 'settings') loadSettings();

    // Track page view (fire-and-forget)
    fetch('/api/telemetry/track', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ event: 'page_view', properties: { page: pageId } })
    }).catch(() => {});
}

// ===== Toast =====
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ===== API Helper =====
async function api(url, options = {}) {
    try {
        const resp = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'Server error');
        return data;
    } catch (e) {
        showToast(e.message, 'error');
        throw e;
    }
}

// ===== Status Badge (schema-driven) =====
function statusBadge(value) {
    if (!value) return '<span class="badge badge-info">-</span>';
    const colors = appSchema ? appSchema.status_colors : {};
    const cls = colors[value] || 'info';
    return `<span class="badge badge-${cls}">${value}</span>`;
}

function isStatusField(key) {
    if (!appSchema) return false;
    const field = appSchema.fields.find(f => f.key === key);
    return field && field.is_status;
}

function cellValue(c, field) {
    const val = c[field.key] || '-';
    if (field.is_status || field.colors) return statusBadge(c[field.key]);
    if (field.key === 'plaintiff_name') return `<strong>${val}</strong>`;
    if (field.key === 'agreed_amount' && c[field.key]) return `₪${Number(c[field.key]).toLocaleString()}`;
    return val;
}

// ===== Dashboard =====
async function loadDashboard() {
    try {
        const stats = await api('/api/dashboard');
        for (const [name, value] of Object.entries(stats)) {
            const el = document.getElementById('stat-' + name);
            if (el) el.textContent = value;
        }

        const cases = await api('/api/cases');
        allCases = cases;
        const recent = cases.slice(0, 10);
        const dashFields = getFields(f => f.in_dashboard);
        const tbody = document.getElementById('recent-cases-body');
        tbody.innerHTML = recent.map(c =>
            `<tr onclick="viewCase(${c.case_number})">${dashFields.map(f => `<td>${cellValue(c, f)}</td>`).join('')}</tr>`
        ).join('');
        if (!recent.length) {
            tbody.innerHTML = `<tr><td colspan="${dashFields.length}" style="text-align:center;padding:30px;color:var(--text-muted)">אין תיקים עדיין</td></tr>`;
        }
    } catch (e) { /* toast shown */ }
}

// ===== Cases List =====
async function loadCases() {
    try {
        allCases = await api('/api/cases');
        renderCasesTable(allCases);
    } catch (e) { /* toast shown */ }
}

function renderCasesTable(cases) {
    const tableCols = getFields(f => f.in_table);
    const tbody = document.getElementById('cases-body');
    tbody.innerHTML = cases.map(c =>
        `<tr onclick="viewCase(${c.case_number})">
            ${tableCols.map(f => `<td>${cellValue(c, f)}</td>`).join('')}
            <td>
                <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation(); editCase(${c.case_number})" title="עריכה">&#9998;</button>
                <button class="btn btn-sm btn-ghost" onclick="event.stopPropagation(); deleteCase(${c.case_number})" title="מחיקה" style="color:var(--danger)">&#10005;</button>
            </td>
        </tr>`
    ).join('');
    if (!cases.length) {
        tbody.innerHTML = `<tr><td colspan="${tableCols.length + 1}" style="text-align:center;padding:30px;color:var(--text-muted)">לא נמצאו תיקים</td></tr>`;
    }
}

function filterCases() {
    const search = document.getElementById('search-input').value.toLowerCase();
    const filterSelects = document.querySelectorAll('[data-filter-key]');
    const filters = {};
    filterSelects.forEach(sel => { if (sel.value) filters[sel.dataset.filterKey] = sel.value; });

    let filtered = allCases.filter(c => {
        const matchSearch = !search || Object.values(c).some(v => String(v).toLowerCase().includes(search));
        const matchFilters = Object.entries(filters).every(([key, val]) => c[key] === val);
        return matchSearch && matchFilters;
    });
    renderCasesTable(filtered);
}

// ===== Case Detail (schema-driven) =====
async function viewCase(caseNumber) {
    try {
        const c = await api('/api/cases/' + caseNumber);
        currentCase = c;
        const fullName = c.plaintiff_name || [c.plaintiff_first_name, c.plaintiff_last_name].filter(Boolean).join(' ') || 'ללא שם';
        document.getElementById('case-detail-title').textContent = `תיק מס׳ ${c.case_number} - ${fullName}`;

        const groups = appSchema.groups;
        const leftGroups = ['info', 'call', 'payment'];
        const rightGroups = ['status'];

        // Build left column
        let leftHtml = '';
        for (const gKey of leftGroups) {
            const gFields = getFields(f => f.group === gKey && f.key !== 'folder_path');
            if (!gFields.length) continue;
            leftHtml += `<div class="detail-section" style="margin-bottom:16px">
                <h3>${groups[gKey]}</h3>
                ${gFields.map(f => {
                    let val = c[f.key] || '-';
                    if (f.is_status || f.colors) val = statusBadge(c[f.key]);
                    else if (f.key === 'agreed_amount' && c[f.key]) val = `₪${Number(c[f.key]).toLocaleString()}`;
                    return `<div class="detail-row"><span class="label">${f.label}:</span><span>${val}</span></div>`;
                }).join('')}
                ${gKey === 'info' ? '<div class="detail-actions"><button class="btn btn-sm btn-outline" onclick="editCase(' + c.case_number + ')">&#9998; עריכת פרטים</button></div>' : ''}
            </div>`;
        }
        document.getElementById('case-detail-left').innerHTML = leftHtml;

        // Build right column
        let rightHtml = '';
        for (const gKey of rightGroups) {
            const gFields = getFields(f => f.group === gKey);
            if (!gFields.length) continue;
            rightHtml += `<div class="detail-section" style="margin-bottom:16px">
                <h3>${groups[gKey]}</h3>
                ${gFields.map(f => {
                    let val = c[f.key] || '-';
                    if (f.is_status || f.colors) val = statusBadge(c[f.key]);
                    return `<div class="detail-row"><span class="label">${f.label}:</span><span>${val}</span></div>`;
                }).join('')}
            </div>`;
        }

        // Attachments section
        rightHtml += `<div class="detail-section" style="margin-bottom:16px">
            <h3>מסמכים מצורפים</h3>
            <div id="case-attachments"></div>
            <div class="detail-actions" style="margin-top:8px">
                <button class="btn btn-sm btn-outline" onclick="rescanAttachments()" id="rescan-btn">&#128270; סרוק מצורפים לחילוץ פרטים</button>
            </div>
        </div>`;

        // Opinions section
        rightHtml += `<div class="detail-section">
            <h3>חוות דעת</h3>
            <div id="case-opinions"></div>
            <div class="detail-actions">
                <button class="btn btn-primary" onclick="generateOpinion()">&#128196; צור חוו"ד</button>
                <button class="btn btn-success" onclick="showSendModal()">&#9993; שלח חוו"ד</button>
            </div>
        </div>`;

        document.getElementById('case-detail-right').innerHTML = rightHtml;
        loadCaseFiles(caseNumber);
        showPage('case-detail');
    } catch (e) { /* toast shown */ }
}

function _escapeHtml(s) {
    return String(s || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function fileItemHtml(f, icon, kind) {
    // Use data-filename + data-kind so the server resolves the path itself.
    // This avoids ALL escaping issues with Hebrew paths, spaces, quotes etc.
    return `<div class="file-item file-item-clickable" data-filename="${_escapeHtml(f.name)}" data-kind="${kind}" title="לחץ לפתיחה">
        <span class="file-icon">${icon}</span>
        <span class="file-name">${_escapeHtml(f.name)}</span>
        <span class="file-size">${formatSize(f.size)}</span>
    </div>`;
}

async function openCaseFile(caseNumber, filename, kind) {
    if (!filename) { showToast('שם קובץ חסר', 'error'); return; }
    try {
        await api('/api/open-file', {
            method: 'POST',
            body: JSON.stringify({ case_number: caseNumber, filename, kind }),
        });
    } catch (e) { /* toast shown */ }
}

function _attachFileClickHandlers(container, caseNumber) {
    container.querySelectorAll('.file-item-clickable').forEach(el => {
        el.addEventListener('click', () => {
            const filename = el.getAttribute('data-filename');
            const kind = el.getAttribute('data-kind');
            openCaseFile(caseNumber, filename, kind);
        });
    });
}

async function loadCaseFiles(caseNumber) {
    try {
        const files = await api('/api/cases/' + caseNumber + '/files');
        const attachDiv = document.getElementById('case-attachments');
        attachDiv.innerHTML = (files.attachments && files.attachments.length)
            ? '<div class="file-list">' + files.attachments.map(f => fileItemHtml(f, '&#128196;', 'attachment')).join('') + '</div>'
            : '<p style="color:var(--text-muted);font-size:13px">אין מסמכים מצורפים</p>';
        _attachFileClickHandlers(attachDiv, caseNumber);

        const opinDiv = document.getElementById('case-opinions');
        opinDiv.innerHTML = (files.opinions && files.opinions.length)
            ? '<div class="file-list">' + files.opinions.map(f => fileItemHtml(f, '&#128209;', 'opinion')).join('') + '</div>'
            : '<p style="color:var(--text-muted);font-size:13px">טרם נוצרה חוות דעת</p>';
        _attachFileClickHandlers(opinDiv, caseNumber);
    } catch (e) { /* toast shown */ }
}

function formatSize(bytes) {
    if (!bytes) return '';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ===== Create Case =====
async function submitNewCase(e) {
    e.preventDefault();
    const form = document.getElementById('new-case-form');
    const data = Object.fromEntries(new FormData(form).entries());
    try {
        const result = await api('/api/cases', { method: 'POST', body: JSON.stringify(data) });
        showToast(`תיק מס׳ ${result.case_number} נוצר בהצלחה`, 'success');
        form.reset();
        viewCase(result.case_number);
    } catch (e) { /* toast shown */ }
}

// ===== Edit Case (schema-driven) =====
function editCase(caseNumber) {
    const c = allCases.find(x => x.case_number == caseNumber) || currentCase;
    if (!c) return;

    const editableFields = getFields(f => f.editable);
    let html = `<input type="hidden" id="edit-case-number" value="${c.case_number}">`;
    html += '<div class="form-row">';
    editableFields.forEach((f, i) => {
        if (i > 0 && i % 2 === 0) html += '</div><div class="form-row">';
        html += `<div class="form-group"><label>${f.label}</label>`;
        html += renderFormInput(f, c[f.key] || '', `edit-${f.key}`, false);
        html += '</div>';
    });
    html += '</div>';

    document.getElementById('edit-modal-body').innerHTML = html;
    document.getElementById('edit-modal').classList.add('active');
}

function closeEditModal() { document.getElementById('edit-modal').classList.remove('active'); }

async function saveEditedCase() {
    const caseNumber = document.getElementById('edit-case-number').value;
    const editableFields = getFields(f => f.editable);
    const data = {};
    editableFields.forEach(f => {
        const el = document.getElementById('edit-' + f.key);
        if (el) data[f.key] = el.value;
    });
    try {
        await api('/api/cases/' + caseNumber, { method: 'PUT', body: JSON.stringify(data) });
        showToast('התיק עודכן בהצלחה', 'success');
        closeEditModal();
        viewCase(caseNumber);
    } catch (e) { /* toast shown */ }
}

// ===== Delete Case =====
async function deleteCase(caseNumber) {
    if (!confirm(`האם למחוק את תיק מס׳ ${caseNumber}?`)) return;
    try {
        await api('/api/cases/' + caseNumber, { method: 'DELETE' });
        showToast('התיק נמחק', 'success');
        loadCases();
    } catch (e) { /* toast shown */ }
}

// ===== Rescan Attachments =====
async function rescanAttachments() {
    if (!currentCase) return;
    const btn = document.getElementById('rescan-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> סורק מצורפים...';
    try {
        const result = await api('/api/cases/' + currentCase.case_number + '/rescan', { method: 'POST' });
        if (result.updated_fields && result.updated_fields.length > 0) {
            // Use schema labels for display
            const labels = {};
            appSchema.fields.forEach(f => labels[f.key] = f.label);
            const updated = result.updated_fields.map(f => labels[f] || f).join(', ');
            showToast('עודכנו שדות: ' + updated, 'success');
            viewCase(currentCase.case_number);
        } else {
            showToast(result.message || 'לא נמצא מידע חדש במצורפים', 'info');
        }
    } catch (e) { /* toast shown */ }
    btn.disabled = false;
    btn.innerHTML = '&#128270; סרוק מצורפים לחילוץ פרטים';
}

// ===== Generate Opinion =====
async function generateOpinion() {
    if (!currentCase) return;
    try {
        await api('/api/cases/' + currentCase.case_number + '/generate', { method: 'POST' });
        showToast('חוות הדעת נוצרה בהצלחה', 'success');
        loadCaseFiles(currentCase.case_number);
    } catch (e) { /* toast shown */ }
}

// ===== Send Opinion =====
function showSendModal() {
    if (!currentCase) return;
    document.getElementById('send-to').value = currentCase.sender_email || '';
    const fullName = currentCase.plaintiff_name || [currentCase.plaintiff_first_name, currentCase.plaintiff_last_name].filter(Boolean).join(' ') || '';
    document.getElementById('send-subject').value = `חוות דעת רפואית - ${fullName}`;
    api('/api/cases/' + currentCase.case_number + '/files').then(files => {
        const select = document.getElementById('send-attachment');
        select.innerHTML = '<option value="">ללא קובץ מצורף</option>';
        if (files.opinions) files.opinions.forEach(f => { select.innerHTML += `<option value="${f.path}">${f.name}</option>`; });
    });
    document.getElementById('send-modal').classList.add('active');
}
function closeSendModal() { document.getElementById('send-modal').classList.remove('active'); }

async function sendOpinionEmail() {
    const to = document.getElementById('send-to').value;
    const subject = document.getElementById('send-subject').value;
    const body = document.getElementById('send-body').value;
    const attachment = document.getElementById('send-attachment').value;
    if (!to) { showToast('יש להזין כתובת נמען', 'error'); return; }
    try {
        await api('/api/send-email', { method: 'POST', body: JSON.stringify({ case_number: currentCase.case_number, to, subject, body: body.replace(/\n/g, '<br>'), attachment_path: attachment }) });
        showToast('חוות הדעת נשלחה בהצלחה', 'success');
        closeSendModal();
        viewCase(currentCase.case_number);
    } catch (e) { /* toast shown */ }
}

// ===== Open Folder =====
async function openCaseFolder() {
    if (!currentCase || !currentCase.folder_path) { showToast('לא נמצא נתיב תיקייה', 'error'); return; }
    try { await api('/api/open-folder', { method: 'POST', body: JSON.stringify({ path: currentCase.folder_path }) }); } catch (e) { /* toast shown */ }
}

// ===== Email Scanning =====
async function scanEmails() {
    const btn = document.getElementById('scan-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> סורק...';

    // Read filter controls
    const days = document.getElementById('scan-days').value;
    const unreadOnly = document.getElementById('scan-unread').value;
    const max = document.getElementById('scan-max').value;
    const url = `/api/emails/scan?days=${days}&unread_only=${unreadOnly}&max=${max}`;

    try {
        const emails = await api(url);
        // Sort by date descending (newest first) - parse DD/MM/YYYY HH:MM
        emails.sort((a, b) => {
            const parseD = d => { const p = (d||'').split(/[\s/:-]+/); return p.length>=5 ? new Date(p[2],p[1]-1,p[0],p[3],p[4]) : new Date(0); };
            return parseD(b.date) - parseD(a.date);
        });
        scannedEmails = emails;
        document.getElementById('email-search-input').value = '';
        renderScannedEmails(emails);
        document.getElementById('import-btn').disabled = false;
        document.getElementById('import-progress').style.display = 'none';
    } catch (e) { /* toast shown */ }
    btn.disabled = false;
    btn.innerHTML = '&#128269; סרוק תיבת דואר';
}

function renderScannedEmails(emails) {
    const container = document.getElementById('email-list-container');
    if (!emails.length) {
        container.innerHTML = '<div class="empty-state"><div class="icon">&#10003;</div><h3>לא נמצאו מיילים</h3><p>נסה להרחיב את טווח הזמן או להחליף ל"כל המיילים"</p></div>';
        return;
    }
    container.innerHTML = '<div class="email-list" id="email-list">' + emails.map((e, i) => {
        // Use the original index in scannedEmails so checkbox data-index stays correct
        const origIdx = scannedEmails.indexOf(e);
        return `<div class="email-item" data-email-index="${origIdx}" onclick="toggleEmailSelect(${origIdx}, this)">
            <input type="checkbox" class="email-checkbox" data-index="${origIdx}">
            <div class="email-content">
                <div class="email-subject">${_escapeHtml(e.subject || '(ללא נושא)')}</div>
                <div class="email-sender">${_escapeHtml(e.sender_name)} &lt;${_escapeHtml(e.sender_email)}&gt;</div>
                <div class="email-date">${e.date}</div>
                ${e.attachments && e.attachments.length ? `<div class="email-attachments">&#128206; ${e.attachments.length} קבצים מצורפים</div>` : ''}
            </div>
            <div class="email-status-icon pending" id="email-status-${origIdx}" style="display:none">⋯</div>
        </div>`;
    }).join('') + '</div>';
    const badge = document.getElementById('email-badge');
    badge.textContent = scannedEmails.length;
    badge.style.display = 'inline';
}

function filterScannedEmails() {
    const q = (document.getElementById('email-search-input').value || '').toLowerCase().trim();
    if (!q) { renderScannedEmails(scannedEmails); return; }
    const filtered = scannedEmails.filter(e =>
        (e.subject || '').toLowerCase().includes(q) ||
        (e.sender_name || '').toLowerCase().includes(q) ||
        (e.sender_email || '').toLowerCase().includes(q) ||
        (e.date || '').includes(q)
    );
    renderScannedEmails(filtered);
}

function toggleEmailSelect(index, element) {
    const cb = element.querySelector('.email-checkbox');
    cb.checked = !cb.checked;
    element.classList.toggle('selected', cb.checked);
}

async function importSelectedEmails() {
    const checkboxes = document.querySelectorAll('.email-checkbox:checked');
    if (!checkboxes.length) { showToast('יש לבחור לפחות מייל אחד', 'error'); return; }

    const selectedIndices = Array.from(checkboxes).map(cb => parseInt(cb.dataset.index));
    const selectedEmails = selectedIndices.map(i => scannedEmails[i]);

    // Show progress UI
    const progressEl = document.getElementById('import-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const progressTitle = document.getElementById('progress-title');
    progressEl.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'מתחיל...';
    progressTitle.textContent = `מייבא ${selectedEmails.length} מיילים...`;

    // Show status icons on selected emails
    selectedIndices.forEach(i => {
        const icon = document.getElementById('email-status-' + i);
        if (icon) {
            icon.style.display = 'inline-flex';
            icon.className = 'email-status-icon pending';
            icon.textContent = '⋯';
        }
    });

    const btn = document.getElementById('import-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> מייבא...';

    let totalImported = 0;
    const importedCases = [];

    // Try streaming import first; fall back to per-email if it fails
    let streamWorked = false;
    try {
        const resp = await fetch('/api/emails/import-stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ emails: selectedEmails }),
        });
        if (!resp.ok || !resp.body) throw new Error('stream not available');

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                const jsonStr = line.slice(6).trim();
                if (!jsonStr) continue;
                let msg;
                try { msg = JSON.parse(jsonStr); }
                catch (e) { continue; }

                handleProgressEvent(msg, selectedIndices, progressFill, progressText, importedCases);
                if (msg.type === 'done') totalImported = msg.total_imported;
            }
        }
        streamWorked = true;
    } catch (e) {
        console.warn('SSE stream failed, falling back to per-email import:', e);
    }

    // Fallback: import each email synchronously with progress between calls
    if (!streamWorked) {
        for (let i = 0; i < selectedEmails.length; i++) {
            const itemIdx = selectedIndices[i];
            const icon = document.getElementById('email-status-' + itemIdx);
            if (icon) {
                icon.className = 'email-status-icon active';
                icon.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:2px"></span>';
            }
            progressText.textContent = `(${i + 1}/${selectedEmails.length}) מייבא: ${selectedEmails[i].subject?.slice(0, 40) || 'מייל'}`;
            progressFill.style.width = ((i / selectedEmails.length) * 100) + '%';

            try {
                const result = await api('/api/emails/import', {
                    method: 'POST',
                    body: JSON.stringify(selectedEmails[i]),
                });
                totalImported++;
                importedCases.push(result.case_number);
                if (icon) { icon.className = 'email-status-icon done'; icon.textContent = '✓'; }
                if (result.parsed_fields) {
                    const p = result.parsed_fields;
                    const parts = [];
                    if (p.plaintiff_name) parts.push(p.plaintiff_name);
                    if (p.plaintiff_id) parts.push('ת.ז: ' + p.plaintiff_id);
                    if (parts.length) showToast(`תיק ${result.case_number}: ${parts.join(' | ')}`, 'success');
                }
            } catch (e) {
                if (icon) { icon.className = 'email-status-icon error'; icon.textContent = '✕'; }
            }
        }
        progressFill.style.width = '100%';
    }

    progressTitle.textContent = `הסתיים: יובאו ${totalImported} מיילים`;
    progressText.textContent = importedCases.length
        ? `תיקים שנוצרו: ${importedCases.join(', ')}`
        : '';
    showToast(`יובאו ${totalImported} מיילים בהצלחה`, 'success');

    document.getElementById('email-badge').style.display = 'none';
    btn.disabled = false;
    btn.innerHTML = '&#10003; ייבא נבחרים';

    setTimeout(() => showPage('cases'), 2000);
}

function handleProgressEvent(msg, selectedIndices, progressFill, progressText, importedCases) {
    if (msg.type === 'progress') {
        const itemIdx = selectedIndices[msg.email_index];
        const icon = document.getElementById('email-status-' + itemIdx);
        if (icon) {
            icon.className = 'email-status-icon active';
            icon.innerHTML = '<span class="spinner" style="width:12px;height:12px;border-width:2px"></span>';
        }
        // Estimate progress: each email = 100/total, current step adds partial
        const stepProgress = (msg.email_index / msg.total) * 100;
        progressFill.style.width = stepProgress + '%';
        progressText.textContent = `(${msg.email_index + 1}/${msg.total}) ${msg.message}`;
    } else if (msg.type === 'complete') {
        const itemIdx = selectedIndices[msg.email_index];
        const icon = document.getElementById('email-status-' + itemIdx);
        if (icon) {
            icon.className = 'email-status-icon done';
            icon.textContent = '✓';
        }
        const completedProgress = ((msg.email_index + 1) / msg.total) * 100;
        progressFill.style.width = completedProgress + '%';
        importedCases.push(msg.case_number);

        if (msg.parsed_fields) {
            const p = msg.parsed_fields;
            const parts = [];
            if (p.plaintiff_name) parts.push(p.plaintiff_name);
            if (p.plaintiff_id) parts.push('ת.ז: ' + p.plaintiff_id);
            if (parts.length) showToast(`תיק ${msg.case_number}: ${parts.join(' | ')}`, 'success');
        }
    } else if (msg.type === 'error') {
        const itemIdx = selectedIndices[msg.email_index];
        const icon = document.getElementById('email-status-' + itemIdx);
        if (icon) {
            icon.className = 'email-status-icon error';
            icon.textContent = '✕';
        }
        showToast('שגיאה בייבוא: ' + msg.message, 'error');
    } else if (msg.type === 'done') {
        progressFill.style.width = '100%';
    }
}

// ===== Field Manager =====
function buildFieldManager() {
    if (!appSchema) return;
    const typeLabels = { text: 'טקסט', number: 'מספר', select: 'בחירה', textarea: 'טקסט ארוך', email: 'אימייל', date: 'תאריך' };
    const toggleProps = [
        { key: 'in_table', label: 'בטבלה' },
        { key: 'in_new_form', label: 'בטופס חדש' },
        { key: 'extractable', label: 'חילוץ אוטומטי' },
        { key: 'in_dashboard', label: 'בדשבורד' },
    ];

    // Only show manageable fields (skip meta/system fields)
    const fields = appSchema.fields.filter(f => f.group !== 'meta');

    let html = `<table class="field-manager-table">
        <thead><tr>
            <th>שדה</th>
            <th>סוג</th>
            ${toggleProps.map(p => `<th style="text-align:center">${p.label}</th>`).join('')}
            <th></th>
        </tr></thead><tbody>`;

    for (const f of fields) {
        const isCustom = f.is_custom;
        html += `<tr>
            <td><strong>${f.label}</strong>${isCustom ? ' <span class="field-type-badge" style="background:#FFE4B5;color:#8A6100">מותאם</span>' : ''}</td>
            <td><span class="field-type-badge">${typeLabels[f.type] || f.type}</span></td>`;
        for (const prop of toggleProps) {
            const checked = f[prop.key] ? 'checked' : '';
            html += `<td style="text-align:center">
                <label class="toggle">
                    <input type="checkbox" data-field="${f.key}" data-prop="${prop.key}" ${checked}>
                    <span class="toggle-slider"></span>
                </label>
            </td>`;
        }
        html += '<td style="text-align:center">';
        if (isCustom) {
            html += `<button class="btn btn-sm btn-ghost" onclick="editCustomField('${f.key}')" title="ערוך">&#9998;</button>
                     <button class="btn btn-sm btn-ghost" onclick="deleteCustomField('${f.key}')" title="מחק" style="color:var(--danger)">&#10005;</button>`;
        }
        html += '</td></tr>';
    }
    html += '</tbody></table>';
    document.getElementById('field-manager-container').innerHTML = html;
}

async function saveFieldOverrides() {
    const checkboxes = document.querySelectorAll('#field-manager-container input[type="checkbox"]');
    const overrides = {};
    checkboxes.forEach(cb => {
        const fieldKey = cb.dataset.field;
        const prop = cb.dataset.prop;
        if (!overrides[fieldKey]) overrides[fieldKey] = {};
        overrides[fieldKey][prop] = cb.checked;
    });

    try {
        await api('/api/schema/overrides', { method: 'POST', body: JSON.stringify(overrides) });
        showToast('הגדרות השדות נשמרו - הדף יתרענן', 'success');
        // Reload schema and rebuild UI
        appSchema = null;
        await loadSchema();
        loadDashboard();
    } catch (e) { /* toast shown */ }
}

// ===== Custom Fields =====
function openCustomFieldModal() {
    document.getElementById('custom-field-modal-title').textContent = 'הוספת שדה חדש';
    document.getElementById('cf-original-key').value = '';
    document.getElementById('cf-label').value = '';
    document.getElementById('cf-type').value = 'text';
    document.getElementById('cf-group').value = 'info';
    document.getElementById('cf-options').value = '';
    document.getElementById('cf-in-table').checked = true;
    document.getElementById('cf-in-new-form').checked = true;
    document.getElementById('cf-in-dashboard').checked = false;
    document.getElementById('cf-extractable').checked = false;
    toggleCustomFieldOptions();
    document.getElementById('custom-field-modal').classList.add('active');
}

function closeCustomFieldModal() {
    document.getElementById('custom-field-modal').classList.remove('active');
}

function toggleCustomFieldOptions() {
    const type = document.getElementById('cf-type').value;
    document.getElementById('cf-options-row').style.display = type === 'select' ? 'block' : 'none';
}

function editCustomField(key) {
    const f = appSchema.fields.find(x => x.key === key);
    if (!f) return;
    document.getElementById('custom-field-modal-title').textContent = 'עריכת שדה: ' + f.label;
    document.getElementById('cf-original-key').value = key;
    document.getElementById('cf-label').value = f.label;
    document.getElementById('cf-type').value = f.type || 'text';
    document.getElementById('cf-group').value = f.group || 'info';
    document.getElementById('cf-options').value = (f.options || []).join(', ');
    document.getElementById('cf-in-table').checked = !!f.in_table;
    document.getElementById('cf-in-new-form').checked = !!f.in_new_form;
    document.getElementById('cf-in-dashboard').checked = !!f.in_dashboard;
    document.getElementById('cf-extractable').checked = !!f.extractable;
    toggleCustomFieldOptions();
    document.getElementById('custom-field-modal').classList.add('active');
}

async function saveCustomField() {
    const label = document.getElementById('cf-label').value.trim();
    if (!label) { showToast('יש להזין תווית לשדה', 'error'); return; }

    const type = document.getElementById('cf-type').value;
    const optionsStr = document.getElementById('cf-options').value.trim();
    const options = type === 'select' && optionsStr
        ? optionsStr.split(',').map(o => o.trim()).filter(Boolean)
        : null;

    const field = {
        key: document.getElementById('cf-original-key').value || '',
        label,
        type,
        group: document.getElementById('cf-group').value,
        options,
        in_table: document.getElementById('cf-in-table').checked,
        in_new_form: document.getElementById('cf-in-new-form').checked,
        in_dashboard: document.getElementById('cf-in-dashboard').checked,
        extractable: document.getElementById('cf-extractable').checked,
    };

    try {
        await api('/api/schema/custom-fields', { method: 'POST', body: JSON.stringify(field) });
        showToast('השדה נשמר', 'success');
        closeCustomFieldModal();
        appSchema = null;
        await loadSchema();
        buildFieldManager();
    } catch (e) { /* toast shown */ }
}

async function deleteCustomField(key) {
    if (!confirm('האם למחוק את השדה? פעולה זו לא תמחק נתונים קיימים בקובץ ה-Excel.')) return;
    try {
        await api('/api/schema/custom-fields/' + encodeURIComponent(key), { method: 'DELETE' });
        showToast('השדה נמחק', 'success');
        appSchema = null;
        await loadSchema();
        buildFieldManager();
    } catch (e) { /* toast shown */ }
}

// ===== Settings =====
async function loadSettings() {
    try {
        const config = await api('/api/settings');
        document.getElementById('set-datadir').value = config.data_dir || '';
        document.getElementById('set-email').value = config.email_address || '';
        document.getElementById('set-password').value = config.email_password || '';
        document.getElementById('set-imap').value = config.imap_server || 'imap.gmail.com';
        document.getElementById('set-smtp').value = config.smtp_server || 'smtp.gmail.com';
        document.getElementById('set-name').value = config.professor_name || '';
        document.getElementById('set-title').value = config.professor_title || 'פרופסור';
        document.getElementById('set-specialty').value = config.professor_specialty || 'אורולוגיה';
        document.getElementById('set-license').value = config.professor_license || '';
        document.getElementById('set-phone').value = config.professor_phone || '';
        document.getElementById('set-address').value = config.professor_address || '';
        document.getElementById('set-github-repo').value = config.github_repo || '';
        document.getElementById('setting-collector-url').value = config.collector_url || '';
    } catch (e) { /* toast shown */ }
    try {
        const ver = await api('/api/update/version');
        document.getElementById('current-version').textContent = ver.version || '-';
    } catch (e) { /* ignore */ }
    buildFieldManager();
}

async function saveSettings(e) {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(document.getElementById('settings-form')).entries());
    try {
        await api('/api/settings', { method: 'POST', body: JSON.stringify(data) });
        showToast('ההגדרות נשמרו בהצלחה', 'success');
    } catch (e) { /* toast shown */ }
}

async function testEmailConnection() {
    const status = document.getElementById('connection-status');
    status.innerHTML = '<span class="spinner"></span> שומר ובודק...';
    status.style.color = 'var(--text-secondary)';
    const data = Object.fromEntries(new FormData(document.getElementById('settings-form')).entries());
    try { await api('/api/settings', { method: 'POST', body: JSON.stringify(data) }); }
    catch (e) { status.textContent = 'שגיאה בשמירת הגדרות'; status.style.color = 'var(--danger)'; return; }
    try {
        const result = await api('/api/emails/test');
        if (result.success) { status.style.color = 'var(--success)'; status.innerHTML = '&#10003; החיבור הצליח'; }
        else { status.textContent = result.message; status.style.color = 'var(--danger)'; }
    } catch (e) { status.textContent = 'שגיאה בחיבור'; status.style.color = 'var(--danger)'; }
}

async function browseDataDir() {
    try {
        const result = await api('/api/settings/browse-folder', { method: 'POST' });
        if (result.path) { document.getElementById('set-datadir').value = result.path; showToast('תיקייה נבחרה - לחץ "שמור הגדרות" לאישור', 'info'); }
        else if (result.error) showToast('במצב דפדפן יש להזין את הנתיב ידנית', 'info');
    } catch (e) { /* toast shown */ }
}

async function openDataDir() {
    const path = document.getElementById('set-datadir').value;
    if (path) try { await api('/api/open-folder', { method: 'POST', body: JSON.stringify({ path }) }); } catch (e) { /* toast shown */ }
}

// ===== Updates =====
async function saveGithubRepo() {
    const repo = document.getElementById('set-github-repo').value.trim();
    try { await api('/api/settings', { method: 'POST', body: JSON.stringify({ github_repo: repo }) }); showToast('Repository saved', 'success'); } catch (e) { /* toast shown */ }
}

async function checkForUpdates() {
    const btn = document.getElementById('check-update-btn');
    btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> בודק...';
    const repo = document.getElementById('set-github-repo').value.trim();
    if (!repo) { showToast('יש להזין GitHub repository (owner/repo)', 'error'); btn.disabled = false; btn.innerHTML = '&#128269; בדוק עדכונים'; return; }
    await api('/api/settings', { method: 'POST', body: JSON.stringify({ github_repo: repo }) });
    try {
        const result = await api('/api/update/check');
        const container = document.getElementById('update-result');
        if (result.error) { container.innerHTML = `<p style="color:var(--danger)">${result.error}</p>`; }
        else if (result.available) {
            const notes = (result.release_notes || '').replace(/\n/g, '<br>');
            container.innerHTML = `<div style="border:2px solid var(--success);border-radius:var(--radius);padding:16px;background:var(--success-bg)">
                <p style="font-weight:600;margin-bottom:8px">&#10004; גרסה חדשה זמינה: <strong>${result.latest_version}</strong></p>
                ${notes ? `<div style="font-size:13px;background:white;padding:10px;border-radius:4px;margin-bottom:12px;max-height:150px;overflow-y:auto">${notes}</div>` : ''}
                <button class="btn btn-success" onclick="applyUpdate('${result.download_url}')">&#128229; התקן עדכון ${result.latest_version}</button></div>`;
        } else { container.innerHTML = `<p style="color:var(--success)">&#10004; המערכת מעודכנת (גרסה ${result.current_version})</p>`; }
    } catch (e) { /* toast shown */ }
    btn.disabled = false; btn.innerHTML = '&#128269; בדוק עדכונים';
}

async function applyUpdate(downloadUrl) {
    if (!confirm('האם להתקין את העדכון? האפליקציה תדרוש הפעלה מחדש.')) return;
    const container = document.getElementById('update-result');
    container.innerHTML = '<div class="loading-overlay"><span class="spinner"></span> מוריד ומתקין עדכון...</div>';
    try {
        const result = await api('/api/update/apply', { method: 'POST', body: JSON.stringify({ download_url: downloadUrl }) });
        if (result.success) { container.innerHTML = `<div style="border:2px solid var(--success);border-radius:var(--radius);padding:16px;background:var(--success-bg)"><p style="font-weight:600">&#10004; ${result.message}</p><button class="btn btn-primary" onclick="location.reload()" style="margin-top:12px">&#8635; הפעל מחדש</button></div>`; }
        else { container.innerHTML = `<p style="color:var(--danger)">&#10006; ${result.message}</p>`; }
    } catch (e) { /* toast shown */ }
}

// ===== Logs / Diagnostics =====
async function viewLogs() {
    const ta = document.getElementById('log-viewer');
    ta.style.display = 'block';
    ta.value = 'טוען...';
    try {
        const data = await api('/api/logs?lines=500');
        ta.value = data.log || '(הלוג ריק)';
        ta.scrollTop = ta.scrollHeight;  // scroll to bottom
    } catch (e) {
        ta.value = 'שגיאה בטעינת הלוג: ' + e.message;
    }
}

async function openLogFile() {
    try {
        const result = await api('/api/logs/open', { method: 'POST' });
        showToast('קובץ הלוג נפתח: ' + (result.path || ''), 'success');
    } catch (e) { /* toast shown */ }
}

async function copyLogs() {
    try {
        const data = await api('/api/logs?lines=500');
        await navigator.clipboard.writeText(data.log || '');
        showToast('הלוג הועתק ללוח - אפשר להדביק למייל', 'success');
    } catch (e) {
        showToast('שגיאה בהעתקה: ' + e.message, 'error');
    }
}

// ===== Telemetry / Log Sending =====
async function sendDiagnosticBundle() {
    const resultDiv = document.getElementById('send-logs-result');
    // Save collector URL first
    const collectorUrl = document.getElementById('setting-collector-url').value.trim();
    if (!collectorUrl) {
        showToast('יש להזין כתובת שרת איסוף', 'error');
        return;
    }
    resultDiv.innerHTML = '<span class="spinner"></span> שומר כתובת ושולח לוגים...';
    try {
        // Save the collector URL to config
        await api('/api/settings', {
            method: 'POST',
            body: JSON.stringify({ collector_url: collectorUrl })
        });
        // Send diagnostic bundle
        const result = await api('/api/telemetry/send-logs', { method: 'POST' });
        if (result.success) {
            resultDiv.innerHTML = `<span style="color:var(--success)">&#10003; ${result.message}</span>`;
            showToast(result.message, 'success');
        } else {
            resultDiv.innerHTML = `<span style="color:var(--danger)">&#10006; ${result.message}</span>`;
            showToast(result.message, 'error');
        }
    } catch (e) {
        resultDiv.innerHTML = `<span style="color:var(--danger)">&#10006; שגיאה: ${e.message}</span>`;
    }
}

async function sendUsageEvents() {
    const collectorUrl = document.getElementById('setting-collector-url').value.trim();
    if (!collectorUrl) {
        showToast('יש להזין כתובת שרת איסוף', 'error');
        return;
    }
    try {
        await api('/api/settings', {
            method: 'POST',
            body: JSON.stringify({ collector_url: collectorUrl })
        });
        const result = await api('/api/telemetry/send-events', { method: 'POST' });
        showToast(result.message || 'נתוני שימוש נשלחו', 'success');
    } catch (e) {
        showToast('שגיאה בשליחת נתוני שימוש: ' + e.message, 'error');
    }
}

// ===== Folder Import =====
async function browseFolderImport() {
    try {
        const result = await api('/api/settings/browse-folder', { method: 'POST' });
        if (result.path) {
            document.getElementById('import-folder-path').value = result.path;
            scanFolderFiles();
        } else if (result.error) {
            showToast('במצב דפדפן יש להזין את הנתיב ידנית', 'info');
        }
    } catch (e) { /* toast shown */ }
}

async function scanFolderFiles() {
    const path = document.getElementById('import-folder-path').value.trim();
    if (!path) { showToast('יש להזין נתיב תיקייה', 'error'); return; }

    const container = document.getElementById('import-folder-files');
    container.innerHTML = '<span class="spinner"></span> סורק...';

    try {
        const result = await api('/api/folder/scan', { method: 'POST', body: JSON.stringify({ path }) });
        if (!result.files || !result.files.length) {
            container.innerHTML = '<p style="color:var(--text-muted);font-size:13px">לא נמצאו קבצים נתמכים (PDF/Word) בתיקייה</p>';
            document.getElementById('import-folder-btn').disabled = true;
            return;
        }
        container.innerHTML = `<p style="font-size:13px;color:var(--text-secondary);margin-bottom:6px">נמצאו ${result.count} קבצים:</p>
            <div class="file-list">${result.files.map(f => `
                <div class="file-item">
                    <span class="file-icon">&#128196;</span>
                    <span class="file-name">${_escapeHtml(f.name)}</span>
                    <span class="file-size">${formatSize(f.size)}</span>
                </div>`).join('')}
            </div>`;
        document.getElementById('import-folder-btn').disabled = false;
    } catch (e) {
        container.innerHTML = '';
    }
}

async function importFromFolder() {
    const path = document.getElementById('import-folder-path').value.trim();
    if (!path) { showToast('יש להזין נתיב תיקייה', 'error'); return; }

    const btn = document.getElementById('import-folder-btn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> מייבא...';

    const progress = document.getElementById('import-folder-progress');
    progress.innerHTML = '<p style="color:var(--text-secondary)"><span class="spinner" style="display:inline-block;vertical-align:middle;margin-left:8px"></span> מחלץ טקסט מקבצים, מנתח פרטים, יוצר תיק...</p>';

    try {
        const result = await api('/api/folder/import', { method: 'POST', body: JSON.stringify({ path }) });
        if (result.success) {
            const p = result.parsed_fields || {};
            const name = p.plaintiff_name || [p.plaintiff_first_name, p.plaintiff_last_name].filter(Boolean).join(' ') || 'ללא שם';
            progress.innerHTML = `<div style="border:2px solid var(--success);border-radius:var(--radius);padding:12px;background:var(--success-bg)">
                <p style="font-weight:600">&#10004; תיק מס׳ ${result.case_number} נוצר: ${_escapeHtml(name)}</p>
                <p style="font-size:12px;margin-top:4px">${result.copied_files} קבצים הועתקו לתיקיית התיק</p>
                <button class="btn btn-sm btn-outline" onclick="viewCase(${result.case_number})" style="margin-top:8px">&#128193; צפה בתיק</button>
            </div>`;
            showToast(`תיק ${result.case_number} נוצר מתיקייה`, 'success');
        }
    } catch (e) {
        progress.innerHTML = `<p style="color:var(--danger)">&#10006; שגיאה: ${e.message}</p>`;
    }

    btn.disabled = false;
    btn.innerHTML = '&#10010; צור תיק מתיקייה';
}

// ===== Initialize =====
document.addEventListener('DOMContentLoaded', async () => {
    await loadSchema();
    loadDashboard();
});
