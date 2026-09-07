/**
 * Общий модуль для загрузки и отображения файлов из папки inbox.
 * Подключается в base.html, используется всеми шаблонами отчётов.
 */

let _inboxData = { files: [], folders: [] };
let _expandedFolders = {};

function savedInboxSelection() {
    try { return JSON.parse(localStorage.getItem('kapitanSelectedFiles') || '[]'); }
    catch (e) { return []; }
}

function inboxFileChecked(path) {
    const saved = savedInboxSelection();
    return !saved.length || saved.includes(path) ? 'checked' : '';
}

function saveInboxSelection() {
    localStorage.setItem('kapitanSelectedFiles', JSON.stringify(selectedFiles()));
}

async function loadInbox() {
    const box = document.getElementById('inboxList');
    if (!box) return;
    try {
        const res = await fetch('/api/inbox/files');
        const json = await res.json();
        _inboxData.files = json.files || [];
        _inboxData.folders = json.folders || [];
        renderInbox(box);
    } catch (e) {
        box.innerHTML = '<div style="padding:8px;color:#c00;">Не удалось загрузить список файлов.</div>';
    }
}

async function loadFolderFiles(folderPath) {
    if (_expandedFolders[folderPath]) return;
    try {
        const res = await fetch(`/api/inbox/folder/${encodeURIComponent(folderPath)}`);
        const json = await res.json();
        _expandedFolders[folderPath] = json.files || [];
        const box = document.getElementById('inboxList');
        if (box) renderInbox(box);
    } catch (e) {
        console.error('Failed to load folder:', e);
    }
}

function renderInbox(box) {
    if (!_inboxData.files.length && !_inboxData.folders.length) {
        box.innerHTML = '<div style="padding:8px;color:#999;">Папка inbox пуста. Положите Excel-файлы из 1С в папку inbox проекта Kapitan Reports.</div>';
        return;
    }

    let html = '';

    // Папки
    if (_inboxData.folders.length) {
        html += '<div style="margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid #e2e8f0;">';
        html += '<div style="font-size:12px;color:#888;margin-bottom:4px;font-weight:600;">ПАПКИ</div>';
        _inboxData.folders.forEach(f => {
            const expanded = _expandedFolders[f.path];
            const arrow = expanded ? '▼' : '▶';
            html += `<div style="margin-bottom:4px;">
                <div style="display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:6px;cursor:pointer;font-size:13px;color:#555;" onclick="loadFolderFiles('${f.path}')">
                    ${arrow} 📁 ${f.name}
                </div>`;
            if (expanded) {
                if (expanded.length) {
                    html += '<div style="margin-left:20px;">';
                    html += expanded.map(file => `
                        <label style="display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:6px;cursor:pointer;font-size:13px;">
                            <input type="checkbox" class="inbox-file" value="${file.path}" ${inboxFileChecked(file.path)} onchange="updateSelectAll();saveInboxSelection()">
                            📄 ${file.name}
                        </label>
                    `).join('');
                    html += '</div>';
                } else {
                    html += '<div style="margin-left:20px;padding:4px 6px;font-size:12px;color:#999;">Пусто</div>';
                }
            }
            html += '</div>';
        });
        html += '</div>';
    }

    // Файлы в корне
    if (_inboxData.files.length) {
        html += '<div style="font-size:12px;color:#888;margin-bottom:4px;font-weight:600;">ФАЙЛЫ</div>';
        html += _inboxData.files.map(f => `
            <label style="display:flex;align-items:center;gap:8px;padding:5px 6px;border-radius:6px;cursor:pointer;font-size:13px;">
                <input type="checkbox" class="inbox-file" value="${f.name}" ${inboxFileChecked(f.name)} onchange="updateSelectAll();saveInboxSelection()">
                📄 ${f.name}
            </label>
        `).join('');
    }

    box.innerHTML = html;
}

function selectedFiles() {
    return Array.from(document.querySelectorAll('.inbox-file:checked')).map(c => c.value);
}

function toggleAll(on) {
    document.querySelectorAll('.inbox-file').forEach(c => c.checked = on);
}

function updateSelectAll() {
    const all = document.querySelectorAll('.inbox-file');
    const sel = document.querySelectorAll('.inbox-file:checked');
    const cb = document.getElementById('selectAll');
    if (cb) cb.checked = all.length > 0 && all.length === sel.length;
}
