// ── State ──
const sessionId = 'session_' + Date.now();
let selectedFiles = [];
let sidebarOpen = true;
let currentTab = 'chat';

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

// ── File Handling ──
function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    addFilesToList(files);
    event.target.value = ''; // Reset input
}

function addFilesToList(files) {
    files.forEach(file => {
        if (file.type === 'application/pdf' && !selectedFiles.find(f => f.name === file.name)) {
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
    const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
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

// ── Send Message ──
async function sendMessage() {
    const message = messageInput.value.trim();

    if (!message && selectedFiles.length === 0) return;

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

                const formData = new FormData();
                formData.append('file', file);
                formData.append('session_id', sessionId);

                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });

                updateProgress(100, 'Complete!', 'Processing next file...');

                const data = await response.json();

                hideProcessing();
                removeTypingIndicator();

                if (data.error) {
                    addMessage(`Error: ${data.error}`, 'assistant');
                } else {
                    addMessage(data.response, 'assistant', data.file_url || null);
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
                    session_id: sessionId
                })
            });

            removeTypingIndicator();

            const data = await response.json();

            if (data.error) {
                addMessage(`Error: ${data.error}`, 'assistant');
            } else {
                addMessage(data.response, 'assistant');
            }
        }
    } catch (error) {
        hideProcessing();
        removeTypingIndicator();
        addMessage(`Connection error: ${error.message}`, 'assistant');
    }

    // Re-enable input
    messageInput.disabled = false;
    sendBtn.disabled = false;
    messageInput.focus();
}

// ── Reset Chat ──
async function resetChat() {
    try {
        const formData = new FormData();
        formData.append('session_id', sessionId);

        await fetch('/reset', {
            method: 'POST',
            body: formData
        });
    } catch (e) {
        console.error('Reset failed:', e);
    }

    // Clear UI
    const wrapper = getScrollWrapper();
    wrapper.innerHTML = `
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

    selectedFiles = [];
    renderFilesList();
    messageInput.value = '';
    hideProcessing();
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

// ── Init ──
messageInput.focus();
