let pdfs = [];
let viperUsers = [];
let deleteTarget = { type: '', id: null };

const avatarColors = [
  { bg: 'rgba(224,159,62,0.15)', fg: '#e09f3e' },
  { bg: 'rgba(62,201,122,0.15)', fg: '#3ec97a' },
  { bg: 'rgba(62,168,224,0.15)', fg: '#3ea8e0' },
  { bg: 'rgba(224,85,85,0.15)', fg: '#e05555' },
  { bg: 'rgba(168,85,224,0.15)', fg: '#a855e0' },
  { bg: 'rgba(224,168,62,0.15)', fg: '#e0a83e' },
  { bg: 'rgba(62,224,201,0.15)', fg: '#3ee0c9' },
  { bg: 'rgba(224,62,168,0.15)', fg: '#e03ea8' },
];

function genId() {
  return 'id_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

function formatDate(iso) {
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return 'Just now';
  if (diff < 3600000) return Math.floor(diff / 60000) + 'm ago';
  if (diff < 86400000) return Math.floor(diff / 3600000) + 'h ago';
  if (diff < 604800000) return Math.floor(diff / 86400000) + 'd ago';
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatTime(iso) {
  const d = new Date(iso);
  const today = new Date();
  const isToday = d.toDateString() === today.toDateString();
  if (isToday) return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function esc(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}

function getInitials(name) {
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function getAvatarColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return avatarColors[Math.abs(hash) % avatarColors.length];
}

function showToast(message, type = 'success') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icons = { success: 'fa-circle-check', error: 'fa-circle-xmark', info: 'fa-circle-info' };
  toast.innerHTML = `<i class="fas ${icons[type]}"></i> ${message}`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3200);
}

function switchPage(pageId) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + pageId).classList.add('active');
  document.querySelector(`.nav-item[data-page="${pageId}"]`).classList.add('active');
  document.getElementById('mainContent').scrollTop = 0;

  if (pageId === 'dashboard') updateDashboard();
  if (pageId === 'pdfs') renderPdfList();
  if (pageId === 'chats') loadChatUsers();
  if (pageId === 'users') loadViperUsers();
}

function updateDashboard() {
  fetch('/api/admin/stats').then(r => r.json()).then(data => {
    document.getElementById('statUsers').textContent   = data.users    || 0;
    document.getElementById('statMessages').textContent = data.messages || 0;
    document.getElementById('statPdfs').textContent    = pdfs.length;
  });

  const recentDiv = document.getElementById('recentUploads');
  if (pdfs.length === 0) {
    recentDiv.innerHTML = `<div class="empty-state" style="height:180px;"><i class="fas fa-cloud-arrow-up"></i><span style="font-size:13px;">No PDFs uploaded yet</span></div>`;
  } else {
    recentDiv.innerHTML = pdfs.slice(-4).reverse().map(p => `
      <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--bg-elevated);border-radius:10px;">
        <div style="width:32px;height:32px;background:rgba(224,85,85,0.12);color:var(--danger);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;">
          <i class="fas fa-file-pdf"></i>
        </div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${p.name}</div>
          <div style="font-size:11px;color:var(--fg-muted);">${formatSize(p.size)} · ${formatDate(p.uploadedAt)}</div>
        </div>
        <span class="badge badge-success" style="font-size:10px;"><i class="fas fa-check"></i> Ready</span>
      </div>
    `).join('');
  }

  fetch('/api/admin/users').then(r => r.json()).then(data => {
    const chatsDiv = document.getElementById('recentChats');
    const users = (data.users || []).filter(u => u.chat_count > 0).slice(0, 4);
    if (users.length === 0) {
      chatsDiv.innerHTML = `<div class="empty-state" style="height:180px;"><i class="fas fa-comments"></i><span style="font-size:13px;">No chat activity yet</span></div>`;
    } else {
      chatsDiv.innerHTML = users.map(u => {
        const name = u.name || u.email;
        const color = getAvatarColor(name);
        return `
          <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--bg-elevated);border-radius:10px;">
            <div style="width:32px;height:32px;background:${color.bg};color:${color.fg};border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;font-family:'Space Grotesk';">${getInitials(name)}</div>
            <div style="flex:1;min-width:0;">
              <div style="font-size:13px;font-weight:500;">${esc(name)}</div>
              <div style="font-size:11px;color:var(--fg-muted);">${u.message_count} messages</div>
            </div>
            <span style="font-size:11px;color:var(--fg-muted);white-space:nowrap;">${formatDate(u.created_at)}</span>
          </div>
        `;
      }).join('');
    }
  });
}

const uploadZone = document.getElementById('uploadZone');

uploadZone.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
  uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
  if (files.length === 0) { showToast('Please drop PDF files only', 'error'); return; }
  processFiles(files);
});

function handleFileSelect(event) {
  const files = Array.from(event.target.files);
  processFiles(files);
  event.target.value = '';
}

function processFiles(files) {
  const progressDiv = document.getElementById('uploadProgress');
  progressDiv.style.display = 'block';

  files.forEach((file, idx) => {
    const fileId = genId();
    const progId = 'prog_' + fileId;
    progressDiv.innerHTML += `
      <div id="${progId}" style="background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:14px 18px;margin-bottom:8px;display:flex;align-items:center;gap:12px;">
        <div style="width:32px;height:32px;background:rgba(224,85,85,0.12);color:var(--danger);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0;"><i class="fas fa-file-pdf"></i></div>
        <div style="flex:1;">
          <div style="font-size:13px;font-weight:500;margin-bottom:6px;">${file.name}</div>
          <div class="progress-bar"><div class="progress-fill" id="${progId}_bar" style="width:0%"></div></div>
        </div>
        <span style="font-size:12px;color:var(--fg-muted);" id="${progId}_pct">0%</span>
      </div>
    `;

    let progress = 0;
    const interval = setInterval(() => {
      progress += Math.random() * 20 + 5;
      if (progress >= 100) {
        progress = 100;
        clearInterval(interval);

        const pages = Math.floor(Math.random() * 40) + 5;
        pdfs.push({
          id: fileId,
          name: file.name,
          size: file.size,
          pages: pages,
          uploadedAt: new Date().toISOString(),
          status: 'processed'
        });
        saveData();

        setTimeout(() => {
          const el = document.getElementById(progId);
          if (el) {
            el.querySelector(`#${progId}_pct`).innerHTML = '<i class="fas fa-check" style="color:var(--success);"></i>';
            el.querySelector(`#${progId}_pct`).style.color = 'var(--success)';
            setTimeout(() => el.remove(), 1500);
          }
          renderPdfList();
          updateDashboard();
        }, 400);
      }

      const bar = document.getElementById(progId + '_bar');
      const pct = document.getElementById(progId + '_pct');
      if (bar) bar.style.width = Math.min(progress, 100) + '%';
      if (pct && progress < 100) pct.textContent = Math.floor(Math.min(progress, 100)) + '%';
    }, 200 + idx * 100);
  });

  showToast(`${files.length} PDF${files.length > 1 ? 's' : ''} uploaded successfully`, 'success');
}

function renderPdfList() {
  const list = document.getElementById('pdfList');
  const search = document.getElementById('pdfSearch').value.toLowerCase();
  document.getElementById('pdfCount').textContent = pdfs.length;

  const filtered = pdfs.filter(p => p.name.toLowerCase().includes(search));

  if (filtered.length === 0) {
    list.innerHTML = `<div class="empty-state" style="height:200px;background:var(--bg-card);border:1px solid var(--border);border-radius:14px;">
      <i class="fas fa-folder-open"></i>
      <span style="font-size:13px;">${search ? 'No documents match your search' : 'Your document library is empty'}</span>
    </div>`;
    return;
  }

  list.innerHTML = filtered.map(p => `
    <div class="pdf-item" id="pdf-${p.id}">
      <div class="pdf-icon"><i class="fas fa-file-pdf"></i></div>
      <div style="flex:1;min-width:0;">
        <div style="font-size:14px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${p.name}</div>
        <div style="font-size:12px;color:var(--fg-muted);margin-top:2px;">
          ${formatSize(p.size)} · ${p.pages} pages · ${formatDate(p.uploadedAt)}
        </div>
      </div>
      <span class="badge badge-success"><i class="fas fa-circle-check"></i> Processed</span>
      <button class="btn-danger" onclick="openDeleteModal('pdf', '${p.id}', '${p.name.replace(/'/g, "\\'")}')">
        <i class="fas fa-trash-can"></i> Remove
      </button>
    </div>
  `).join('');
}

function filterPdfs() { renderPdfList(); }

let selectedChatId = null;
let chatPageUsers = [];

async function loadChatUsers() {
  const list = document.getElementById('chatUserList');
  list.innerHTML = `<div class="empty-state" style="height:200px;"><i class="fas fa-spinner fa-spin"></i><span style="font-size:13px;">Loading...</span></div>`;
  try {
    const res = await fetch('/api/admin/users');
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    chatPageUsers = (data.users || []).filter(u => u.chat_count > 0);
    document.getElementById('chatCount').textContent = chatPageUsers.length;
    renderChatUserList();
  } catch (err) {
    list.innerHTML = `<div class="empty-state" style="height:200px;"><i class="fas fa-circle-exclamation" style="color:var(--danger);"></i><span style="font-size:13px;color:var(--danger);">Failed to load</span></div>`;
  }
}

function renderChatUserList() {
  const list = document.getElementById('chatUserList');
  const search = document.getElementById('chatSearch').value.toLowerCase();
  const filtered = chatPageUsers.filter(u =>
    (u.name || '').toLowerCase().includes(search) || u.email.toLowerCase().includes(search)
  );
  if (filtered.length === 0) {
    list.innerHTML = `<div class="empty-state" style="height:300px;background:var(--bg-card);border:1px solid var(--border);border-radius:14px;"><i class="fas fa-user-group"></i><span style="font-size:13px;">${search ? 'No users match your search' : 'No user conversations found'}</span></div>`;
    return;
  }
  list.innerHTML = filtered.map(u => {
    const name = u.name || u.email;
    const color = getAvatarColor(name);
    return `
      <div class="chat-user-item" onclick="selectChatUser('${u.email}', '${esc(name)}', '${getInitials(name)}', '${color.bg}', '${color.fg}')">
        <div class="user-avatar" style="background:${color.bg};color:${color.fg};">${getInitials(name)}</div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:14px;font-weight:600;">${esc(name)}</div>
          <div style="font-size:12px;color:var(--fg-muted);">${u.email}</div>
        </div>
        <div style="text-align:right;flex-shrink:0;">
          <div style="font-size:11px;color:var(--fg-muted);">${formatDate(u.created_at)}</div>
          <div style="font-size:11px;color:var(--fg-muted);margin-top:4px;">${u.chat_count} chats</div>
        </div>
      </div>
    `;
  }).join('');
}

function filterChats() { renderChatUserList(); }

async function selectChatUser(email, displayName, initials, bg, fg) {
  document.getElementById('chatHeader').style.display = 'block';
  document.getElementById('chatAvatar').style.background = bg;
  document.getElementById('chatAvatar').style.color = fg;
  document.getElementById('chatAvatar').textContent = initials;
  document.getElementById('chatUserName').textContent = displayName;
  document.getElementById('chatUserEmail').textContent = email;

  const msgContainer = document.getElementById('chatMessages');
  msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><span style="font-size:13px;">Loading chats...</span></div>`;

  try {
    const res = await fetch(`/api/admin/users/${encodeURIComponent(email)}/chats`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const chats = data.chats || [];
    document.getElementById('chatMsgCount').innerHTML = `<i class="fas fa-message"></i> ${chats.length} chats`;
    if (chats.length === 0) {
      msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-comments"></i><span style="font-size:14px;">No chats found</span></div>`;
      return;
    }
    selectChatById(chats[0].id, email);
  } catch (err) {
    msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-circle-exclamation" style="color:var(--danger);"></i><span style="font-size:14px;color:var(--danger);">Failed to load chats</span></div>`;
  }
}

async function selectChatById(chatId, userEmail) {
  selectedChatId = chatId;
  const msgContainer = document.getElementById('chatMessages');
  msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><span style="font-size:13px;">Loading messages...</span></div>`;
  try {
    const res = await fetch(`/api/admin/chats/${chatId}/messages`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const messages = data.messages || [];
    if (!messages.length) {
      msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-inbox"></i><span style="font-size:14px;">No messages</span></div>`;
      return;
    }
    msgContainer.innerHTML = messages.map((m, i) => {
      const isUser = m.role === 'user';
      return `
        <div style="display:flex;flex-direction:column;align-items:${isUser ? 'flex-end' : 'flex-start'};">
          <div class="chat-bubble ${isUser ? 'bubble-user' : 'bubble-bot'}" style="animation-delay:${i * 0.05}s;">${m.message}</div>
          <div style="font-size:10px;color:var(--fg-muted);margin-top:4px;padding:0 4px;">
            ${isUser ? (userEmail || 'User') : 'ViperAI'} · ${formatTime(m.created_at)}
          </div>
        </div>
      `;
    }).join('');
    setTimeout(() => msgContainer.scrollTop = msgContainer.scrollHeight, 100);
  } catch (err) {
    msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-circle-exclamation" style="color:var(--danger);"></i><span style="font-size:14px;color:var(--danger);">Failed to load messages</span></div>`;
  }
}

function openDeleteModal(type, id, name) {
  deleteTarget = { type, id };
  const text = type === 'pdf'
    ? `Are you sure you want to delete "${name}"? The chatbot will no longer use this document.`
    : `Are you sure you want to delete all chat history for this user?`;
  document.getElementById('deleteModalText').textContent = text;
  document.getElementById('deleteModal').classList.add('show');
}

function closeDeleteModal() {
  document.getElementById('deleteModal').classList.remove('show');
  deleteTarget = { type: '', id: null };
}

function confirmDelete() {
  if (deleteTarget.type === 'pdf') {
    pdfs = pdfs.filter(p => p.id !== deleteTarget.id);
    saveData();
    renderPdfList();
    updateDashboard();
    showToast('PDF removed successfully', 'success');
  } else if (deleteTarget.type === 'chat') {
    userChats = userChats.filter(c => c.id !== deleteTarget.id);
    saveData();
    if (selectedChatId === deleteTarget.id) {
      selectedChatId = null;
      document.getElementById('chatHeader').style.display = 'none';
      document.getElementById('chatMessages').innerHTML = `
        <div class="empty-state"><i class="fas fa-arrow-left"></i>
        <span style="font-size:14px;">Select a user to view their conversation</span>
        <span style="font-size:12px;">Search by name or email on the left panel</span></div>`;
    }
    renderChatUserList();
    updateDashboard();
    showToast('Chat history deleted', 'success');
  }
  closeDeleteModal();
}

function saveSettings() {
  showToast('Settings saved successfully', 'success');
}

function exportData() {
  const data = JSON.stringify({ pdfs, userChats, exportedAt: new Date().toISOString() }, null, 2);
  const blob = new Blob([data], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'botbase_export_' + new Date().toISOString().slice(0, 10) + '.json';
  a.click();
  URL.revokeObjectURL(url);
  showToast('Chat data exported successfully', 'info');
}

function clearAllData() {
  deleteTarget = { type: 'all', id: null };
  document.getElementById('deleteModalText').textContent = 'Are you sure you want to clear ALL data? This will remove all PDFs and chat history. This cannot be undone.';
  document.getElementById('confirmDeleteBtn').textContent = 'Clear All';
  document.getElementById('confirmDeleteBtn').onclick = function() {
    pdfs = [];
    userChats = [];
    selectedChatId = null;
    saveData();
    updateDashboard();
    renderPdfList();
    renderChatUserList();
    document.getElementById('chatHeader').style.display = 'none';
    document.getElementById('chatMessages').innerHTML = `
      <div class="empty-state"><i class="fas fa-arrow-left"></i>
      <span style="font-size:14px;">Select a user to view their conversation</span></div>`;
    closeDeleteModal();
    document.getElementById('confirmDeleteBtn').textContent = 'Delete';
    document.getElementById('confirmDeleteBtn').onclick = confirmDelete;
    showToast('All data cleared', 'success');
  };
  document.getElementById('deleteModal').classList.add('show');
}

async function loadViperUsers() {
  const list = document.getElementById('viperUserList');
  list.innerHTML = `<div class="empty-state" style="height:200px;"><i class="fas fa-spinner fa-spin"></i><span style="font-size:13px;">Loading users...</span></div>`;

  try {
    const res = await fetch('/api/admin/users');
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    viperUsers = data.users || [];
    document.getElementById('viperUserCount').textContent = viperUsers.length;
    renderViperUserList();
  } catch (err) {
    list.innerHTML = `<div class="empty-state" style="height:200px;"><i class="fas fa-circle-exclamation" style="color:var(--danger);"></i><span style="font-size:13px;color:var(--danger);">Failed to load users</span></div>`;
    console.error('Error loading ViperAI users:', err);
  }
}

function renderViperUserList() {
  const list = document.getElementById('viperUserList');
  const search = (document.getElementById('viperUserSearch')?.value || '').toLowerCase();

  const filtered = viperUsers.filter(u => u.email.toLowerCase().includes(search));

  if (filtered.length === 0) {
    list.innerHTML = `<div class="empty-state" style="height:300px;background:var(--bg-card);border:1px solid var(--border);border-radius:14px;">
      <i class="fas fa-users-gear"></i>
      <span style="font-size:13px;">${search ? 'No users match your search' : 'No users found'}</span>
    </div>`;
    return;
  }

  list.innerHTML = filtered.map(u => {
    const name  = u.name || u.email;
    const color = getAvatarColor(name);
    return `
      <div class="chat-user-item" onclick="selectViperUser('${u.email}', '${esc(name)}', '${getInitials(name)}', '${color.bg}', '${color.fg}')">
        <div class="user-avatar" style="background:${color.bg};color:${color.fg};">${getInitials(name)}</div>
        <div style="flex:1;min-width:0;">
          <div style="font-size:14px;font-weight:600;">${esc(name)}</div>
          <div style="font-size:12px;color:var(--fg-muted);">${u.email}</div>
          <div style="font-size:11px;color:var(--fg-muted);margin-top:2px;">${u.chat_count || 0} chats · ${u.message_count || 0} messages</div>
        </div>
        <div style="font-size:11px;color:var(--fg-muted);white-space:nowrap;">${formatDate(u.created_at)}</div>
      </div>
    `;
  }).join('');
}

function filterViperUsers() { renderViperUserList(); }

let selectedViperUser = null;
let selectedViperChatId = null;

async function selectViperUser(email, displayName, initials, bg, fg) {
  selectedViperUser = email;
  selectedViperChatId = null;

  document.getElementById('viperChatHeader').style.display = 'block';
  document.getElementById('viperChatAvatar').style.background = bg;
  document.getElementById('viperChatAvatar').style.color = fg;
  document.getElementById('viperChatAvatar').textContent = initials;
  document.getElementById('viperChatUserName').textContent = displayName;
  document.getElementById('viperChatUserEmail').textContent = email;

  document.getElementById('viperChatTabs').style.display = 'none';
  document.getElementById('viperChatTabs').innerHTML = '';

  const msgContainer = document.getElementById('viperChatMessages');
  msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><span style="font-size:13px;">Loading chats...</span></div>`;

  try {
    const res = await fetch(`/api/admin/users/${encodeURIComponent(email)}/chats`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    const chats = data.chats || [];
    document.getElementById('viperChatCount').innerHTML = `<i class="fas fa-comments"></i> ${chats.length} chats`;

    if (chats.length === 0) {
      msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-comments"></i><span style="font-size:14px;">No chat history yet</span><span style="font-size:12px;">This user hasn't started any conversations</span></div>`;
      return;
    }

    const tabs = document.getElementById('viperChatTabs');
    tabs.style.display = 'flex';
    tabs.innerHTML = chats.map(c => `
      <button class="btn-ghost" style="padding:6px 14px;font-size:12px;border-radius:8px;white-space:nowrap;" onclick="selectViperChat(${c.id}, this)" id="viper-chat-tab-${c.id}">
        <i class="fas fa-message" style="font-size:10px;margin-right:4px;"></i> ${esc(c.title || 'Chat')}
      </button>
    `).join('');

    selectViperChat(chats[0].id, document.getElementById('viper-chat-tab-' + chats[0].id));
  } catch (err) {
    msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-circle-exclamation" style="color:var(--danger);"></i><span style="font-size:14px;color:var(--danger);">Failed to load chats</span></div>`;
    console.error('Error loading user chats:', err);
  }
}

async function selectViperChat(chatId, tabEl) {
  selectedViperChatId = chatId;
  document.querySelectorAll('#viperChatTabs .btn-ghost').forEach(b => {
    b.classList.remove('btn-accent');
    b.style.background = '';
    b.style.color = '';
    b.style.borderColor = '';
  });
  if (tabEl) {
    tabEl.classList.add('btn-accent');
  }

  const msgContainer = document.getElementById('viperChatMessages');
  msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-spinner fa-spin"></i><span style="font-size:13px;">Loading messages...</span></div>`;

  try {
    const res = await fetch(`/api/admin/chats/${chatId}/messages`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    renderViperChatMessages(data.messages || []);
  } catch (err) {
    msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-circle-exclamation" style="color:var(--danger);"></i><span style="font-size:14px;color:var(--danger);">Failed to load messages</span></div>`;
    console.error('Error loading chat messages:', err);
  }
}

function renderViperChatMessages(messages) {
  const msgContainer = document.getElementById('viperChatMessages');
  if (!messages.length) {
    msgContainer.innerHTML = `<div class="empty-state"><i class="fas fa-inbox"></i><span style="font-size:14px;">No messages in this chat</span></div>`;
    return;
  }

  msgContainer.innerHTML = messages.map((m, i) => {
    const isUser = m.role === 'user';
    return `
      <div style="display:flex;flex-direction:column;align-items:${isUser ? 'flex-end' : 'flex-start'};">
        <div class="chat-bubble ${isUser ? 'bubble-user' : 'bubble-bot'}" style="animation-delay:${i * 0.05}s;">
          ${m.message}
        </div>
        <div style="font-size:10px;color:var(--fg-muted);margin-top:4px;padding:0 4px;">
          ${isUser ? (selectedViperUser || 'User') : 'ViperAI'} · ${formatTime(m.created_at)}
        </div>
      </div>
    `;
  }).join('');

  setTimeout(() => msgContainer.scrollTop = msgContainer.scrollHeight, 100);
}

updateDashboard();
