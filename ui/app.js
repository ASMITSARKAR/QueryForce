// ui/app.js

/**
 * Custom SSE Fetch parser.
 * Replaces @microsoft/fetch-event-source to avoid bundling completely.
 * Solves T1 by natively allowing X-API-Key headers.
 */
async function fetchSSE(url, options, onMessage) {
    const response = await fetch(url, options);
    if (!response.ok) {
        if (response.status === 403 || response.status === 422) {
            localStorage.removeItem('qf_api_key');
            document.getElementById('auth-modal').classList.remove('hidden');
            throw new Error("Invalid API Key");
        }
        const text = await response.text();
        throw new Error(`HTTP ${response.status}: ${text}`);
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    
    while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep the last incomplete chunk in buffer
        
        for (const block of lines) {
            if (!block.trim()) continue;
            let eventType = "message";
            let dataStr = "";
            for (const line of block.split('\n')) {
                if (line.startsWith("event: ")) eventType = line.substring(7);
                else if (line.startsWith("data: ")) dataStr = line.substring(6);
            }
            if (dataStr) {
                try {
                    onMessage(eventType, JSON.parse(dataStr));
                } catch (e) {
                    console.error("Failed to parse SSE JSON", e, dataStr);
                }
            }
        }
    }
}

// --- DOM Elements ---
const DOM = {
    modal: document.getElementById('auth-modal'),
    authForm: document.getElementById('auth-form'),
    keyInput: document.getElementById('api-key-input'),
    btnLogout: document.getElementById('btn-logout'),
    
    form: document.getElementById('query-form'),
    input: document.getElementById('query-input'),
    submitBtn: document.getElementById('query-submit'),
    chatHistory: document.getElementById('chat-history'),
    
    sqlOutput: document.getElementById('sql-output'),
    badges: document.getElementById('status-badges'),
    badgeAst: document.getElementById('badge-ast'),
    badgeConf: document.getElementById('badge-conf'),
    
    table: document.getElementById('data-table'),
    tableHead: document.getElementById('data-table-head'),
    tableBody: document.getElementById('data-table-body'),
    tableEmpty: document.getElementById('data-empty'),
    btnExport: document.getElementById('btn-export')
};

let currentResults = null;

// --- Day 19 (T5): LocalStorage Vault Auth ---
function getApiKey() {
    return localStorage.getItem('qf_api_key');
}

function checkAuth() {
    if (!getApiKey()) {
        DOM.modal.classList.remove('hidden');
    } else {
        DOM.modal.classList.add('hidden');
    }
}

DOM.authForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const key = DOM.keyInput.value.trim();
    if (key) {
        localStorage.setItem('qf_api_key', key);
        checkAuth();
        DOM.keyInput.value = '';
    }
});

DOM.btnLogout.addEventListener('click', () => {
    localStorage.removeItem('qf_api_key');
    checkAuth();
});

checkAuth(); // Initial check

// --- Chat UI Helpers ---
function appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'flex items-end gap-4 flex-row-reverse animate-fade-in-up';
    div.innerHTML = `
        <div class="w-10 h-10 rounded-2xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 shadow-md">
            <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"></path></svg>
        </div>
        <div class="chat-bubble-user rounded-3xl rounded-br-sm px-6 py-4 max-w-[85%] text-white text-lg font-light leading-relaxed"></div>
    `;
    div.lastElementChild.textContent = text; // G7 safe
    DOM.chatHistory.appendChild(div);
    DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;
}

function createAiMessageBubble() {
    const div = document.createElement('div');
    div.className = 'flex items-end gap-4 animate-fade-in-up';
    div.innerHTML = `
        <div class="w-10 h-10 rounded-2xl bg-gradient-to-br from-blue-500/20 to-indigo-500/20 text-blue-400 flex items-center justify-center shrink-0 border border-blue-500/30 shadow-inner">
            <svg class="w-5 h-5 drop-shadow-[0_0_8px_rgba(59,130,246,0.8)]" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
        </div>
        <div class="chat-bubble-ai rounded-3xl rounded-bl-sm px-6 py-5 max-w-[85%] flex flex-col gap-3 min-w-[200px]">
            <div class="flex items-center gap-3 text-blue-400/80 text-sm font-medium status-text">
                <svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                Connecting...
            </div>
        </div>
    `;
    DOM.chatHistory.appendChild(div);
    DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;
    
    return {
        container: div,
        contentBox: div.lastElementChild,
        statusText: div.querySelector('.status-text')
    };
}

// SQL Syntax Highlighting (very basic client-side coloring)
function highlightSql(sql) {
    const keywords = ['SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'LIMIT', 'JOIN', 'LEFT', 'INNER', 'ON', 'AS', 'AND', 'OR', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN'];
    let colored = sql;
    keywords.forEach(kw => {
        const regex = new RegExp(`\\b${kw}\\b`, 'gi');
        colored = colored.replace(regex, `<span class="text-blue-400 font-semibold">$&</span>`);
    });
    return colored;
}

// --- Table Rendering ---
function renderTable(results) {
    currentResults = results;
    if (!results || results.length === 0) {
        DOM.table.classList.add('hidden');
        DOM.btnExport.classList.add('hidden');
        DOM.tableEmpty.classList.remove('hidden');
        DOM.tableEmpty.textContent = "Query executed successfully, but returned 0 rows.";
        return;
    }
    
    DOM.tableEmpty.classList.add('hidden');
    DOM.table.classList.remove('hidden');
    DOM.btnExport.classList.remove('hidden');
    
    const headers = Object.keys(results[0]);
    
    // Header
    const trHead = document.createElement('tr');
    headers.forEach(h => {
        const th = document.createElement('th');
        th.className = 'px-4 py-2.5 font-semibold whitespace-nowrap tracking-wider text-[11px]';
        th.textContent = h; // G7
        trHead.appendChild(th);
    });
    DOM.tableHead.innerHTML = '';
    DOM.tableHead.appendChild(trHead);
    
    // Body
    DOM.tableBody.innerHTML = '';
    results.forEach((row, i) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-800/80 bg-slate-900/40 transition-colors backdrop-blur-sm';
        headers.forEach(h => {
            const td = document.createElement('td');
            td.className = 'px-4 py-3 whitespace-nowrap border-b border-slate-800/50';
            td.textContent = row[h] !== null ? row[h] : 'NULL'; // G7
            tr.appendChild(td);
        });
        DOM.tableBody.appendChild(tr);
    });
}

// --- Query Execution Flow ---
DOM.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = DOM.input.value.trim();
    if (!query) return;
    
    DOM.input.value = '';
    DOM.submitBtn.disabled = true;
    DOM.submitBtn.innerHTML = `<svg class="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>`;
    
    appendUserMessage(query);
    const bubble = createAiMessageBubble();
    
    // Reset side panels
    DOM.sqlOutput.textContent = "Pipeline activated...";
    DOM.badges.classList.add('opacity-0');
    DOM.badges.classList.add('hidden');
    DOM.table.classList.add('hidden');
    DOM.tableEmpty.classList.remove('hidden');
    DOM.tableEmpty.textContent = "Awaiting execution...";
    DOM.btnExport.classList.add('hidden');
    
    try {
        await fetchSSE('/api/v1/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': getApiKey()
            },
            body: JSON.stringify({ query })
        }, (event, data) => {
            
            if (event === 'status') {
                bubble.statusText.textContent = data.msg;
            } 
            else if (event === 'data') {
                DOM.sqlOutput.innerHTML = highlightSql(data.sql);
                
                // Badges
                DOM.badges.classList.remove('hidden');
                setTimeout(() => DOM.badges.classList.remove('opacity-0'), 50);
                
                DOM.badgeAst.textContent = "VALID";
                DOM.badgeAst.className = "px-2.5 py-1 rounded-md text-[10px] font-bold tracking-widest uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 shadow-[0_0_10px_rgba(16,185,129,0.1)]";
                
                const confPct = Math.round(data.confidence * 100);
                DOM.badgeConf.textContent = `RAG ${confPct}%`;
                if (confPct < 20) {
                    DOM.badgeConf.className = "px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase bg-amber-500/20 text-amber-500 border border-amber-500/30";
                } else {
                    DOM.badgeConf.className = "px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase bg-blue-500/20 text-blue-400 border border-blue-500/30";
                }
                
                if (data.retries > 0) {
                    bubble.statusText.textContent = `Auto-corrected syntax after ${data.retries} retries...`;
                }
                
                renderTable(data.results);
            }
            else if (event === 'complete') {
                bubble.statusText.remove();
                
                const textEl = document.createElement('p');
                textEl.className = "text-slate-200 text-lg font-light leading-relaxed animate-fade-in-up";
                textEl.textContent = data.answer; // G7 safe insertion
                bubble.contentBox.appendChild(textEl);
            }
            else if (event === 'error') {
                bubble.statusText.remove();
                
                const errEl = document.createElement('div');
                errEl.className = "text-rose-400 bg-rose-950/30 border border-rose-900/40 px-5 py-4 rounded-2xl text-base font-medium shadow-inner flex items-center gap-3";
                errEl.innerHTML = `<svg class="w-5 h-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg> <span>${data.msg.replace(/</g, '&lt;')}</span>`;
                bubble.contentBox.appendChild(errEl);
                
                DOM.sqlOutput.textContent = "Execution halted due to error.";
                DOM.tableEmpty.textContent = "No data returned.";
                
                if (data.msg.includes("Security")) {
                    DOM.badges.classList.remove('hidden');
                    DOM.badges.classList.remove('opacity-0');
                    DOM.badgeAst.textContent = "BLOCKED";
                    DOM.badgeAst.className = "px-2.5 py-1 rounded-md text-[10px] font-bold tracking-widest uppercase bg-rose-500/10 text-rose-500 border border-rose-500/30 shadow-[0_0_10px_rgba(244,63,94,0.1)]";
                }
            }
            
            DOM.chatHistory.scrollTop = DOM.chatHistory.scrollHeight;
        });
        
    } catch (e) {
        if (e.message !== "Invalid API Key") {
            bubble.statusText.textContent = "Connection failed.";
            bubble.statusText.classList.remove('animate-pulse');
            bubble.statusText.classList.add('text-red-400');
        } else {
            bubble.container.remove();
        }
    } finally {
        DOM.submitBtn.disabled = false;
        DOM.submitBtn.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>`;
        DOM.input.focus();
    }
});

// CSV Export
DOM.btnExport.addEventListener('click', () => {
    if (!currentResults || currentResults.length === 0) return;
    
    const headers = Object.keys(currentResults[0]);
    const csvRows = [];
    csvRows.push(headers.map(h => `"${h.replace(/"/g, '""')}"`).join(','));
    
    for (const row of currentResults) {
        const values = headers.map(h => {
            const val = row[h] !== null ? String(row[h]) : '';
            return `"${val.replace(/"/g, '""')}"`;
        });
        csvRows.push(values.join(','));
    }
    
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `queryforce_export_${new Date().getTime()}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
});
