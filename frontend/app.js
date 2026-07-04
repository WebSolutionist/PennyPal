// API Configuration
const API_BASE_URL = 'http://127.0.0.1:5000/api';

// State management (with local memory for message logs per session)
let sessions = [
    { 
        id: 'session-1', 
        name: 'Session 1', 
        messages: [],
        welcomeFetched: false,
        aiRenamed: false,
        userCustomRenamed: false
    }
];
let currentSessionId = 'session-1';
let memoryEnabled = true;

// DOM Elements
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const newSessionBtn = document.getElementById('new-session-btn');
const sessionList = document.getElementById('session-list');
const currentSessionTitle = document.getElementById('current-session-title');
const memoryToggle = document.getElementById('memory-toggle');
const memoryList = document.getElementById('memory-list');
const memoryCount = document.getElementById('memory-count');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkBackendHealth();
    renderSessions();
    setupEventListeners();
    fetchWelcomeAndMemories();
    
    // Initialize Lucide Icons
    if (window.lucide) {
        window.lucide.createIcons();
    }
});

// Setup event listeners
function setupEventListeners() {
    chatForm.addEventListener('submit', handleSendMessage);
    newSessionBtn.onclick = createNewSession;
    
    // Sidebar toggle logic
    sidebarToggle.onclick = () => {
        sidebar.classList.toggle('collapsed');
    };

    memoryToggle.onchange = (e) => {
        memoryEnabled = e.target.checked;
        console.log(`Memory engine toggled: ${memoryEnabled}`);
        fetchMemories();
    };
}

// Check Backend Connection
async function checkBackendHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        if (data.status === 'online') {
            statusDot.className = 'status-dot online';
            statusText.textContent = data.qwen_configured ? 'Connected to Qwen' : 'Local Demo Mode';
        } else {
            setOfflineStatus();
        }
    } catch (error) {
        console.error('Failed to connect to backend:', error);
        setOfflineStatus();
    }
}

function setOfflineStatus() {
    statusDot.className = 'status-dot offline';
    statusText.textContent = 'Offline (Run backend)';
}

// Fetch memories from backend and render them
async function fetchMemories() {
    if (!memoryEnabled) {
        memoryList.innerHTML = '<div class="empty-memory">Memory engine is disabled.</div>';
        memoryCount.textContent = '0 memories';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/memories?session_id=${currentSessionId}`);
        const memories = await response.json();
        renderMemories(memories);
    } catch (error) {
        console.error('Error fetching memories:', error);
    }
}

// Render memories in the sidebar
function renderMemories(memories) {
    memoryCount.textContent = `${memories.length} ${memories.length === 1 ? 'memory' : 'memories'}`;
    
    if (memories.length === 0) {
        memoryList.innerHTML = '<div class="empty-memory">No memories saved yet. Start talking to PennyPal!</div>';
        return;
    }
    
    memoryList.innerHTML = '';
    memories.sort((a, b) => b.importance - a.importance);
    
    memories.forEach(mem => {
        const div = document.createElement('div');
        div.className = 'memory-item';
        
        let catColor = '#3b82f6';
        if (mem.category === 'Goals') catColor = '#10b981';
        if (mem.category === 'Feelings & Attitudes') catColor = '#f59e0b';
        if (mem.category === 'Action Plan Commitments') catColor = '#8b5cf6';
        if (mem.category === 'Constraints & Facts') catColor = '#ec4899';
        
        div.innerHTML = `
            <div style="font-weight: 600; font-size: 11px; color: ${catColor}; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px;">
                ${mem.category}
            </div>
            <div>${mem.content}</div>
            <div class="memory-item-meta">
                <span>Importance: ${'★'.repeat(mem.importance)}${'☆'.repeat(5 - mem.importance)}</span>
                <span>Mentions: ${mem.mention_count || 1}</span>
            </div>
        `;
        memoryList.appendChild(div);
    });
}

// Render Session list (Updated with edit button support)
function renderSessions() {
    sessionList.innerHTML = '';
    sessions.forEach(session => {
        const div = document.createElement('div');
        div.className = `session-item ${session.id === currentSessionId ? 'active' : ''}`;
        
        div.innerHTML = `
            <span class="session-name-text" id="session-text-${session.id}">${session.name}</span>
            <button class="edit-session-btn" id="edit-btn-${session.id}" title="Rename Session">
                <i data-lucide="edit-3" style="width: 12px; height: 12px; opacity: 0.7;"></i>
            </button>
        `;
        
        // Handle selecting session
        div.onclick = (e) => {
            // Prevent click propagation if clicking the edit button
            if (e.target.closest('.edit-session-btn') || e.target.closest('input')) {
                return;
            }
            selectSession(session.id);
        };
        
        sessionList.appendChild(div);
        
        // Bind the edit rename listener
        const editBtn = div.querySelector(`#edit-btn-${session.id}`);
        editBtn.onclick = () => enableSessionRename(session.id);
    });
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

// Enable renaming input field inline
function enableSessionRename(sessionId) {
    const textSpan = document.getElementById(`session-text-${sessionId}`);
    const activeSession = sessions.find(s => s.id === sessionId);
    
    if (!textSpan) return;
    
    const input = document.createElement('input');
    input.type = 'text';
    input.value = activeSession.name;
    input.className = 'session-rename-input';
    input.style.background = 'rgba(15, 23, 42, 0.8)';
    input.style.border = '1px solid var(--accent-color)';
    input.style.color = '#fff';
    input.style.borderRadius = '6px';
    input.style.padding = '2px 6px';
    input.style.width = '160px';
    
    // Save rename function
    const saveRename = () => {
        const newName = input.value.trim();
        if (newName) {
            activeSession.name = newName;
            activeSession.userCustomRenamed = true;
            if (sessionId === currentSessionId) {
                currentSessionTitle.textContent = newName;
            }
            renderSessions();
        }
    };
    
    input.onblur = saveRename;
    input.onkeydown = (e) => {
        if (e.key === 'Enter') {
            saveRename();
        }
    };
    
    textSpan.innerHTML = '';
    textSpan.appendChild(input);
    input.focus();
}

// Create new session
function createNewSession() {
    const lastSessionId = currentSessionId;
    const newId = `session-${sessions.length + 1}`;
    const newName = `Session ${sessions.length + 1}`;
    sessions.push({ 
        id: newId, 
        name: newName,
        messages: [],
        welcomeFetched: false,
        aiRenamed: false,
        userCustomRenamed: false
    });
    renderSessions();
    
    // Trigger memory decay on transition to the new session
    triggerDecay(newId, lastSessionId);
}

// Trigger memory decay on backend
async function triggerDecay(newSessionId, lastActiveSession) {
    if (!memoryEnabled) {
        selectSession(newSessionId);
        return;
    }
    
    try {
        await fetch(`${API_BASE_URL}/decay`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: newSessionId,
                last_active_session: lastActiveSession
            })
        });
    } catch (error) {
        console.error('Error triggering memory decay:', error);
    }
    
    selectSession(newSessionId);
}

// Select session
function selectSession(sessionId) {
    currentSessionId = sessionId;
    currentSessionTitle.textContent = sessions.find(s => s.id === sessionId).name;
    renderSessions();
    fetchWelcomeAndMemories();
}

// Fetch welcome message and memories together, or load existing history
async function fetchWelcomeAndMemories() {
    const activeSession = sessions.find(s => s.id === currentSessionId);
    
    // If we already have message history for this session, restore it
    if (activeSession.messages.length > 0) {
        chatMessages.innerHTML = '';
        activeSession.messages.forEach(msg => {
            appendMessageToScreen(msg.sender, msg.avatar, msg.text);
        });
        fetchMemories();
        return;
    }

    chatMessages.innerHTML = '';
    const welcomeId = appendTypingIndicator();
    
    try {
        const welcomeResponse = await fetch(`${API_BASE_URL}/welcome`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                session_id: currentSessionId,
                memory_enabled: memoryEnabled
            })
        });
        const welcomeData = await welcomeResponse.json();
        
        removeTypingIndicator(welcomeId);
        
        const welcomeText = welcomeData.reply;
        activeSession.messages.push({
            sender: 'system',
            avatar: 'logo',
            text: welcomeText
        });
        activeSession.welcomeFetched = true;
        
        appendMessageToScreen('system', 'logo', welcomeText);
        fetchMemories();
    } catch (error) {
        console.error('Error in session welcome initialization:', error);
        removeTypingIndicator(welcomeId);
        
        const fallbackText = "Hello! I'm **PennyPal**, your personal AI financial coach. Let's talk about your money goals, budgets, or any financial questions you have today!";
        activeSession.messages.push({
            sender: 'system',
            avatar: 'logo',
            text: fallbackText
        });
        
        appendMessageToScreen('system', 'logo', fallbackText);
        fetchMemories();
    }
}

// Check if we should rename the session using AI
async function checkAndTriggerAIRename() {
    const activeSession = sessions.find(s => s.id === currentSessionId);
    
    // Rename if session has messages, hasn't been custom renamed by user, and hasn't been renamed by AI yet
    if (activeSession.messages.length >= 3 && !activeSession.aiRenamed && !activeSession.userCustomRenamed) {
        try {
            const response = await fetch(`${API_BASE_URL}/rename-session`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    messages: activeSession.messages
                })
            });
            const data = await response.json();
            if (data.suggested_name) {
                activeSession.name = data.suggested_name;
                activeSession.aiRenamed = true;
                currentSessionTitle.textContent = data.suggested_name;
                renderSessions();
            }
        } catch (error) {
            console.error('Failed to rename session via AI:', error);
        }
    }
}

// Handle sending message
async function handleSendMessage(e) {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;

    const activeSession = sessions.find(s => s.id === currentSessionId);

    // Save and append user message
    activeSession.messages.push({
        sender: 'user',
        avatar: 'user',
        text: text
    });
    appendMessageToScreen('user', 'user', text);
    chatInput.value = '';
    
    // Show typing state
    const typingId = appendTypingIndicator();
    
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: text,
                session_id: currentSessionId,
                memory_enabled: memoryEnabled
            })
        });
        
        const data = await response.json();
        removeTypingIndicator(typingId);
        
        if (data.reply) {
            // Save and append system response
            activeSession.messages.push({
                sender: 'system',
                avatar: 'logo',
                text: data.reply
            });
            appendMessageToScreen('system', 'logo', data.reply);
            fetchMemories();
            
            // Trigger AI renaming check
            checkAndTriggerAIRename();
        } else if (data.error) {
            appendMessageToScreen('system', 'error', `Error: ${data.error}`);
        }
    } catch (error) {
        console.error('Error sending message:', error);
        removeTypingIndicator(typingId);
        appendMessageToScreen('system', 'error', 'Unable to connect to PennyPal backend. Please ensure the server is running.');
    }
}

// Low-level helper to append HTML representation to the screen
function appendMessageToScreen(sender, avatar, text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;
    
    const formattedText = text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    let avatarHtml = '';
    if (avatar === 'logo') {
        avatarHtml = `<img src="assets/logo.png" alt="PennyPal Avatar" class="avatar-img">`;
    } else if (avatar === 'user') {
        avatarHtml = `<i data-lucide="user"></i>`;
    } else {
        avatarHtml = `<i data-lucide="alert-circle"></i>`;
    }

    messageDiv.innerHTML = `
        <div class="message-avatar">${avatarHtml}</div>
        <div class="message-content">
            <p>${formattedText}</p>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    if (window.lucide) {
        window.lucide.createIcons();
    }
}

// Typing Indicator helpers
function appendTypingIndicator() {
    const id = 'typing-' + Date.now();
    const div = document.createElement('div');
    div.className = 'message system typing';
    div.id = id;
    div.innerHTML = `
        <div class="message-avatar">
            <img src="assets/logo.png" alt="PennyPal Avatar" class="avatar-img">
        </div>
        <div class="message-content">
            <p>Thinking...</p>
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return id;
}

function removeTypingIndicator(id) {
    const element = document.getElementById(id);
    if (element) {
        element.remove();
    }
}
