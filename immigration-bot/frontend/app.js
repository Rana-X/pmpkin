// ── State ──
let chatSessions = [];
let activeSessionId = null;
let chatCounter = 0;
let selectedFiles = [];
let sidebarOpen = true;
let currentTab = 'chat';
let investigationData = null;
let investigationActive = false;
let canInvestigate = false;
let readyToInvestigate = false;

const WELCOME_HTML = `
    <div class="welcome-screen" id="welcome">
        <div class="welcome-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
            </svg>
        </div>
        <h1>Welcome to Pumpkin</h1>
    </div>
`;

// ── DOM Elements ──
const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const fileInput = document.getElementById('file-input');
const filesList = document.getElementById('files-list');
const filesZone = document.getElementById('files-zone');
const uploadZone = document.getElementById('upload-zone');
const processingIndicator = document.getElementById('processing-indicator');
const progressFill = document.getElementById('progress-fill');
const processingTitle = document.getElementById('processing-title');
const processingSubtitle = document.getElementById('processing-subtitle');

// ── Sidebar Functions ──
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    const menuBtn = document.getElementById('menu-toggle');
    const isMobile = window.innerWidth <= 768;

    if (isMobile) {
        sidebar.classList.toggle('mobile-open');
        overlay.classList.toggle('active');
    } else {
        sidebarOpen = !sidebarOpen;
        sidebar.classList.toggle('collapsed');
        menuBtn.classList.toggle('visible', !sidebarOpen);
    }
}

// ── Tab Switching ──
function switchTab(tabName) {
    currentTab = tabName;

    // Update sidebar menu items
    document.querySelectorAll('.sidebar-menu-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.tab === tabName) {
            item.classList.add('active');
        }
    });

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Close sidebar on mobile
    if (window.innerWidth <= 768) {
        const sidebar = document.getElementById('sidebar');
        sidebar.classList.remove('mobile-open');
        document.getElementById('sidebar-overlay').classList.remove('active');
    }
}

// ── Multi-Session Chat ──
function initChats() {
    createNewChat();
}

function createNewChat() {
    if (activeSessionId) {
        saveCurrentChat();
    }

    chatCounter++;
    const id = 'session_' + Date.now();

    chatSessions.push({ id, name: 'New Chat', html: null, files: [] });
    activeSessionId = id;

    getScrollWrapper().innerHTML = WELCOME_HTML;

    selectedFiles = [];
    renderFilesList();
    messageInput.value = '';
    autoResize(messageInput);
    hideProcessing();
    renderChatList();
    messageInput.focus();

    // Close sidebar on mobile after creating
    if (window.innerWidth <= 768) {
        document.getElementById('sidebar').classList.remove('mobile-open');
        document.getElementById('sidebar-overlay').classList.remove('active');
    }
}

function saveCurrentChat() {
    const session = chatSessions.find(s => s.id === activeSessionId);
    if (session) {
        session.html = getScrollWrapper().innerHTML;
        session.files = selectedFiles;
    }
}

function switchToChat(id) {
    if (id === activeSessionId) return;

    saveCurrentChat();
    activeSessionId = id;

    const session = chatSessions.find(s => s.id === id);
    getScrollWrapper().innerHTML = session.html || WELCOME_HTML;

    selectedFiles = session.files || [];
    renderFilesList();
    messageInput.value = '';
    autoResize(messageInput);
    hideProcessing();
    renderChatList();
    chatContainer.scrollTop = chatContainer.scrollHeight;
    messageInput.focus();

    if (window.innerWidth <= 768) {
        document.getElementById('sidebar').classList.remove('mobile-open');
        document.getElementById('sidebar-overlay').classList.remove('active');
    }
}

async function deleteChat(id) {
    try {
        const formData = new FormData();
        formData.append('session_id', id);
        await fetch('/reset', { method: 'POST', body: formData });
    } catch (e) {}

    if (chatSessions.length <= 1) {
        chatSessions[0].name = 'New Chat';
        chatSessions[0].html = null;
        getScrollWrapper().innerHTML = WELCOME_HTML;
        selectedFiles = [];
        renderFilesList();
        messageInput.value = '';
        hideProcessing();
        renderChatList();
        return;
    }

    const idx = chatSessions.findIndex(s => s.id === id);
    chatSessions.splice(idx, 1);

    if (id === activeSessionId) {
        const newIdx = Math.min(idx, chatSessions.length - 1);
        activeSessionId = chatSessions[newIdx].id;
        const session = chatSessions[newIdx];
        getScrollWrapper().innerHTML = session.html || WELCOME_HTML;
        selectedFiles = [];
        renderFilesList();
        messageInput.value = '';
        hideProcessing();
    }

    renderChatList();
    messageInput.focus();
}

function renderChatList() {
    const list = document.getElementById('chat-list');
    if (!list) return;

    list.innerHTML = chatSessions.map(session => `
        <div class="chat-list-item ${session.id === activeSessionId ? 'active' : ''}"
             onclick="switchToChat('${session.id}')">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <span class="chat-list-name">${escapeHtml(session.name)}</span>
            <button class="chat-list-delete" onclick="event.stopPropagation(); deleteChat('${session.id}')" title="Delete">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>
    `).join('');
}

// ── File Handling ──
function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    addFilesToList(files);
    event.target.value = ''; // Reset input
}

function addFilesToList(files) {
    files.forEach(file => {
        if (!selectedFiles.find(f => f.name === file.name)) {
            selectedFiles.push(file);
        }
    });
    renderFilesList();
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    renderFilesList();
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function renderFilesList() {
    if (selectedFiles.length === 0) {
        filesList.classList.remove('active');
        filesZone.classList.remove('active');
        filesList.innerHTML = '';
        return;
    }

    filesList.classList.add('active');
    filesZone.classList.remove('active');

    filesList.innerHTML = selectedFiles.map((file, index) => `
        <div class="file-item">
            <div class="file-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                </svg>
            </div>
            <div class="file-info">
                <div class="file-name">${escapeHtml(file.name)}</div>
                <div class="file-size">${formatFileSize(file.size)}</div>
            </div>
            <button class="file-remove" onclick="removeFile(${index})" title="Remove file">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
        </div>
    `).join('');
}

// ── Drag and Drop ──
uploadZone.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', handleFileSelect);

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
});

uploadZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    const files = Array.from(e.dataTransfer.files);
    addFilesToList(files);
});

// Show upload zone
function showUploadZone() {
    filesZone.classList.add('active');
}

// ── Progress Bar ──
function showProcessing(title, subtitle) {
    processingIndicator.classList.add('active');
    processingTitle.textContent = title;
    processingSubtitle.textContent = subtitle;
    progressFill.style.width = '0%';

    // Animate progress
    setTimeout(() => progressFill.style.width = '30%', 100);
}

function updateProgress(percent, title, subtitle) {
    progressFill.style.width = percent + '%';
    if (title) processingTitle.textContent = title;
    if (subtitle) processingSubtitle.textContent = subtitle;
}

function hideProcessing() {
    processingIndicator.classList.remove('active');
    progressFill.style.width = '0%';
}

// ── Message Functions ──
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
}

function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function getScrollWrapper() {
    return document.querySelector('.chat-scroll-wrapper');
}

function addMessage(content, role, downloadUrl = null) {
    const welcome = document.getElementById('welcome');
    if (welcome) welcome.remove();

    const wrapper = getScrollWrapper();
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    if (role === 'assistant') {
        const formattedContent = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        const downloadButton = downloadUrl ? `
            <a href="${downloadUrl}" class="download-btn" download>
                📥 Download Filled Form
            </a>
        ` : '';

        messageDiv.innerHTML = `
            <div class="avatar assistant">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
                    <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                    <line x1="9" y1="9" x2="9.01" y2="9"/>
                    <line x1="15" y1="9" x2="15.01" y2="9"/>
                </svg>
            </div>
            <div class="message-content">
                <div class="message-bubble">${formattedContent}</div>
                ${downloadButton}
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="avatar user">You</div>
            <div class="message-content">
                <div class="message-bubble">${escapeHtml(content)}</div>
            </div>
        `;
    }

    wrapper.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;

    // Name the chat after the first user message
    if (role === 'user') {
        const session = chatSessions.find(s => s.id === activeSessionId);
        if (session && session.name === 'New Chat') {
            session.name = content.length > 30 ? content.substring(0, 30) + '...' : content;
            renderChatList();
        }
    }
}

function addTypingIndicator() {
    const wrapper = getScrollWrapper();
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant';
    typingDiv.id = 'typing-indicator';
    typingDiv.innerHTML = `
        <div class="avatar assistant">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
            </svg>
        </div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    wrapper.appendChild(typingDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeTypingIndicator() {
    const typing = document.getElementById('typing-indicator');
    if (typing) typing.remove();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function buildMessageHTML(content, role, downloadUrl = null) {
    if (role === 'assistant') {
        const formattedContent = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        const downloadButton = downloadUrl ? `
            <a href="${downloadUrl}" class="download-btn" download>📥 Download Filled Form</a>
        ` : '';
        return `<div class="message assistant">
            <div class="avatar assistant">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
                    <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                    <line x1="9" y1="9" x2="9.01" y2="9"/>
                    <line x1="15" y1="9" x2="15.01" y2="9"/>
                </svg>
            </div>
            <div class="message-content">
                <div class="message-bubble">${formattedContent}</div>
                ${downloadButton}
            </div>
        </div>`;
    } else {
        return `<div class="message user">
            <div class="avatar user">You</div>
            <div class="message-content">
                <div class="message-bubble">${escapeHtml(content)}</div>
            </div>
        </div>`;
    }
}

function appendToStoredSession(sessionId, content, role, downloadUrl) {
    const session = chatSessions.find(s => s.id === sessionId);
    if (!session || !session.html) return;
    const temp = document.createElement('div');
    temp.innerHTML = session.html;
    const typing = temp.querySelector('#typing-indicator');
    if (typing) typing.remove();
    temp.innerHTML += buildMessageHTML(content, role, downloadUrl);
    session.html = temp.innerHTML;
}

// ── Send Message ──
async function sendMessage() {
    const message = messageInput.value.trim();

    if (!message && selectedFiles.length === 0) return;

    const originSessionId = activeSessionId;
    const onOrigin = () => activeSessionId === originSessionId;

    // Disable input
    messageInput.disabled = true;
    sendBtn.disabled = true;

    try {
        if (selectedFiles.length > 0) {
            // Process files sequentially
            for (let i = 0; i < selectedFiles.length; i++) {
                const file = selectedFiles[i];

                addMessage(`📄 ${file.name}`, 'user');

                showProcessing(
                    `Processing ${file.name}...`,
                    `File ${i + 1} of ${selectedFiles.length}`
                );

                updateProgress(50, `Processing ${file.name}...`, 'Analyzing with AI');

                addTypingIndicator();

                const formData = new FormData();
                formData.append('file', file);
                formData.append('session_id', originSessionId);

                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (onOrigin()) {
                    updateProgress(100, 'Complete!', 'Processing next file...');
                    hideProcessing();
                    removeTypingIndicator();

                    if (data.error) {
                        addMessage(`Error: ${data.error}`, 'assistant');
                    } else {
                        addMessage(data.response, 'assistant', data.file_url || null);
                    }

                    // Mark investigation as available when both docs are uploaded
                    if (data.ready_to_investigate || data.state === 'profile_uploaded') {
                        canInvestigate = true;
                        const btn = document.getElementById('investigate-btn');
                        btn.classList.add('glow-active');
                    }
                } else {
                    // User switched sessions — route response to origin session
                    const msg = data.error ? `Error: ${data.error}` : data.response;
                    appendToStoredSession(originSessionId, msg, 'assistant', data.file_url || null);
                }

                // Small delay between files
                if (i < selectedFiles.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }

            // Clear files after processing
            selectedFiles = [];
            renderFilesList();

        } else if (message) {
            // If investigate is armed, send context then kick off investigation
            if (readyToInvestigate && canInvestigate) {
                addMessage(message, 'user');
                messageInput.value = '';
                autoResize(messageInput);
                addTypingIndicator();

                // Send as additional context
                try {
                    const resp = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message, session_id: originSessionId })
                    });
                    const data = await resp.json();
                    removeTypingIndicator();
                    addMessage(data.response, 'assistant');
                } catch (err) {
                    removeTypingIndicator();
                }

                // Small pause then start investigation
                messageInput.disabled = false;
                sendBtn.disabled = false;
                await new Promise(r => setTimeout(r, 800));
                startInvestigation();
                return;
            }

            // Check for "send to candidate" patterns
            const sendToCandidate = /send\s+(?:it\s+)?(?:to\s+)?(?:the\s+)?candidate/i.test(message)
                || /cool\s+send\s+it/i.test(message)
                || /send\s+(?:the\s+)?report/i.test(message)
                || /email\s+(?:the\s+)?candidate/i.test(message);

            if (sendToCandidate && investigationData) {
                addMessage(message, 'user');
                messageInput.value = '';
                autoResize(messageInput);
                addTypingIndicator();

                try {
                    const resp = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ message, session_id: originSessionId })
                    });
                    const data = await resp.json();
                    removeTypingIndicator();
                    addMessage(data.response, 'assistant');
                } catch (err) {
                    removeTypingIndicator();
                    addMessage('Failed to send report: ' + err.message, 'assistant');
                }
                messageInput.disabled = false;
                sendBtn.disabled = false;
                messageInput.focus();
                return;
            }

            // Check for email send command
            const emailMatch = message.match(/send\s+(?:this\s+)?(?:to\s+)?(\S+@\S+\.\S+)/i);
            if (emailMatch && investigationData) {
                addMessage(message, 'user');
                messageInput.value = '';
                autoResize(messageInput);
                const emailInput = document.getElementById('inv-email-input');
                if (emailInput) emailInput.value = emailMatch[1];
                await sendReport(0);
                addMessage(`Report ready for ${emailMatch[1]}`, 'assistant');
                messageInput.disabled = false;
                sendBtn.disabled = false;
                messageInput.focus();
                return;
            }

            // Send text message
            addMessage(message, 'user');
            messageInput.value = '';
            autoResize(messageInput);

            addTypingIndicator();

            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    session_id: originSessionId
                })
            });

            const data = await response.json();

            if (onOrigin()) {
                removeTypingIndicator();

                if (data.error) {
                    addMessage(`Error: ${data.error}`, 'assistant');
                } else {
                    addMessage(data.response, 'assistant');
                }
            } else {
                const msg = data.error ? `Error: ${data.error}` : data.response;
                appendToStoredSession(originSessionId, msg, 'assistant');
            }
        }
    } catch (error) {
        if (onOrigin()) {
            hideProcessing();
            removeTypingIndicator();
            addMessage(`Connection error: ${error.message}`, 'assistant');
        } else {
            appendToStoredSession(originSessionId, `Connection error: ${error.message}`, 'assistant');
        }
    }

    // Re-enable input
    messageInput.disabled = false;
    sendBtn.disabled = false;
    messageInput.focus();
}

// ── Investigation ──

function scrollToBottom() {
    const threshold = 150;
    const distanceFromBottom = chatContainer.scrollHeight - chatContainer.scrollTop - chatContainer.clientHeight;
    if (distanceFromBottom < threshold) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

function toggleInvestigateArm() {
    if (!canInvestigate) {
        addMessage('Please upload your documents first (RFE notice and candidate profile) before running the investigation.', 'assistant');
        return;
    }
    startInvestigation();
}

function deactivateInvestigateGlow() {
    const btn = document.getElementById('investigate-btn');
    btn.classList.remove('glow-active');
    readyToInvestigate = false;
}

async function startInvestigation() {
    if (investigationActive) return;
    investigationActive = true;

    deactivateInvestigateGlow();
    canInvestigate = false;

    messageInput.disabled = true;
    sendBtn.disabled = true;
    document.getElementById('investigate-btn').disabled = true;

    // Name the chat
    const session = chatSessions.find(s => s.id === activeSessionId);
    if (session && session.name === 'New Chat') {
        session.name = 'H-1B Investigation';
        renderChatList();
    }

    // Clear previous chat content (uploaded docs, messages) for a clean view
    const wrapper = getScrollWrapper();
    wrapper.innerHTML = '';

    selectedFiles = [];
    renderFilesList();
    hideProcessing();

    addMessage('Run H-1B RFE Strategy Analysis', 'user');

    const invContainer = document.createElement('div');
    invContainer.className = 'inv-container';
    invContainer.id = 'inv-container';
    wrapper.appendChild(invContainer);

    // Fire fetch in background
    const fetchPromise = fetch('/api/investigate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: activeSessionId })
    }).then(r => r.json());

    // Run animation sequence
    await runInvestigationAnimation(invContainer, fetchPromise);

    // Await results
    try {
        const response = await fetchPromise;
        if (response.success) {
            investigationData = response.data;
            renderStrategyCards(invContainer, investigationData);
        } else {
            renderInvestigationError(invContainer, response.error || 'Investigation failed');
        }
    } catch (err) {
        renderInvestigationError(invContainer, 'Connection error: ' + err.message);
    }

    messageInput.disabled = false;
    sendBtn.disabled = false;
    document.getElementById('investigate-btn').disabled = false;
    investigationActive = false;
    messageInput.focus();
}

function runInvestigationAnimation(container, investigatePromise) {
    return new Promise(async (resolve) => {

        // ── Thinking phase: fetch graph data while showing init messages ──
        const thinkingDiv = document.createElement('div');
        thinkingDiv.className = 'inv-thinking';
        thinkingDiv.innerHTML = `
            <div class="inv-thinking-icon"><div class="spinner"></div></div>
            <div class="inv-thinking-text">Initializing analysis engine<span id="thinking-dots"></span></div>
        `;
        container.appendChild(thinkingDiv);
        scrollToBottom();

        // Animate thinking dots
        const dotsEl = document.getElementById('thinking-dots');
        let dotCount = 0;
        const dotsInterval = setInterval(() => {
            dotCount = (dotCount + 1) % 4;
            if (dotsEl) dotsEl.textContent = '.'.repeat(dotCount);
        }, 500);

        const thinkingText = thinkingDiv.querySelector('.inv-thinking-text');
        const graphFetchPromise = fetchGraphData();

        await jitteredDelay(500, 150);
        thinkingText.textContent = 'Loading H-1B AAO appeal database...';

        // Wait for graph data (or timeout)
        let graphResult = null;
        const fetchStart = Date.now();
        try {
            graphResult = await Promise.race([
                graphFetchPromise,
                new Promise(r => setTimeout(() => r(null), 4000))
            ]);
        } catch (e) { /* fallback */ }

        // Enforce minimum thinking time
        const elapsed = Date.now() - fetchStart;
        if (elapsed < 1500) await new Promise(r => setTimeout(r, 1500 - elapsed));

        let graphData = graphResult?.graphData || null;
        const profile = graphResult?.profile || null;

        if (graphData) {
            graphData = normalizeGraphCoords(graphData);
            thinkingText.textContent = `Connected — ${graphData.nodes.length} cases loaded, ${graphData.edges.length} similarity edges`;
            await jitteredDelay(600, 150);
        }

        clearInterval(dotsInterval);
        thinkingDiv.remove();

        // ── Steps container ──
        const stepsDiv = document.createElement('div');
        stepsDiv.className = 'inv-steps';
        stepsDiv.id = 'inv-steps';
        container.appendChild(stepsDiv);
        scrollToBottom();

        // Pre-compute data for steps
        const similarSet = graphData ? new Set(graphData.similar_ids) : new Set();
        const similarNodes = graphData ? graphData.nodes.filter(n => similarSet.has(n.id)) : [];
        const totalCases = graphData ? graphData.nodes.length : 61;
        const similarCount = graphData ? graphData.similar_ids.length : 0;

        // Compute argument frequencies from similar cases
        const argFreq = {};
        for (const n of similarNodes) {
            for (const arg of (n.arguments_made || [])) {
                argFreq[arg] = (argFreq[arg] || 0) + 1;
            }
        }
        const sortedArgs = Object.entries(argFreq).sort((a, b) => b[1] - a[1]);

        // ──────────────────────────────────────────────────
        // STEP 1: Parse candidate profile
        // ──────────────────────────────────────────────────
        const step1 = createStepElement(1, 'Parsing candidate profile...', profile
            ? `${profile.job_title || 'Unknown'} — ${profile.company_type || 'unknown'} company`
            : 'Extracting candidate information and current arguments');
        stepsDiv.appendChild(step1);
        scrollToBottom();
        step1.classList.add('active');

        if (profile) {
            const fields = [
                ['job_title', profile.job_title],
                ['company_type', profile.company_type],
                ['wage_level', profile.wage_level],
                ['rfe_issues', Array.isArray(profile.rfe_issues) ? profile.rfe_issues.join(', ') : profile.rfe_issues],
                ['current_arguments', Array.isArray(profile.current_arguments) ? profile.current_arguments.join(', ') : profile.current_arguments],
            ].filter(([k, v]) => v);

            for (const [key, val] of fields) {
                await jitteredDelay(280, 120);
                appendSubLine(step1, `${key}: ${val}`);
            }
            await jitteredDelay(350, 100);
        } else {
            await jitteredDelay(1800, 200);
        }

        step1.classList.remove('active');
        step1.classList.add('complete');

        // ──────────────────────────────────────────────────
        // STEP 2: Analyze RFE issues
        // ──────────────────────────────────────────────────
        await jitteredDelay(350, 120);

        const rfeIssues = profile?.rfe_issues || [];
        const step2 = createStepElement(2, 'Analyzing RFE issues...', rfeIssues.length
            ? `${rfeIssues.length} issue(s) identified in RFE document`
            : 'Identifying RFE issues and USCIS requirements');
        stepsDiv.appendChild(step2);
        scrollToBottom();
        step2.classList.add('active');

        if (rfeIssues.length) {
            for (const issue of rfeIssues) {
                await jitteredDelay(400, 150);
                const label = RFE_ISSUE_LABELS[issue] || formatArgName(issue);
                appendSubLine(step2, `Issue identified: ${label}`, 'found');
            }
            await jitteredDelay(350, 100);
            appendSubLine(step2, 'Cross-referencing AAO precedent decisions...');
            await jitteredDelay(500, 150);
            appendSubLine(step2, 'Matching against 8 CFR 214.2(h)(4)(ii) criteria');
            await jitteredDelay(400, 100);
        } else {
            await jitteredDelay(1500, 200);
        }

        step2.classList.remove('active');
        step2.classList.add('complete');

        // ──────────────────────────────────────────────────
        // STEP 3: Graph traversal + visualization
        // ──────────────────────────────────────────────────
        await jitteredDelay(350, 120);

        const step3 = createStepElement(3, 'Querying case graph...', graphData
            ? `Traversing ${totalCases} cases, ${graphData.edges.length} similarity edges`
            : 'Analyzing H-1B AAO appeal cases');
        stepsDiv.appendChild(step3);
        scrollToBottom();
        step3.classList.add('active');

        // Render graph SVG
        const graphDiv = document.createElement('div');
        graphDiv.className = 'inv-graph inv-graph-inline';
        graphDiv.style.position = 'relative';

        const svgHtml = graphData ? generateRealGraphSVG(graphData) : generateGraphSVG();

        graphDiv.innerHTML = `
            <div class="inv-graph-label">Case Graph Analysis</div>
            <div class="inv-graph-counter" id="inv-node-counter">0 cases</div>
            ${svgHtml}
        `;

        if (graphData) {
            const legend = document.createElement('div');
            legend.className = 'inv-graph-legend';
            legend.innerHTML = `
                <div class="legend-item"><span class="legend-dot dismissed"></span>Dismissed</div>
                <div class="legend-item"><span class="legend-dot sustained"></span>Sustained</div>
                <div class="legend-item"><span class="legend-dot remanded"></span>Remanded</div>
                <div class="legend-item"><span class="legend-dot user-dot"></span>Your case</div>
            `;
            graphDiv.appendChild(legend);
            setupGraphTooltips(graphDiv);
        }

        stepsDiv.appendChild(graphDiv);
        scrollToBottom();

        // Animate counter + stream case matches
        let nodeCount = 0;
        const counter = document.getElementById('inv-node-counter');
        const counterInterval = setInterval(() => {
            nodeCount = Math.min(totalCases, nodeCount + Math.ceil(Math.random() * 3) + 1);
            if (counter) counter.textContent = nodeCount + ' cases analyzed';
            if (nodeCount >= totalCases) {
                clearInterval(counterInterval);
                if (similarCount && counter) {
                    counter.textContent = `${totalCases} cases · ${similarCount} similar`;
                }
            }
        }, 350);

        // Stream similar case matches as sub-lines
        const casesToShow = similarNodes.slice(0, 6);
        for (const c of casesToShow) {
            await jitteredDelay(450, 150);
            const outcome = (c.outcome || 'UNKNOWN').toUpperCase();
            const cls = outcome.includes('SUSTAIN') ? 'success' : outcome.includes('REMAND') ? 'warn' : '';
            appendSubLine(step3, `Match: ${c.job_title || 'Case ' + c.id} — ${outcome}`, cls);
        }

        await jitteredDelay(600, 200);
        if (similarCount) {
            appendSubLine(step3, `${similarCount} similar cases identified in neighborhood`, 'found');
        }

        await jitteredDelay(800, 200);
        clearInterval(counterInterval);
        if (counter) counter.textContent = `${totalCases} cases · ${similarCount} similar`;

        step3.classList.remove('active');
        step3.classList.add('complete');

        // ──────────────────────────────────────────────────
        // STEP 4: Mine patterns + estimate probability
        // ──────────────────────────────────────────────────
        await jitteredDelay(350, 120);

        const step4 = createStepElement(4, 'Mining patterns and estimating probability...', sortedArgs.length
            ? `Analyzing ${sortedArgs.length} argument types across ${similarCount} similar cases`
            : 'Running counterfactual analysis on similar cases');
        stepsDiv.appendChild(step4);
        scrollToBottom();
        step4.classList.add('active');

        // Stream argument frequencies
        if (sortedArgs.length) {
            appendSubLine(step4, `Counting argument frequencies across ${similarCount} similar cases...`, 'dim');
            await jitteredDelay(400, 100);

            for (const [arg, count] of sortedArgs.slice(0, 5)) {
                await jitteredDelay(300, 120);
                appendSubLine(step4, `${formatArgName(arg)}: ${count}/${similarCount} cases`);
            }
            await jitteredDelay(400, 100);
        }

        // Try to get real investigate results if available
        let investigateData = null;
        if (investigatePromise) {
            try {
                investigateData = await Promise.race([
                    investigatePromise.then(r => r.success ? r : null),
                    new Promise(r => setTimeout(() => r(null), 100))
                ]);
            } catch (e) { /* not ready yet */ }
        }

        if (investigateData?.data) {
            const d = investigateData.data;

            // Show winning pattern if available
            if (d.winning_patterns?.length) {
                const wp = d.winning_patterns[0];
                const combo = (wp.arguments || []).map(formatArgName).join(' + ');
                appendSubLine(step4, `Top pattern: ${combo} → ${Math.round(wp.success_rate * 100)}% success rate`, 'success');
                await jitteredDelay(500, 150);
            }

            // Show probability breakdown
            appendSubLine(step4, 'Running counterfactual analysis...', 'dim');
            await jitteredDelay(500, 150);

            const prob = d.success_probability;
            if (prob) {
                appendSubLine(step4, `Base rate from similar cases: ${(prob.base_probability * 100).toFixed(1)}%`);
                await jitteredDelay(300, 100);
                appendSubLine(step4, `Argument boost: +${(prob.argument_boost * 100).toFixed(1)}%`);
                await jitteredDelay(300, 100);
                appendSubLine(step4, `Adjusted probability: ${(prob.probability * 100).toFixed(1)}%`, prob.probability > 0.3 ? 'success' : 'warn');
                await jitteredDelay(300, 100);
                appendSubLine(step4, `Confidence: ${prob.confidence} (n=${prob.sample_size})`);
                await jitteredDelay(400, 100);
            }
        } else {
            // Fallback: show graph-derived stats
            const sustained = similarNodes.filter(n => (n.outcome || '').toLowerCase().includes('sustain')).length;
            const dismissed = similarNodes.filter(n => (n.outcome || '').toLowerCase().includes('dismiss')).length;

            appendSubLine(step4, 'Running counterfactual analysis...', 'dim');
            await jitteredDelay(600, 150);

            if (similarCount) {
                appendSubLine(step4, `Similar outcomes: ${sustained} sustained, ${dismissed} dismissed of ${similarCount}`);
                await jitteredDelay(400, 100);
            }

            appendSubLine(step4, 'Computing weighted probability...');
            await jitteredDelay(800, 200);
            appendSubLine(step4, 'Building strategy recommendations...');
            await jitteredDelay(600, 150);
        }

        step4.classList.remove('active');
        step4.classList.add('complete');

        // Final pause before results
        await jitteredDelay(800, 200);
        resolve();
    });
}

function createStepElement(number, label, detail) {
    const el = document.createElement('div');
    el.className = 'inv-step';
    el.innerHTML = `
        <div class="inv-step-indicator">
            <div class="inv-step-spinner"></div>
            <div class="inv-step-check">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
            </div>
            <div class="inv-step-number">${number}</div>
        </div>
        <div class="inv-step-content">
            <div class="inv-step-label">${escapeHtml(label)}</div>
            <div class="inv-step-detail">${escapeHtml(detail)}</div>
        </div>
    `;
    return el;
}

// ── Helpers for realistic animation ──

const ANIMATION_PACE = 1.7; // Scale factor — tunes total investigation to ~30s

function jitteredDelay(baseMs, jitterMs = 100) {
    const scaled = baseMs * ANIMATION_PACE;
    return new Promise(r => setTimeout(r, Math.max(80, scaled + (Math.random() * jitterMs * 2 - jitterMs))));
}

function appendSubLine(stepEl, text, className) {
    const content = stepEl.querySelector('.inv-step-content');
    const line = document.createElement('div');
    line.className = 'inv-sub-line' + (className ? ' ' + className : '');
    line.textContent = text;
    content.appendChild(line);
    scrollToBottom();
}

const RFE_ISSUE_LABELS = {
    'specialty_occupation': 'Specialty Occupation (degree requirement)',
    'employer_employee': 'Employer-Employee Relationship',
    'wage_level': 'Wage Level Adequacy',
    'beneficiary_qualification': 'Beneficiary Qualifications',
    'itinerary': 'Work Itinerary Requirement',
};

function generateGraphSVG() {
    const cx = 50, cy = 50;
    const nodes = [];
    const edges = [];

    // Central user node
    nodes.push(`<circle class="inv-graph-node user" cx="${cx}%" cy="${cy}%" r="6" style="animation-delay:0s"/>`);

    // Satellite case nodes
    const positions = [];
    for (let i = 0; i < 12; i++) {
        const angle = (i / 12) * Math.PI * 2 + (Math.random() * 0.4 - 0.2);
        const radius = 25 + Math.random() * 18;
        const x = cx + Math.cos(angle) * radius;
        const y = cy + Math.sin(angle) * radius;
        const cls = Math.random() > 0.85 ? 'sustained' : 'dismissed';
        const delay = (0.3 + i * 0.15).toFixed(2);
        positions.push({ x, y });

        nodes.push(`<circle class="inv-graph-node ${cls}" cx="${x}%" cy="${y}%" r="4" style="animation-delay:${delay}s"/>`);

        const edgeDelay = (0.5 + i * 0.12).toFixed(2);
        const edgeCls = i < 3 ? 'inv-graph-edge highlight' : 'inv-graph-edge';
        edges.push(`<line class="${edgeCls}" x1="${cx}%" y1="${cy}%" x2="${x}%" y2="${y}%" style="animation-delay:${edgeDelay}s"/>`);
    }

    // Cross-edges
    for (let i = 0; i < 4; i++) {
        const a = Math.floor(Math.random() * positions.length);
        const b = (a + 1 + Math.floor(Math.random() * 3)) % positions.length;
        const d = (1.5 + i * 0.2).toFixed(2);
        edges.push(`<line class="inv-graph-edge" x1="${positions[a].x}%" y1="${positions[a].y}%" x2="${positions[b].x}%" y2="${positions[b].y}%" style="animation-delay:${d}s" stroke-opacity="0.3"/>`);
    }

    return `<svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">${edges.join('')}${nodes.join('')}</svg>`;
}

async function fetchGraphData() {
    try {
        const resp = await fetch('/api/graph-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: activeSessionId })
        });
        const json = await resp.json();
        if (json.success) return { graphData: json.data, profile: json.profile || null };
        console.warn('Graph data fetch failed:', json.error);
        return null;
    } catch (err) {
        console.warn('Graph data fetch error:', err);
        return null;
    }
}

function normalizeGraphCoords(graphData) {
    const pad = 8;
    const lo = pad, hi = 100 - pad;
    const nodes = graphData.nodes;
    if (!nodes.length) return graphData;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const n of nodes) {
        if (n.x < minX) minX = n.x;
        if (n.x > maxX) maxX = n.x;
        if (n.y < minY) minY = n.y;
        if (n.y > maxY) maxY = n.y;
    }
    const ux = graphData.user_node.x, uy = graphData.user_node.y;
    if (ux < minX) minX = ux; if (ux > maxX) maxX = ux;
    if (uy < minY) minY = uy; if (uy > maxY) maxY = uy;

    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const norm = (val, min, range) => lo + ((val - min) / range) * (hi - lo);

    for (const n of nodes) {
        n.nx = norm(n.x, minX, rangeX);
        n.ny = norm(n.y, minY, rangeY);
    }
    graphData.user_node.nx = norm(ux, minX, rangeX);
    graphData.user_node.ny = norm(uy, minY, rangeY);

    return graphData;
}

function generateRealGraphSVG(graphData) {
    const similarSet = new Set(graphData.similar_ids);
    const nodeMap = {};
    for (const n of graphData.nodes) nodeMap[n.id] = n;

    const userX = graphData.user_node.nx;
    const userY = graphData.user_node.ny;

    const edgesSvg = [];
    const bgNodes = [];
    const simNodes = [];

    const userNode = `<circle class="inv-graph-node user" cx="${userX}%" cy="${userY}%" r="6" style="animation-delay:0s" data-tooltip="Your Case"/>`;

    const similarArr = graphData.nodes.filter(n => similarSet.has(n.id));
    const backgroundArr = graphData.nodes.filter(n => !similarSet.has(n.id));

    similarArr.forEach((n, i) => {
        const outcome = (n.outcome || '').toLowerCase();
        let cls = 'dismissed';
        if (outcome.includes('sustain')) cls = 'sustained';
        else if (outcome.includes('remand')) cls = 'remanded';

        const delay = (0.2 + i * (1.6 / Math.max(similarArr.length, 1))).toFixed(2);
        simNodes.push(`<circle class="inv-graph-node similar ${cls}" cx="${n.nx}%" cy="${n.ny}%" r="4" style="animation-delay:${delay}s" data-tooltip="${escapeHtml(n.job_title || 'Case')} — ${cls}" data-case-id="${n.id}"/>`);

        const edgeDelay = (0.4 + i * (1.6 / Math.max(similarArr.length, 1))).toFixed(2);
        const edgeCls = i < 5 ? 'inv-graph-edge highlight' : 'inv-graph-edge';
        edgesSvg.push(`<line class="${edgeCls}" x1="${userX}%" y1="${userY}%" x2="${n.nx}%" y2="${n.ny}%" style="animation-delay:${edgeDelay}s"/>`);
    });

    backgroundArr.forEach((n) => {
        const outcome = (n.outcome || '').toLowerCase();
        let cls = 'dismissed';
        if (outcome.includes('sustain')) cls = 'sustained';
        else if (outcome.includes('remand')) cls = 'remanded';

        bgNodes.push(`<circle class="inv-graph-node background ${cls}" cx="${n.nx}%" cy="${n.ny}%" r="3" style="animation-delay:2.0s" data-tooltip="${escapeHtml(n.job_title || 'Case')} — ${cls}" data-case-id="${n.id}"/>`);
    });

    const crossEdges = [];
    for (const e of graphData.edges) {
        if (similarSet.has(e.source) && similarSet.has(e.target) && nodeMap[e.source] && nodeMap[e.target]) {
            const s = nodeMap[e.source], t = nodeMap[e.target];
            if (s.nx !== undefined && t.nx !== undefined) {
                const d = (1.8 + crossEdges.length * 0.05).toFixed(2);
                crossEdges.push(`<line class="inv-graph-edge" x1="${s.nx}%" y1="${s.ny}%" x2="${t.nx}%" y2="${t.ny}%" style="animation-delay:${d}s" stroke-opacity="0.25"/>`);
            }
            if (crossEdges.length >= 15) break;
        }
    }

    return `<svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">${edgesSvg.join('')}${crossEdges.join('')}${bgNodes.join('')}${simNodes.join('')}${userNode}</svg>`;
}

function setupGraphTooltips(graphDiv) {
    let tooltip = null;

    graphDiv.addEventListener('mouseover', (e) => {
        const target = e.target;
        if (!target.hasAttribute || !target.hasAttribute('data-tooltip')) return;
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.className = 'inv-graph-tooltip';
            graphDiv.appendChild(tooltip);
        }
        tooltip.textContent = target.getAttribute('data-tooltip');
        tooltip.style.display = 'block';
    });

    graphDiv.addEventListener('mousemove', (e) => {
        if (!tooltip || tooltip.style.display === 'none') return;
        const rect = graphDiv.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        tooltip.style.left = (x + 12) + 'px';
        tooltip.style.top = (y - 30) + 'px';
    });

    graphDiv.addEventListener('mouseout', (e) => {
        const target = e.target;
        if (target.hasAttribute && target.hasAttribute('data-tooltip') && tooltip) {
            tooltip.style.display = 'none';
        }
    });
}

function appendLogLine(container, text, extraClass) {
    const line = document.createElement('div');
    line.className = 'inv-log-line' + (extraClass ? ' ' + extraClass : '');
    const now = new Date();
    const ts = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    line.innerHTML = `<span class="log-ts">[${ts}]</span> ${escapeHtml(text)}`;
    container.appendChild(line);
    container.scrollTop = container.scrollHeight;
}

function renderStrategyCards(container, data) {
    const strategies = buildStrategyOptions(data);

    // Add a summary message first
    const prob = data.success_probability;
    const probPct = Math.round((prob?.probability || 0) * 100);
    const summaryDiv = document.createElement('div');
    summaryDiv.className = 'message assistant';
    summaryDiv.innerHTML = `
        <div class="avatar assistant">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
            </svg>
        </div>
        <div class="message-content">
            <div class="message-bubble">Hey! I've gone through the results of the graph analysis across <strong>61 H-1B AAO cases</strong>. Your current estimated success probability is <strong>${probPct}%</strong>. Here are <strong>${strategies.length} strategy options</strong> I've found &mdash; click one to see the full breakdown.</div>
        </div>
    `;
    container.appendChild(summaryDiv);

    const cardsDiv = document.createElement('div');
    cardsDiv.className = 'inv-strategies';
    cardsDiv.id = 'inv-strategies';

    strategies.forEach((strat, idx) => {
        const card = document.createElement('div');
        card.className = 'inv-strategy-card';
        card.dataset.idx = idx;
        card.innerHTML = `
            <div class="inv-card-number">Strategy ${idx + 1}</div>
            <div class="inv-card-title">${escapeHtml(strat.title)}</div>
            <div class="inv-card-impact">${escapeHtml(strat.impact)}</div>
            <div class="inv-card-meta">Confidence: ${escapeHtml(strat.confidence)} | n=${strat.sampleSize}</div>
        `;
        cardsDiv.appendChild(card);
    });

    container.appendChild(cardsDiv);
    scrollToBottom();
}

function buildStrategyOptions(data) {
    const options = [];

    // 1: Top recommendation
    if (data.recommendations?.length > 0) {
        const rec = data.recommendations[0];
        options.push({
            title: `Add "${formatArgName(rec.add)}" argument`,
            impact: rec.impact,
            confidence: rec.confidence,
            sampleSize: rec.sample_size,
            detail: rec,
            type: 'recommendation'
        });
    }

    // 2: Winning pattern
    if (data.winning_patterns?.length > 0) {
        const wp = data.winning_patterns[0];
        options.push({
            title: `Winning combo: ${wp.arguments.map(formatArgName).join(' + ')}`,
            impact: `${Math.round(wp.success_rate * 100)}% success rate`,
            confidence: wp.sample_size >= 5 ? 'medium' : 'low',
            sampleSize: wp.sample_size,
            detail: wp,
            type: 'winning_pattern'
        });
    }

    // 3: Best association rule
    if (data.association_rules?.length > 0) {
        const rule = data.association_rules[0];
        const args = rule.antecedent.filter(a => a.startsWith('arg:')).map(a => formatArgName(a.split(':')[1]));
        options.push({
            title: `Rule: ${args.join(' + ') || 'Combined factors'}`,
            impact: `${Math.round(rule.confidence * 100)}% confidence, lift ${rule.lift.toFixed(1)}x`,
            confidence: rule.sample_size >= 5 ? 'medium' : 'low',
            sampleSize: rule.sample_size,
            detail: rule,
            type: 'association_rule'
        });
    }

    // 4: Current risk assessment
    options.push({
        title: 'Keep current strategy (risk assessment)',
        impact: data.current_strategy_risk || 'No risk data',
        confidence: data.success_probability?.confidence || 'unknown',
        sampleSize: data.success_probability?.sample_size || 0,
        detail: { probability: data.success_probability, risk: data.current_strategy_risk },
        type: 'risk_assessment'
    });

    // Pad with extra recommendations if < 4
    let ri = 1;
    while (options.length < 4 && data.recommendations && ri < data.recommendations.length) {
        const rec = data.recommendations[ri++];
        options.push({
            title: `Add "${formatArgName(rec.add)}"`,
            impact: rec.impact,
            confidence: rec.confidence,
            sampleSize: rec.sample_size,
            detail: rec,
            type: 'recommendation'
        });
    }
    // Still need more? Pull from additional association rules
    let ruleIdx = 1;
    while (options.length < 4 && data.association_rules && ruleIdx < data.association_rules.length) {
        const rule = data.association_rules[ruleIdx++];
        const args = rule.antecedent.filter(a => a.startsWith('arg:')).map(a => formatArgName(a.split(':')[1]));
        options.push({
            title: `Rule: ${args.join(' + ') || 'Combined factors'}`,
            impact: `${Math.round(rule.confidence * 100)}% confidence, lift ${rule.lift.toFixed(1)}x`,
            confidence: rule.sample_size >= 5 ? 'medium' : 'low',
            sampleSize: rule.sample_size,
            detail: rule,
            type: 'association_rule'
        });
    }

    return options.slice(0, 4);
}

function formatArgName(name) {
    return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function selectStrategy(idx, strategies, container) {
    const cards = container.querySelectorAll('.inv-strategy-card');
    cards.forEach((c, i) => c.classList.toggle('selected', i === idx));

    const existing = container.querySelector('.inv-detail');
    if (existing) existing.remove();

    const strat = strategies[idx];
    const detailDiv = document.createElement('div');
    detailDiv.className = 'inv-detail';
    detailDiv.innerHTML = buildDetailHTML(strat, idx);
    container.appendChild(detailDiv);
    scrollToBottom();
}

function buildDetailHTML(strat, idx) {
    let summary = '';
    let stats = '';

    if (strat.type === 'recommendation') {
        summary = `Add <strong>${escapeHtml(formatArgName(strat.detail.add))}</strong> to your current argument strategy for the H-1B RFE response.`;
        stats = `
            <div class="inv-detail-section">
                <div class="inv-detail-label">Expected Impact</div>
                <div class="inv-detail-stat"><span class="val">${escapeHtml(strat.detail.impact)}</span></div>
                <div class="inv-detail-stat">Success rate with this argument: <span class="val">${Math.round((strat.detail.with_success_rate || 0) * 100)}%</span></div>
                <div class="inv-detail-stat">Source: <span class="val">${escapeHtml(strat.detail.source || '')} analysis across ${strat.sampleSize} cases</span></div>
            </div>
        `;
    } else if (strat.type === 'winning_pattern') {
        const items = (strat.detail.arguments || []).map(formatArgName).join(', ');
        summary = `Use the winning argument combination: <strong>${escapeHtml(items)}</strong>.`;
        stats = `
            <div class="inv-detail-section">
                <div class="inv-detail-label">Statistics</div>
                <div class="inv-detail-stat">Success rate: <span class="val">${Math.round(strat.detail.success_rate * 100)}%</span></div>
                <div class="inv-detail-stat">Sustained cases: <span class="val">${strat.detail.sustained_count}</span></div>
                <div class="inv-detail-stat">Sample size: <span class="val">${strat.detail.sample_size}</span></div>
            </div>
        `;
    } else if (strat.type === 'association_rule') {
        const factors = (strat.detail.antecedent || []).map(a => {
            const p = a.split(':');
            return p.length > 1 ? formatArgName(p[1]) : a;
        });
        summary = `Apply the rule combination: <strong>${escapeHtml(factors.join(' + '))}</strong>.`;
        stats = `
            <div class="inv-detail-section">
                <div class="inv-detail-label">Rule Metrics</div>
                <div class="inv-detail-stat">Confidence: <span class="val">${Math.round(strat.detail.confidence * 100)}%</span></div>
                <div class="inv-detail-stat">Lift: <span class="val">${strat.detail.lift?.toFixed(1) || 'N/A'}x</span></div>
                <div class="inv-detail-stat">Support: <span class="val">${Math.round((strat.detail.support || 0) * 100)}%</span></div>
            </div>
        `;
    } else if (strat.type === 'risk_assessment') {
        const prob = strat.detail.probability || {};
        summary = `Keep the current argument strategy and assess risk.`;
        stats = `
            <div class="inv-detail-section">
                <div class="inv-detail-label">Current Risk</div>
                <div class="inv-detail-text">${escapeHtml(strat.detail.risk || 'N/A')}</div>
            </div>
            <div class="inv-detail-section">
                <div class="inv-detail-label">Success Probability Breakdown</div>
                <div class="inv-detail-stat">Overall: <span class="val">${Math.round((prob.probability || 0) * 100)}%</span></div>
                <div class="inv-detail-stat">Base: <span class="val">${Math.round((prob.base_probability || 0) * 100)}%</span></div>
                <div class="inv-detail-stat">Argument boost: <span class="val">+${Math.round((prob.argument_boost || 0) * 100)}%</span></div>
                <div class="inv-detail-stat">Sample: <span class="val">${prob.sample_size || 0} cases (${prob.sustained_in_similar || 0} sustained)</span></div>
            </div>
        `;
    }

    const prosConsHTML = buildProsConsDetails(strat);

    return `
        <div class="inv-detail-header">
            <div class="inv-detail-title">Strategy ${idx + 1}: ${escapeHtml(strat.title)}</div>
            <div class="inv-detail-badge">${escapeHtml(strat.confidence)}</div>
        </div>
        <div class="inv-detail-section">
            <div class="inv-detail-label">Summary</div>
            <div class="inv-detail-text">${summary}</div>
        </div>
        ${prosConsHTML}
        ${stats}
        <div class="inv-email-row">
            <input type="email" id="inv-email-input" placeholder="Send report to email..." />
            <button class="inv-email-btn" onclick="sendReport(${idx})">Send Report</button>
        </div>
    `;
}

function buildProsConsDetails(strat) {
    const pros = [];
    const cons = [];
    const detailsNeeded = [];

    if (strat.type === 'recommendation') {
        const argName = formatArgName(strat.detail.add);
        pros.push('Positive impact observed in similar cases');
        pros.push('Based on ' + (strat.detail.source || 'statistical') + ' analysis of ' + strat.sampleSize + ' cases');
        if ((strat.detail.with_success_rate || 0) > 0.3) {
            pros.push('Success rate of ' + Math.round(strat.detail.with_success_rate * 100) + '% with this argument');
        }
        cons.push('Confidence level: ' + strat.confidence);
        if (strat.sampleSize < 5) cons.push('Small sample size -- interpret with caution');
        detailsNeeded.push('Documentation supporting ' + argName);
        detailsNeeded.push('Updated expert opinion letter if applicable');
    } else if (strat.type === 'winning_pattern') {
        const args = (strat.detail.arguments || []).map(formatArgName);
        pros.push('Proven combination with ' + Math.round(strat.detail.success_rate * 100) + '% success rate');
        pros.push(strat.detail.sustained_count + ' sustained cases used this combination');
        cons.push('May require multiple supporting documents');
        if (strat.sampleSize < 5) cons.push('Limited sample size');
        args.forEach(a => detailsNeeded.push('Documentation for: ' + a));
    } else if (strat.type === 'association_rule') {
        pros.push('Rule confidence: ' + Math.round(strat.detail.confidence * 100) + '%');
        pros.push('Lift factor: ' + (strat.detail.lift?.toFixed(1) || 'N/A') + 'x');
        cons.push('Association does not guarantee causation');
        if (strat.sampleSize < 5) cons.push('Small sample size');
        detailsNeeded.push('Supporting evidence for each factor in the rule');
    } else if (strat.type === 'risk_assessment') {
        pros.push('No additional preparation required');
        pros.push('Uses current argument set');
        cons.push('No improvement to success probability');
        const prob = strat.detail.probability || {};
        if ((prob.probability || 0) < 0.3) cons.push('Current success probability is low');
        detailsNeeded.push('Consider strengthening arguments with additional evidence');
    }

    const renderList = (items) => items.map(i => '<li>' + escapeHtml(i) + '</li>').join('');

    return `
        <div class="inv-detail-section inv-pros-cons">
            <div class="inv-detail-columns">
                <div class="inv-detail-col">
                    <div class="inv-detail-label pros-label">Pros</div>
                    <ul class="inv-detail-list pros-list">${renderList(pros)}</ul>
                </div>
                <div class="inv-detail-col">
                    <div class="inv-detail-label cons-label">Cons</div>
                    <ul class="inv-detail-list cons-list">${renderList(cons)}</ul>
                </div>
            </div>
        </div>
        <div class="inv-detail-section">
            <div class="inv-detail-label">Details Needed from Candidate</div>
            <ul class="inv-detail-list details-list">${renderList(detailsNeeded)}</ul>
        </div>
    `;
}

async function sendReport(strategyIndex) {
    const emailInput = document.getElementById('inv-email-input');
    const email = emailInput ? emailInput.value.trim() : '';

    if (!email || !email.includes('@')) {
        if (emailInput) {
            emailInput.style.borderColor = 'var(--error)';
            setTimeout(() => { emailInput.style.borderColor = ''; }, 2000);
        }
        return;
    }

    const btn = document.querySelector('.inv-email-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Sending...'; }

    const summary = investigationData?.explanation || 'No summary available.';

    try {
        const resp = await fetch('/api/send-report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: email,
                strategy_index: strategyIndex,
                report_summary: summary,
            })
        });
        const data = await resp.json();

        if (data.mailto_url) {
            window.open(data.mailto_url, '_blank');
        }

        if (btn) {
            btn.textContent = 'Sent!';
            btn.style.background = 'var(--success)';
            setTimeout(() => { btn.disabled = false; btn.textContent = 'Send Report'; btn.style.background = ''; }, 3000);
        }
    } catch (err) {
        if (btn) {
            btn.textContent = 'Failed';
            btn.style.background = 'var(--error)';
            setTimeout(() => { btn.disabled = false; btn.textContent = 'Send Report'; btn.style.background = ''; }, 3000);
        }
    }
}

function renderInvestigationError(container, errorMsg) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message assistant';
    errorDiv.innerHTML = `
        <div class="avatar assistant">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/>
                <path d="M8 14s1.5 2 4 2 4-2 4-2"/>
                <line x1="9" y1="9" x2="9.01" y2="9"/>
                <line x1="15" y1="9" x2="15.01" y2="9"/>
            </svg>
        </div>
        <div class="message-content">
            <div class="message-bubble">Investigation could not be completed: ${escapeHtml(errorMsg)}</div>
        </div>
    `;
    container.appendChild(errorDiv);
    scrollToBottom();
}

// ── Handle Resize ──
window.addEventListener('resize', () => {
    const sidebar = document.getElementById('sidebar');
    const menuBtn = document.getElementById('menu-toggle');
    if (window.innerWidth > 768) {
        sidebar.classList.remove('mobile-open');
        document.getElementById('sidebar-overlay').classList.remove('active');
        if (sidebarOpen) {
            sidebar.classList.remove('collapsed');
            menuBtn.classList.remove('visible');
        }
    }
});

// ── Event Delegation (survives session restore) ──
document.addEventListener('click', (e) => {
    const card = e.target.closest('.inv-strategy-card');
    if (card && investigationData) {
        const container = card.closest('.inv-container');
        if (!container) return;
        const cards = Array.from(container.querySelectorAll('.inv-strategy-card'));
        const idx = cards.indexOf(card);
        if (idx >= 0) {
            const strategies = buildStrategyOptions(investigationData);
            selectStrategy(idx, strategies, container);
        }
    }
});

// ── Init ──
initChats();
