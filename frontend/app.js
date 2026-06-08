document.addEventListener('DOMContentLoaded', () => {
    // API Configurations
    const API_BASE_URL = window.location.protocol.startsWith('file') 
        ? 'http://127.0.0.1:8000' 
        : '';

    // State
    let currentMode = 'coach';
    let messageHistory = [];

    // Selectors
    const modeCards = document.querySelectorAll('.mode-card');
    const welcomeText = document.getElementById('welcome-text');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-message-btn');
    const messagesContainer = document.getElementById('chat-messages-container');
    
    // Mobile Sidebar Elements
    const mobileMenuToggle = document.getElementById('mobile-menu-toggle');
    const mobileMenuClose = document.getElementById('mobile-menu-close');
    const appSidebar = document.getElementById('app-sidebar');

    // Welcome configurations
    const modeConfigs = {
        coach: {
            welcome: "Bonjour ! Je suis l'assistant **Football IQ**. Je suis configuré en **Mode Coach**. Posez-moi vos questions pour préparer des séances d'entraînement ou clarifier des consignes tactiques basées sur nos fiches RAG.",
            placeholder: "Écrivez votre consigne tactique ou question RAG ici..."
        },
        analyst: {
            welcome: "Bonjour ! Je suis l'assistant **Football IQ**. Je suis configuré en **Mode Analyste**. Demandez-moi d'analyser une structure collective, un système de jeu ou d'identifier des forces et faiblesses.",
            placeholder: "Demandez une analyse de structure ou système..."
        },
        fan: {
            welcome: "Bonjour ! Je suis l'assistant **Football IQ**. Je suis configuré en **Mode Fan**. Posez-moi une question sur le foot de manière simple, vivante et accessible !",
            placeholder: "Posez votre question de supporter..."
        }
    };

    // --- Helpers ---

    // Secure HTML escaping to prevent raw injection
    function escapeHtml(text) {
        if (!text) return "";
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    // Markdown Parser with strict element tags matching
    function renderMarkdown(text) {
        if (!text) return "";
        
        let html = escapeHtml(text);
        
        // Parse Headers: ### Title -> <h3>Title</h3>
        html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
        
        // Parse Bold: **text** -> <strong>text</strong>
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        // Parse Lists
        html = html.replace(/^\s*[\*\-]\s+(.*?)$/gm, '<li>$1</li>');
        html = html.replace(/^\s*\d+\.\s+(.*?)$/gm, '<li>$1</li>');
        
        // Wrap consecutive <li> elements in <ul>
        const lines = html.split('\n');
        let inList = false;
        let processedLines = [];
        
        for (let line of lines) {
            const trimmed = line.trim();
            const isLi = trimmed.startsWith('<li>') || line.startsWith('<li>');
            
            if (isLi) {
                if (!inList) {
                    inList = true;
                    processedLines.push('<ul>');
                }
                processedLines.push(line);
            } else {
                if (inList) {
                    processedLines.push('</ul>');
                    inList = false;
                }
                if (trimmed === '') {
                    processedLines.push('<br>');
                } else if (!trimmed.startsWith('<h') && !trimmed.startsWith('<ul>') && !trimmed.startsWith('</ul>')) {
                    processedLines.push(`<p>${line}</p>`);
                } else {
                    processedLines.push(line);
                }
            }
        }
        
        if (inList) {
            processedLines.push('</ul>');
        }
        
        return processedLines.join('\n');
    }

    // Dynamic message creation
    function createMessageElement(role, content, sources = [], isError = false) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${role}`;
        if (isError) {
            wrapper.classList.add('error-message');
        }
        
        const avatar = document.createElement('div');
        avatar.className = role === 'user' ? 'message-avatar user-avatar' : 'message-avatar';
        avatar.innerText = role === 'user' ? 'U' : '⚽';
        
        const body = document.createElement('div');
        body.className = 'message-body';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        if (role === 'assistant') {
            messageContent.classList.add('markdown-rendered');
            messageContent.innerHTML = isError 
                ? `<span class="error-title">⚠️ Erreur :</span> ${escapeHtml(content)}` 
                : renderMarkdown(content);
        } else {
            messageContent.textContent = content; // Secure textContent representation
        }
        body.appendChild(messageContent);
        
        // RAG Sources Block
        if (sources && sources.length > 0) {
            const sourcesBox = document.createElement('div');
            sourcesBox.className = 'rag-sources-box';
            
            const header = document.createElement('div');
            header.className = 'sources-header';
            header.innerHTML = `
                <span class="sources-title">
                    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2"/>
                    </svg>
                    Sources RAG consultées (${sources.length})
                </span>
            `;
            sourcesBox.appendChild(header);
            
            const listContainer = document.createElement('div');
            listContainer.className = 'sources-list-container';
            
            sources.forEach(src => {
                const item = document.createElement('div');
                item.className = 'source-item';
                item.innerHTML = `
                    <span class="source-file-badge" title="${escapeHtml(src.text)}">${escapeHtml(src.source)}</span>
                    <span class="source-score">score: ${src.score.toFixed(4)}</span>
                `;
                listContainer.appendChild(item);
            });
            
            sourcesBox.appendChild(listContainer);
            body.appendChild(sourcesBox);
        }
        
        // Bottom Action buttons (Disabled placeholders as per specifications)
        if (role === 'assistant' && !isError) {
            const actions = document.createElement('div');
            actions.className = 'message-actions';
            actions.innerHTML = `
                <button class="action-btn disabled" title="Exporter en PDF (Indisponible)" disabled>
                    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                    </svg>
                    Exporter PDF
                </button>
                <button class="action-btn disabled" title="Simplifier le contenu (Indisponible)" disabled>
                    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M15 12H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    Simplifier
                </button>
                <button class="action-btn disabled" title="Approfondir le concept (Indisponible)" disabled>
                    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                    Approfondir
                </button>
                <button class="action-btn disabled" title="Copier la réponse (Indisponible)" disabled>
                    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/>
                    </svg>
                    Copier
                </button>
            `;
            body.appendChild(actions);
        }
        
        wrapper.appendChild(avatar);
        wrapper.appendChild(body);
        return wrapper;
    }

    // Health checking function
    async function checkHealth() {
        const ragStatusText = document.getElementById('rag-status-text');
        const statusBadge = document.querySelector('.status-badge');
        
        try {
            const response = await fetch(`${API_BASE_URL}/api/health`);
            if (!response.ok) throw new Error('API non disponible');
            const data = await response.json();
            
            if (ragStatusText) {
                ragStatusText.textContent = `Index RAG : ${data.rag_chunks_loaded} chunks actifs (${data.rag_mode})`;
            }
            if (statusBadge) {
                statusBadge.style.borderColor = 'rgba(16, 185, 129, 0.2)';
                statusBadge.style.backgroundColor = 'rgba(16, 185, 129, 0.06)';
                statusBadge.style.color = 'var(--accent-green)';
            }
            
            document.querySelectorAll('.pulse-dot').forEach(dot => {
                dot.style.backgroundColor = 'var(--accent-green)';
            });
        } catch (error) {
            console.warn('API Offline - fallback démo actif:', error);
            if (ragStatusText) {
                ragStatusText.textContent = "Serveur déconnecté (mode démo)";
            }
            if (statusBadge) {
                statusBadge.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                statusBadge.style.backgroundColor = 'rgba(239, 68, 68, 0.06)';
                statusBadge.style.color = '#ef4444';
            }
            
            document.querySelectorAll('.pulse-dot').forEach(dot => {
                dot.style.backgroundColor = '#ef4444';
            });
        }
    }

    // Send chat message
    async function handleSendMessage() {
        if (!chatInput || !sendBtn || !messagesContainer) return;
        
        const query = chatInput.value.trim();
        if (!query) return;
        
        // Disable UI controls
        chatInput.value = '';
        chatInput.style.height = '38px';
        chatInput.disabled = true;
        sendBtn.disabled = true;
        
        // Render user message bubble
        const userMsgEl = createMessageElement('user', query);
        messagesContainer.appendChild(userMsgEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Render loading bubble
        const typingWrapper = document.createElement('div');
        typingWrapper.className = 'message-wrapper assistant loading-wrapper';
        typingWrapper.innerHTML = `
            <div class="message-avatar">⚽</div>
            <div class="message-body">
                <div class="message-content">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        `;
        messagesContainer.appendChild(typingWrapper);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        try {
            const payload = {
                message: query,
                mode: currentMode,
                history: messageHistory
            };
            
            const response = await fetch(`${API_BASE_URL}/api/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `Le serveur a renvoyé le code statut ${response.status}`);
            }
            
            const data = await response.json();
            
            // Remove typing bubble
            typingWrapper.remove();
            
            // Render assistant response bubble
            const assistantMsgEl = createMessageElement('assistant', data.answer, data.sources);
            messagesContainer.appendChild(assistantMsgEl);
            
            // Save inside history
            messageHistory.push({ role: 'user', content: query });
            messageHistory.push({ role: 'assistant', content: data.answer });
            
        } catch (error) {
            console.error('Erreur API Chat:', error);
            typingWrapper.remove();
            
            // Render error bubble
            const errorMsgEl = createMessageElement(
                'assistant', 
                `Impossible de contacter le service tactique. Vérifiez que le serveur backend est démarré sur http://127.0.0.1:8000. Détail : ${error.message}`, 
                [], 
                true
            );
            messagesContainer.appendChild(errorMsgEl);
        } finally {
            chatInput.disabled = false;
            sendBtn.disabled = false;
            chatInput.focus();
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    // --- Event Listeners ---

    // 1. Switch Mode Handler
    modeCards.forEach(card => {
        card.addEventListener('click', () => {
            modeCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            
            const mode = card.getAttribute('data-mode');
            currentMode = mode;
            const config = modeConfigs[mode];
            
            if (config) {
                const welcomeWrapper = document.getElementById('welcome-message-wrapper');
                if (welcomeWrapper) {
                    welcomeWrapper.style.opacity = '0';
                    welcomeWrapper.style.transform = 'translateY(5px)';
                    
                    setTimeout(() => {
                        welcomeText.innerHTML = config.welcome.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                        chatInput.placeholder = config.placeholder;
                        welcomeWrapper.style.opacity = '1';
                        welcomeWrapper.style.transform = 'translateY(0)';
                    }, 200);
                }
            }
        });
    });

    // 2. Auto-grow Textarea Input
    if (chatInput) {
        chatInput.addEventListener('input', () => {
            chatInput.style.height = '38px';
            const scrollHeight = chatInput.scrollHeight;
            if (scrollHeight > 38) {
                chatInput.style.height = `${Math.min(scrollHeight, 150)}px`;
            }
        });

        // Submit query on Enter (without Shift key)
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
            }
        });
    }

    // Submit query on button click
    if (sendBtn) {
        sendBtn.addEventListener('click', () => {
            handleSendMessage();
        });
    }

    // 3. Mobile Menu Handlers
    if (mobileMenuToggle && appSidebar) {
        mobileMenuToggle.addEventListener('click', () => {
            appSidebar.classList.add('open');
        });
    }

    if (mobileMenuClose && appSidebar) {
        mobileMenuClose.addEventListener('click', () => {
            appSidebar.classList.remove('open');
        });
    }

    // Close sidebar on option click (mobile optimization)
    const sidebarItems = document.querySelectorAll('.sidebar-nav li, .new-chat-btn');
    sidebarItems.forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) {
                appSidebar.classList.remove('open');
            }
        });
    });

    // --- Startup initialization ---
    checkHealth();
});
