/* ===== STATE ===== */
let chats = [], activeId = null, delId = null, rnId = null, gen = false, compact = false;
let profile = { name: 'User', email: 'user@botbase.io' };
let settingsOpen = false;

/* ===== UTILS ===== */
const gid = () => Date.now().toString(36) + Math.random().toString(36).substr(2, 8);
const ft = iso => new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
function fd(iso) { const n = Date.now() - new Date(iso).getTime(); if (n < 6e4) return 'Just now'; if (n < 36e5) return Math.floor(n / 6e4) + 'm ago'; if (n < 864e5) return Math.floor(n / 36e5) + 'h ago'; if (n < 6048e5) return Math.floor(n / 864e5) + 'd ago'; return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
const ini = n => n.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
const esc = t => { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; };
function rt(t) {
    let h = esc(t);
    h = h.replace(/```(\w*)\n([\s\S]*?)```/g, (m, lang, code) => {
        const l = esc(lang || 'code');
        return `<div class="cb"><div class="cb-h"><span class="cb-l">${l}</span><button class="cb-c" onclick="copyCode(this)" title="Copy"><i class="fas fa-copy"></i></button></div><pre><code class="language-${l}">${code.replace(/\n$/, '')}</code></pre></div>`;
    });
    h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
    h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
    h = h.replace(/^- (.+)$/gm, '<li>$1</li>');
    h = h.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');
    h = h.replace(/^\d+\.\s(.+)$/gm, '<li>$1</li>');
    h = h.split('\n\n').map(b => { if (/^<(pre|ul|ol|li|div class="cb")/.test(b)) return b; return '<p>' + b.replace(/\n/g, '<br>') + '</p>'; }).join('');
    return h;
}
function copyCode(btn) {
    const box = btn.closest('.cb'); if (!box) return;
    const text = box.querySelector('pre').textContent;
    const done = () => { const i = btn.querySelector('i'); i.className = 'fas fa-check'; setTimeout(() => i.className = 'fas fa-copy', 1500); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
    else fallbackCopy(text, done);
}
function fallbackCopy(text, done) {
    const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); } catch (e) { } ta.remove(); done();
}
function toast(msg) { const c = document.getElementById('toasts'), e = document.createElement('div'); e.className = 'tt tt-s'; e.textContent = msg; c.appendChild(e); setTimeout(() => e.remove(), 3200); }
function save() { localStorage.setItem('bb_chats', JSON.stringify(chats)); localStorage.setItem('bb_profile', JSON.stringify(profile)); }
function load() { const d = localStorage.getItem('bb_chats'); chats = d ? JSON.parse(d) : []; const p = localStorage.getItem('bb_profile'); if (p) profile = JSON.parse(p); }

/* ===== THEME ===== */
function setTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem('bb_theme', t);
    document.querySelector('#themeToggle input').checked = (t === 'dark');
    document.getElementById('dotDark').classList.toggle('active', t === 'dark');
    document.getElementById('dotLight').classList.toggle('active', t === 'light');
}

/* ===== PROFILE ===== */
function togProfile() {
    const drop = document.getElementById('pfDrop');
    const btn = document.getElementById('pfBtn');
    const isOpen = drop.classList.contains('open');
    drop.classList.toggle('open');
    btn.classList.toggle('expanded');
    if (!isOpen) closeSettings();
    updateProfileStats();
}
function updateProfile() {
    profile.name = document.getElementById('pfNameIn').value.trim() || 'User';
    profile.email = document.getElementById('pfEmailIn').value.trim() || 'user@botbase.io';
    document.getElementById('pfName').textContent = profile.name;
    document.getElementById('pfEmail').textContent = profile.email;
    document.getElementById('pfAv').textContent = ini(profile.name);
    save();
}
function updateProfileStats() {
    document.getElementById('pfStatChats').textContent = chats.length;
    document.getElementById('pfStatMsgs').textContent = chats.reduce((s, c) => s + c.messages.length, 0);
    if (chats.length > 0) {
        const d = Math.max(1, Math.ceil((Date.now() - new Date(chats[chats.length - 1].createdAt).getTime()) / 864e5));
        document.getElementById('pfStatDays').textContent = d;
    } else {
        document.getElementById('pfStatDays').textContent = '0';
    }
}

/* ===== SETTINGS ===== */
function togSettings() {
    const panel = document.getElementById('setPanel');
    panel.classList.contains('open') ? closeSettings() : openSettings();
}
function openSettings() {
    const panel = document.getElementById('setPanel');
    const btn = document.getElementById('setTbBtn');
    panel.classList.add('open');
    btn.classList.add('set-active');
    settingsOpen = true;
    document.getElementById('pfDrop').classList.remove('open');
    document.getElementById('pfBtn').classList.remove('expanded');
    if (innerWidth <= 768) document.getElementById('sb').classList.add('open');
}
function closeSettings() {
    const panel = document.getElementById('setPanel');
    const btn = document.getElementById('setTbBtn');
    panel.classList.remove('open');
    btn.classList.remove('set-active');
    settingsOpen = false;
}
function togCompact(on) {
    compact = on;
    document.querySelectorAll('.mg').forEach(m => { m.style.marginBottom = on ? '10px' : '20px'; });
    localStorage.setItem('bb_compact', on ? '1' : '0');
    toast(on ? 'Compact mode on' : 'Compact mode off');
}

/* ===== SIDEBAR ===== */
function togSB() { document.getElementById('sb').classList.toggle('open'); }
function renderSB() {
    const el = document.getElementById('sbList'), q = document.getElementById('sbSrch').value.toLowerCase();
    const fl = chats.filter(c => c.title.toLowerCase().includes(q));
    if (!fl.length) { el.innerHTML = `<div class="sb-empty"><i class="fas fa-comments"></i><span>${q ? 'No matches' : 'No conversations yet'}</span></div>`; return; }
    const now = Date.now(), td = [], wk = [], ol = [];
    fl.forEach(c => { const a = now - new Date(c.createdAt).getTime(); if (a < 864e5) td.push(c); else if (a < 6048e5) wk.push(c); else ol.push(c); });
    const g = (l, items) => {
        if (!items.length) return '';
        let s = `<div class="sb-lbl">${l}</div>`;
        items.forEach(c => {
            s += `<div class="sb-it ${c.id === activeId ? 'on' : ''}" onclick="selChat('${c.id}')"><div class="sb-it-i"><i class="fas fa-message"></i></div><div style="flex:1;min-width:0"><div class="sb-it-t">${esc(c.title)}</div><div class="sb-it-m">${c.messages.length} msgs · ${fd(c.createdAt)}</div></div><button class="sb-it-d" onclick="event.stopPropagation();openDlId('${c.id}')" title="Delete"><i class="fas fa-xmark"></i></button></div>`;
        });
        return s;
    };
    el.innerHTML = g('Today', td) + g('This Week', wk) + g('Older', ol);
}

/* ===== CHAT ===== */
function selChat(id) {
    if (!profile.email || profile.email === 'user@botbase.io') {
        chats = chats.filter(c => c.id === id); save();
    }
    activeId = id;
    const c = chats.find(x => x.id === id); if (!c) return;
    document.getElementById('tbT').textContent = c.title;
    renderMsgs(c); renderSB();
    if (innerWidth <= 768) document.getElementById('sb').classList.remove('open');
}
function showWelcome() {
    activeId = null;
    document.getElementById('tbT').textContent = 'New Chat';
    document.getElementById('msIn').innerHTML = `<div class="wc"><div class="wc-ic"><i class="fas fa-robot"></i></div><h2>How can I help you?</h2><p>Ask me anything about your uploaded documents — company policies, API docs, onboarding, troubleshooting, and more.</p><div class="wc-g"><div class="wc-c" onclick="useS('What is the remote work policy?')"><div class="wc-c-t">Remote Work Policy</div><div class="wc-c-d">Rules for working from home</div></div><div class="wc-c" onclick="useS('How do I authenticate with the API?')"><div class="wc-c-t">API Authentication</div><div class="wc-c-d">Getting started with the API</div></div><div class="wc-c" onclick="useS('What happens on my first day?')"><div class="wc-c-t">First Day Guide</div><div class="wc-c-d">New employee onboarding steps</div></div><div class="wc-c" onclick="useS('How do I fix a 500 error on checkout?')"><div class="wc-c-t">Troubleshoot Errors</div><div class="wc-c-d">Debug common checkout issues</div></div></div></div>`;
    renderSB();
}
function useS(t) { const i = document.getElementById('cIn'); i.value = t; aH(i); document.getElementById('sBtn').disabled = false; send(); }
function renderMsgs(c) {
    const el = document.getElementById('msIn');
    if (!c.messages.length) { showWelcome(); return; }
    const mb = compact ? '10px' : '20px';
    el.innerHTML = '';
    c.messages.forEach(msg => {
        const wrap = document.createElement('div');
        wrap.className = 'mg' + (msg.role === 'user' ? ' mg-user' : '');
        wrap.style.marginBottom = mb;
        if (msg.role === 'user') {
            const avatar = `<div class="mg-a u">${ini(profile.name)}</div>`;
            const header = `<div class="mg-h">${avatar}<span class="mg-n">${esc(profile.name)}</span><span class="mg-t">${ft(msg.time)}</span></div>`;
            let fileChipsHtml = '';
            if (msg.files && msg.files.length) {
                fileChipsHtml = '<div class="mg-files">' + msg.files.map(f => {
                    const name = typeof f === 'string' ? f : (f.name || '');
                    const isImg = typeof f === 'object' && f.type ? f.type.startsWith('image/') : /\.(png|jpe?g|gif|webp|svg)$/i.test(name);
                    const icon = isImg ? '<i class="fas fa-image" style="font-size:14px;color:var(--accent)"></i>' : '<i class="fas fa-file" style="font-size:14px;color:var(--accent)"></i>';
                    return `<span class="ia-file-chip" style="pointer-events:none">${icon}<span>${esc(name)}</span></span>`;
                }).join('') + '</div>';
            }
            wrap.innerHTML = header + `<div class="mg-b">${fileChipsHtml}<p>${esc(msg.text || '')}</p></div>`;
        } else {
            const header = `<div class="mg-h"><div class="mg-a b"><i class="fas fa-robot" style="font-size:10px"></i></div><span class="mg-n">ViperAI</span><span class="mg-t">${ft(msg.time)}</span></div>`;
            wrap.innerHTML = header;
            const body = document.createElement('div');
            body.className = 'mg-b';
            body.innerHTML = rt(msg.text || '');
            wrap.appendChild(body);
        }
        el.appendChild(wrap);
    });
    hlCode(el);
    document.getElementById('ms').scrollTop = 1e6;
}
function hlCode(root) {
    if (typeof hljs === 'undefined') return;
    root.querySelectorAll('.cb pre code').forEach(b => {
        if (b.dataset.hl) return;
        const match = b.className.match(/language-(\w+)/);
        const lang = match ? match[1] : null;
        const text = b.textContent;
        try {
            const res = (lang && hljs.getLanguage(lang))
                ? hljs.highlight(text, { language: lang, ignoreIllegals: true })
                : hljs.highlightAuto(text);
            b.innerHTML = res.value;
        } catch (e) {
            b.textContent = text;
        }
        b.classList.add('hljs');
        b.dataset.hl = '1';
    });
}

/* ===== SEND ===== */
function iKey(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } document.getElementById('sBtn').disabled = !e.target.value.trim(); }
function aH(el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 140) + 'px'; document.getElementById('sBtn').disabled = !el.value.trim(); }
function send() {
    const inp = document.getElementById('cIn'), txt = inp.value.trim();
    if (!txt || gen) return;
    if (!activeId) {
        const c = { id: gid(), title: txt.length > 52 ? txt.slice(0, 49) + '...' : txt, messages: [], createdAt: new Date().toISOString() };
        if (!profile.email || profile.email === 'user@botbase.io') { chats = []; }
        chats.unshift(c); activeId = c.id; document.getElementById('tbT').textContent = c.title;
    }
    const chat = chats.find(c => c.id === activeId); if (!chat) return;
    const filesToSend = [...attachedFiles];
    attachedFiles = []; renderFilePreview();
    const filesMeta = filesToSend.map(f => ({ name: f.name, type: f.type }));
    chat.messages.push({ role: 'user', text: txt, time: new Date().toISOString(), files: filesMeta }); save();
    inp.value = ''; inp.style.height = 'auto'; document.getElementById('sBtn').disabled = true;
    renderMsgs(chat); renderSB(); updateProfileStats();
    gen = true;
    const inner = document.getElementById('msIn');
    const tip = document.createElement('div'); tip.className = 'ty'; tip.id = 'typI'; tip.innerHTML = '<span></span><span></span><span></span>';
    inner.appendChild(tip); document.getElementById('ms').scrollTop = 1e6;

    let fetchOpts;
    if (filesToSend.length) {
        const fd = new FormData();
        fd.append('message', txt);
        fd.append('chat_id', chat.serverChatId || '');
        fd.append('title', chat.title);
        fd.append('user_email', profile.email);
        fd.append('user_name', profile.name);
        filesToSend.forEach(f => fd.append('files', f));
        fetchOpts = { method: 'POST', body: fd };
    } else {
        fetchOpts = {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: txt, chat_id: chat.serverChatId || null, title: chat.title, user_email: profile.email, user_name: profile.name })
        };
    }
    fetch('/chat', fetchOpts)
        .then(r => r.json())
        .then(d => {
            const resp = d.answer || 'Sorry, no answer was returned.';
            if (d.chat_id && !chat.serverChatId) { chat.serverChatId = d.chat_id; save(); }
            chat.messages.push({ role: 'bot', text: resp, time: new Date().toISOString() });
            save(); gen = false; renderMsgs(chat); updateProfileStats(); speakText(resp);
        })
        .catch(() => {
            chat.messages.push({ role: 'bot', text: 'Sorry, I could not reach the server. Please try again.', time: new Date().toISOString() });
            save(); gen = false; renderMsgs(chat); updateProfileStats();
        });
}

/* ===== NEW / RENAME / DELETE ===== */
function newChat() {
    if (!profile.email || profile.email === 'user@botbase.io') { chats = []; save(); }
    showWelcome(); document.getElementById('cIn').focus();
    if (innerWidth <= 768) document.getElementById('sb').classList.remove('open');
}
function saveRn() { if (!rnId) return; const c = chats.find(x => x.id === rnId), v = document.getElementById('rnIn').value.trim(); if (c && v) { c.title = v; save(); document.getElementById('tbT').textContent = v; renderSB(); toast('Chat renamed'); } closeMo('rnMo'); }
document.getElementById('rnIn').addEventListener('keydown', e => { if (e.key === 'Enter') saveRn(); if (e.key === 'Escape') closeMo('rnMo'); });
function openDlId(id) { delId = id; document.getElementById('dlTitle').textContent = 'Delete Chat'; document.getElementById('dlText').textContent = 'This conversation will be permanently deleted.'; document.getElementById('dlConfirm').textContent = 'Delete'; document.getElementById('dlConfirm').onclick = doDel; document.getElementById('dlMo').classList.add('on'); }
function doDel() { if (!delId) return; chats = chats.filter(c => c.id !== delId); save(); if (activeId === delId) { if (chats.length) selChat(chats[0].id); else showWelcome(); } renderSB(); updateProfileStats(); closeMo('dlMo'); toast('Chat deleted'); }

/* ===== CLEAR ALL ===== */
function clearAll() {
    if (!chats.length) { toast('No chats to clear'); return; }
    document.getElementById('dlTitle').textContent = 'Clear All Chats';
    document.getElementById('dlText').textContent = 'All conversations will be permanently deleted. This cannot be undone.';
    document.getElementById('dlConfirm').textContent = 'Clear All';
    document.getElementById('dlConfirm').onclick = function () {
        chats = []; activeId = null; save(); showWelcome(); renderSB(); updateProfileStats(); closeMo('dlMo'); closeSettings(); toast('All chats cleared');
        document.getElementById('dlConfirm').onclick = doDel;
    };
    document.getElementById('dlMo').classList.add('on');
}

/* ===== MODAL ===== */
function closeMo(id) { document.getElementById(id).classList.remove('on'); delId = null; rnId = null; }
document.querySelectorAll('.mo').forEach(m => { m.addEventListener('click', e => { if (e.target === m && m.id !== 'authPopup') { m.classList.remove('on'); delId = null; rnId = null; } }); });

/* Close sidebar on outside click (mobile) */
document.addEventListener('click', e => {
    if (innerWidth <= 768 && document.getElementById('sb').classList.contains('open') && !document.getElementById('sb').contains(e.target) && !e.target.closest('.tb-ham') && !e.target.closest('#setTbBtn')) {
        document.getElementById('sb').classList.remove('open');
    }
});

/* ===== FILE ATTACHMENTS ===== */
let attachedFiles = [];
function onFileSelect(input) {
    Array.from(input.files).forEach(f => attachedFiles.push(f));
    input.value = '';
    renderFilePreview();
}
function renderFilePreview() {
    const el = document.getElementById('filePreview');
    if (!attachedFiles.length) { el.innerHTML = ''; return; }
    el.innerHTML = attachedFiles.map((f, i) => {
        const isImg = f.type.startsWith('image/');
        const preview = isImg ? `<img src="${URL.createObjectURL(f)}">` : `<i class="fas fa-file" style="font-size:16px;color:var(--accent)"></i>`;
        return `<div class="ia-file-chip">${preview}<span title="${esc(f.name)}">${esc(f.name)}</span><button onclick="removeFile(${i})"><i class="fas fa-xmark"></i></button></div>`;
    }).join('');
}
function removeFile(i) { attachedFiles.splice(i, 1); renderFilePreview(); }

/* ===== MICROPHONE / SPEECH ===== */
let recognition = null, micActive = false;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
function toggleMic() {
    if (!SpeechRecognition) { toast('Speech recognition not supported in this browser'); return; }
    if (micActive) { recognition.stop(); return; }
    recognition = new SpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.onstart = () => { micActive = true; document.getElementById('micBtn').classList.add('recording'); };
    recognition.onresult = e => {
        const txt = e.results[0][0].transcript;
        const inp = document.getElementById('cIn');
        inp.value = (inp.value + ' ' + txt).trim();
        aH(inp);
        document.getElementById('sBtn').disabled = !inp.value.trim();
    };
    recognition.onend = () => { micActive = false; document.getElementById('micBtn').classList.remove('recording'); };
    recognition.onerror = () => { micActive = false; document.getElementById('micBtn').classList.remove('recording'); };
    recognition.start();
}
function speakText(text) {
    if (!window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    const plain = text.replace(/<[^>]+>/g, '').replace(/```[\s\S]*?```/g, 'code block').trim();
    const utt = new SpeechSynthesisUtterance(plain);
    utt.lang = 'en-US';
    utt.rate = 1;
    window.speechSynthesis.speak(utt);
}

/* ===== PWA INSTALL ===== */
const isStandalone = () => window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
let _installPrompt = null;
window.addEventListener('beforeinstallprompt', e => {
    e.preventDefault();
    if (isStandalone()) return;
    _installPrompt = e;
    setTimeout(() => {
        if (!isStandalone()) document.getElementById('installPopup').style.display = 'block';
        setInterval(() => {
            if (_installPrompt && !isStandalone()) document.getElementById('installPopup').style.display = 'block';
        }, 60000);
    }, 3000);
});
function installApp() {
    if (!_installPrompt) return;
    _installPrompt.prompt();
    _installPrompt.userChoice.then(() => {
        _installPrompt = null;
        document.getElementById('installPopup').style.display = 'none';
    });
}
function dismissInstall() { document.getElementById('installPopup').style.display = 'none'; }
window.addEventListener('appinstalled', () => { document.getElementById('installPopup').style.display = 'none'; });

/* ===== INIT ===== */
setTheme(localStorage.getItem('bb_theme') || 'dark');
if (localStorage.getItem('bb_compact') === '1') { compact = true; document.getElementById('compactToggle').checked = true; }
showWelcome();
document.getElementById('cIn').focus();

fetch('/api/auth/me')
    .then(r => r.json())
    .then(u => {
        if (u.logged_in) {
            load();
            profile.name = u.name;
            profile.email = u.email;
            document.getElementById('pfName').textContent = u.name;
            document.getElementById('pfEmail').textContent = u.email;
            document.getElementById('pfAv').textContent = ini(u.name);
            document.getElementById('sbAuth').style.display = 'none';
            document.getElementById('sbProfile').style.display = 'block';
            document.getElementById('setLogoutBtn').style.display = 'flex';
            document.getElementById('setLogoutDivider').style.display = 'block';
            if (chats.length) { selChat(chats[0].id); updateProfileStats(); renderSB(); }
            const safeEmail = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/.test(u.email) ? u.email : '';
            if (!safeEmail) return;
            fetch('/api/chats?email=' + encodeURIComponent(safeEmail))
                .then(r => r.json())
                .then(data => {
                    if (data.chats && data.chats.length) {
                        chats = data.chats.map(c => ({
                            id: 'db_' + c.id,
                            serverChatId: c.id,
                            title: c.title,
                            createdAt: c.createdAt,
                            messages: c.messages
                        }));
                        save();
                        selChat(chats[0].id);
                        updateProfileStats();
                        renderSB();
                    }
                });
        } else {
            chats = []; activeId = null;
            profile = { name: 'User', email: 'user@botbase.io' };
            localStorage.removeItem('bb_chats');
            localStorage.removeItem('bb_profile');
            document.getElementById('sbAuth').style.display = 'block';
            document.getElementById('sbProfile').style.display = 'none';
            showWelcome(); renderSB(); updateProfileStats();
            const authPopup = document.getElementById('authPopup');
            const maybeLaterBtn = document.getElementById('maybeLaterBtn');
            authPopup.classList.add('on');
            if (isStandalone()) {
                authPopup.classList.add('locked');
                maybeLaterBtn.style.display = 'none';
            } else {
                let popCount = 1;
                const popTimer = setInterval(() => {
                    popCount++;
                    authPopup.classList.add('on');
                    if (popCount >= 2) {
                        clearInterval(popTimer);
                        authPopup.classList.add('locked');
                        maybeLaterBtn.style.display = 'none';
                    }
                }, 60000);
            }
        }
    })
    .catch(() => {
        const sbAuth = document.getElementById('sbAuth');
        const sbProfile = document.getElementById('sbProfile');
        if (sbAuth) sbAuth.style.display = 'block';
        if (sbProfile) sbProfile.style.display = 'none';
    });

function doLogout() {
    fetch('/api/auth/logout', { method: 'POST' })
        .then(r => r.json())
        .then(d => {
            chats = []; activeId = null;
            profile = { name: 'User', email: 'user@botbase.io' };
            localStorage.removeItem('bb_chats');
            localStorage.removeItem('bb_profile');
            window.location.href = d.redirect;
        });
}
