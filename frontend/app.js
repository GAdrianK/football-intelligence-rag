document.addEventListener('DOMContentLoaded', () => {
    // API Configurations
    // EN DÉVELOPPEMENT LOCAL : utilise http://127.0.0.1:8000
    // EN PRODUCTION : Remplacez l'URL ci-dessous par l'URL de votre backend Render
    const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol.startsWith('file')
        ? 'http://127.0.0.1:8000'
        : 'https://football-iq-backend.onrender.com'; // À remplacer par l'URL de votre serveur Render

    const LS_KEY = 'fiq_session';

    // Session State
    let currentSession = {
        mode: 'coach',
        messages: []   // { role, content, sources? }
    };

    // Selectors
    const modeCards = document.querySelectorAll('.mode-card');
    const welcomeText = document.getElementById('welcome-text');
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-message-btn');
    const messagesContainer = document.getElementById('chat-messages-container');
    const newSessionBtn = document.querySelector('.new-chat-btn');
    
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

    // =============================================================
    // localStorage helpers
    // =============================================================

    function saveSession() {
        try {
            localStorage.setItem(LS_KEY, JSON.stringify(currentSession));
        } catch (e) {
            console.warn('localStorage indisponible :', e);
        }
    }

    function loadStoredSession() {
        try {
            const raw = localStorage.getItem(LS_KEY);
            if (!raw) return null;
            const parsed = JSON.parse(raw);
            // Validation minimale
            if (parsed && parsed.mode && Array.isArray(parsed.messages)) {
                return parsed;
            }
        } catch (e) {
            console.warn('Session corrompue, ignorée :', e);
        }
        return null;
    }

    function clearStoredSession() {
        try {
            localStorage.removeItem(LS_KEY);
        } catch (e) {}
    }

    // =============================================================
    // Helpers
    // =============================================================

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
        
        // Parse Headers
        html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
        html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
        html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');
        
        // Parse Bold
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

    // Rend un rapport tactique structuré sous forme de dashboard premium
    function renderTacticalReportHTML(report) {
        return `
            <div class="tactical-report-dashboard">
                <div class="report-header">
                    <span class="report-tag">📊 RAPPORT D'ANALYSE TACTIQUE</span>
                    <h3>${escapeHtml(report.titre)}</h3>
                    <p class="report-subject"><strong>Sujet :</strong> ${escapeHtml(report.match_ou_sujet)}</p>
                </div>
                
                <div class="report-grid">
                    <div class="report-card">
                        <div class="card-title">⚔️ Organisation Offensive</div>
                        <div class="card-detail-item"><strong>Création :</strong> ${escapeHtml(report.organisation_offensive.creation)}</div>
                        <div class="card-detail-item"><strong>Espaces :</strong> ${escapeHtml(report.organisation_offensive.espaces)}</div>
                        <div class="card-detail-item"><strong>Largeur :</strong> ${escapeHtml(report.organisation_offensive.largeur)}</div>
                        <div class="card-detail-item"><strong>Profondeur :</strong> ${escapeHtml(report.organisation_offensive.profondeur)}</div>
                    </div>

                    <div class="report-card">
                        <div class="card-title">🛡️ Organisation Défensive</div>
                        <div class="card-detail-item"><strong>Bloc :</strong> ${escapeHtml(report.organisation_defensive.bloc)}</div>
                        <div class="card-detail-item"><strong>Compacité :</strong> ${escapeHtml(report.organisation_defensive.compacite)}</div>
                        <div class="card-detail-item"><strong>Duels :</strong> ${escapeHtml(report.organisation_defensive.duels)}</div>
                        <div class="card-detail-item"><strong>Couverture :</strong> ${escapeHtml(report.organisation_defensive.couverture)}</div>
                    </div>

                    <div class="report-card">
                        <div class="card-title">⚡ Pressing & Transitions</div>
                        <div class="card-detail-item"><strong>Pressing (Intensité) :</strong> ${escapeHtml(report.pressing.intensite)}</div>
                        <div class="card-detail-item"><strong>Pressing (Zones) :</strong> ${escapeHtml(report.pressing.zones)}</div>
                        <div class="card-detail-item"><strong>Transition Off. :</strong> ${escapeHtml(report.transitions.offensive)}</div>
                        <div class="card-detail-item"><strong>Transition Déf. :</strong> ${escapeHtml(report.transitions.defensive)}</div>
                    </div>

                    <div class="report-card">
                        <div class="card-title">🏗️ Sortie & Progression</div>
                        <div class="card-detail-item"><strong>Relance :</strong> ${escapeHtml(report.construction.relance)}</div>
                        <div class="card-detail-item"><strong>Progression :</strong> ${escapeHtml(report.construction.progression)}</div>
                    </div>

                    <div class="report-card">
                        <div class="card-title">🏃‍♂️ Animation des Couloirs</div>
                        <div class="card-detail-item"><strong>Ailes :</strong> ${escapeHtml(report.couloirs.ailes)}</div>
                        <div class="card-detail-item"><strong>Centres :</strong> ${escapeHtml(report.couloirs.centres)}</div>
                    </div>

                    <div class="report-card">
                        <div class="card-title">💎 Milieu & Occasions</div>
                        <div class="card-detail-item"><strong>Milieu (Domination) :</strong> ${escapeHtml(report.milieu.domination)}</div>
                        <div class="card-detail-item"><strong>Milieu (Création) :</strong> ${escapeHtml(report.milieu.creation)}</div>
                        <div class="card-detail-item"><strong>Occasions (Qualité) :</strong> ${escapeHtml(report.occasions.qualite)}</div>
                        <div class="card-detail-item"><strong>Occasions (Volume) :</strong> ${escapeHtml(report.occasions.volume)}</div>
                    </div>
                </div>

                <div class="report-section-full">
                    <div class="section-title">👥 Analyse Individuelle (Joueurs Clés)</div>
                    <div class="players-list">
                        ${report.joueurs_cles.map(player => `
                            <div class="player-card">
                                <div class="player-header">
                                    <strong>${escapeHtml(player.nom)}</strong>
                                </div>
                                <div class="player-info-text"><strong>Impact :</strong> ${escapeHtml(player.impact)}</div>
                                ${player.erreurs ? `<div class="player-info-text warnings"><strong>Axe de vigilance :</strong> ${escapeHtml(player.erreurs)}</div>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>

                <div class="report-section-full recommendations-section">
                    <div class="section-title">💡 Recommandations Tactiques</div>
                    <div class="recs-list">
                        <div class="rec-work-axes">
                            <strong>Axes de travail prioritaires :</strong>
                            <ul>
                                ${report.recommandations.axes_travail.map(axe => `<li>${escapeHtml(axe)}</li>`).join('')}
                            </ul>
                        </div>
                        <div class="rec-drill">
                            <strong>⚽ Exercice terrain préconisé :</strong>
                            <p>${escapeHtml(report.recommandations.exercice_entrainement)}</p>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // =============================================================
    // API call helpers (shared by send + quick actions)
    // =============================================================

    async function callChatAPI(message) {
        const payload = {
            message: message,
            mode: currentSession.mode,
            history: currentSession.messages
        };
        
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Statut serveur ${response.status}`);
        }
        
        return response.json();
    }

    async function callAnalyzeAPI(query) {
        const payload = {
            query: query
        };
        
        const response = await fetch(`${API_BASE_URL}/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Statut serveur ${response.status}`);
        }
        
        return response.json();
    }

    // =============================================================
    // Quick Action helpers (Simplifier / Approfondir)
    // =============================================================

    async function handleQuickAction(actionLabel, prefixPrompt, rawContent, actionsEl) {
        // Disable all action buttons while processing
        actionsEl.querySelectorAll('.action-btn').forEach(b => b.disabled = true);
        
        const fullMessage = `${prefixPrompt} : ${rawContent.slice(0, 1200)}`;

        // Render user pseudo-message (label only for clarity)
        const userMsgEl = createMessageElement('user', `[${actionLabel}] ${rawContent.slice(0, 80)}…`);
        messagesContainer.appendChild(userMsgEl);

        // Typing bubble
        const typingWrapper = buildTypingBubble();
        messagesContainer.appendChild(typingWrapper);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        try {
            const data = await callChatAPI(fullMessage);
            typingWrapper.remove();

            const assistantMsgEl = createMessageElement('assistant', data.answer, data.sources || []);
            messagesContainer.appendChild(assistantMsgEl);

            currentSession.messages.push({ role: 'user', content: fullMessage });
            currentSession.messages.push({ role: 'assistant', content: data.answer, sources: data.sources });
            saveSession();
        } catch (error) {
            console.error('Quick action error:', error);
            typingWrapper.remove();
            const errorEl = createMessageElement('assistant', `Erreur : ${error.message}`, [], true);
            messagesContainer.appendChild(errorEl);
        } finally {
            actionsEl.querySelectorAll('.action-btn').forEach(b => b.disabled = false);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    // =============================================================
    // Export PDF helper
    // =============================================================

    async function handleExportPDF(rawContent, btn) {
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<span>⏳ Génération...</span>`;

        try {
            // Build a valid PDFExportRequest payload from the response text
            // Split by ### headers to create individual blocks
            const modeLabel = { coach: 'Coach', analyst: 'Analyste', fan: 'Fan' }[currentSession.mode] || 'Assistant';
            const lines = rawContent.split('\n');
            const blocks = [];
            let currentBlockTitle = 'Réponse tactique';
            let currentBlockLines = [];

            for (const line of lines) {
                const stripped = line.trim();
                if (stripped.startsWith('### ') || stripped.startsWith('## ')) {
                    // Save previous block if it has content
                    if (currentBlockLines.length > 0) {
                        blocks.push({ title: currentBlockTitle, content: currentBlockLines.join('\n').trim() });
                        currentBlockLines = [];
                    }
                    currentBlockTitle = stripped.replace(/^#{2,3}\s+/, '');
                } else if (stripped) {
                    currentBlockLines.push(stripped);
                }
            }
            // Save last block
            if (currentBlockLines.length > 0) {
                blocks.push({ title: currentBlockTitle, content: currentBlockLines.join('\n').trim() });
            }
            // Fallback if no blocks were created
            if (blocks.length === 0) {
                blocks.push({ title: 'Analyse', content: rawContent.trim() });
            }

            const payload = {
                title: `Fiche tactique — Mode ${modeLabel}`,
                coach: 'Football IQ Assistant',
                blocks: blocks
            };

            const response = await fetch(`${API_BASE_URL}/api/export-pdf`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error(`Statut ${response.status}`);

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `football-iq-${currentSession.mode}-${Date.now()}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);

            btn.innerHTML = `<span>✅ Téléchargé</span>`;
            setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2500);
        } catch (err) {
            console.error('Export PDF error:', err);
            btn.innerHTML = `<span>❌ Erreur PDF</span>`;
            setTimeout(() => { btn.innerHTML = originalText; btn.disabled = false; }, 2500);
        }
    }

    // =============================================================
    // Message element builder
    // =============================================================

    function createMessageElement(role, content, sources = [], isError = false) {
        const wrapper = document.createElement('div');
        wrapper.className = `message-wrapper ${role}`;
        if (isError) wrapper.classList.add('error-message');
        
        const avatar = document.createElement('div');
        avatar.className = role === 'user' ? 'message-avatar user-avatar' : 'message-avatar';
        avatar.innerText = role === 'user' ? 'U' : '⚽';
        
        const body = document.createElement('div');
        body.className = 'message-body';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        if (role === 'assistant') {
            const trimmed = content.trim();
            if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
                try {
                    const report = JSON.parse(trimmed);
                    messageContent.innerHTML = renderTacticalReportHTML(report);
                } catch (e) {
                    messageContent.classList.add('markdown-rendered');
                    messageContent.innerHTML = isError 
                        ? `<span class="error-title">⚠️ Erreur :</span> ${escapeHtml(content)}` 
                        : renderMarkdown(content);
                }
            } else {
                messageContent.classList.add('markdown-rendered');
                messageContent.innerHTML = isError 
                    ? `<span class="error-title">⚠️ Erreur :</span> ${escapeHtml(content)}` 
                    : renderMarkdown(content);
            }
        } else {
            messageContent.textContent = content;
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
        
        // Action buttons — only for real assistant messages, not errors
        if (role === 'assistant' && !isError) {
            const actions = document.createElement('div');
            actions.className = 'message-actions';

            // --- PDF button ---
            const pdfBtn = document.createElement('button');
            pdfBtn.className = 'action-btn';
            pdfBtn.title = 'Exporter cette réponse en PDF';
            pdfBtn.innerHTML = `
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                </svg>
                Exporter PDF`;
            pdfBtn.addEventListener('click', () => handleExportPDF(content, pdfBtn));

            // --- Simplifier button ---
            const simplifyBtn = document.createElement('button');
            simplifyBtn.className = 'action-btn';
            simplifyBtn.title = 'Obtenir une version simplifiée';
            simplifyBtn.innerHTML = `
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M15 12H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                Simplifier`;
            simplifyBtn.addEventListener('click', () =>
                handleQuickAction(
                    'Simplifier',
                    'Simplifie cette réponse pour un débutant complet, en termes très simples et accessibles',
                    content,
                    actions
                )
            );

            // --- Approfondir button ---
            const deepenBtn = document.createElement('button');
            deepenBtn.className = 'action-btn';
            deepenBtn.title = 'Obtenir une version plus détaillée';
            deepenBtn.innerHTML = `
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                Approfondir`;
            deepenBtn.addEventListener('click', () =>
                handleQuickAction(
                    'Approfondir',
                    'Approfondis cette réponse avec beaucoup plus de détails tactiques, exercices concrets et exemples professionnels',
                    content,
                    actions
                )
            );

            // --- Copier button ---
            const copyBtn = document.createElement('button');
            copyBtn.className = 'action-btn';
            copyBtn.title = 'Copier la réponse';
            copyBtn.innerHTML = `
                <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"/>
                </svg>
                Copier`;
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(content).then(() => {
                    const originalHTML = copyBtn.innerHTML;
                    copyBtn.innerHTML = `<span class="copied-feedback">✅ Copié !</span>`;
                    copyBtn.classList.add('btn-copied');
                    setTimeout(() => {
                        copyBtn.innerHTML = originalHTML;
                        copyBtn.classList.remove('btn-copied');
                    }, 2000);
                }).catch(err => {
                    console.error('Clipboard error:', err);
                });
            });

            actions.appendChild(pdfBtn);
            actions.appendChild(simplifyBtn);
            actions.appendChild(deepenBtn);
            actions.appendChild(copyBtn);
            body.appendChild(actions);
        }
        
        wrapper.appendChild(avatar);
        wrapper.appendChild(body);
        return wrapper;
    }

    // =============================================================
    // Typing bubble builder
    // =============================================================

    function buildTypingBubble() {
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
        return typingWrapper;
    }

    // =============================================================
    // Session Management
    // =============================================================

    /**
     * Resets the chat UI for a given mode.
     * Clears DOM, localStorage, history — then shows welcome bubble.
     * @param {string} mode
     */
    function resetSession(mode) {
        currentSession = { mode: mode, messages: [] };
        clearStoredSession();

        if (messagesContainer) messagesContainer.innerHTML = '';
        if (chatInput) {
            chatInput.value = '';
            chatInput.style.height = '38px';
            chatInput.disabled = false;
        }
        if (sendBtn) sendBtn.disabled = false;

        const config = modeConfigs[mode];
        if (!config) return;

        if (chatInput) chatInput.placeholder = config.placeholder;

        const welcomeWrapper = document.getElementById('welcome-message-wrapper');
        if (welcomeWrapper && welcomeText) {
            welcomeWrapper.style.opacity = '0';
            welcomeWrapper.style.transform = 'translateY(5px)';
            setTimeout(() => {
                welcomeText.innerHTML = config.welcome.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
                welcomeWrapper.style.opacity = '1';
                welcomeWrapper.style.transform = 'translateY(0)';
            }, 150);
        }

        const welcomeBubble = createMessageElement('assistant', config.welcome);
        welcomeBubble.classList.add('welcome-bubble');
        if (messagesContainer) messagesContainer.appendChild(welcomeBubble);
    }

    /**
     * Restores a previously saved session from localStorage.
     * Re-renders all messages in the DOM.
     * @param {object} saved
     */
    function restoreSession(saved) {
        currentSession = { mode: saved.mode, messages: [] };

        if (messagesContainer) messagesContainer.innerHTML = '';

        const config = modeConfigs[saved.mode];
        if (config) {
            if (chatInput) chatInput.placeholder = config.placeholder;
            const welcomeWrapper = document.getElementById('welcome-message-wrapper');
            if (welcomeWrapper && welcomeText) {
                welcomeText.innerHTML = config.welcome.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            }
        }

        // Re-activate the right mode card
        modeCards.forEach(card => {
            card.classList.toggle('active', card.getAttribute('data-mode') === saved.mode);
        });

        // Replay messages
        saved.messages.forEach(msg => {
            const el = createMessageElement(msg.role, msg.content, msg.sources || []);
            if (messagesContainer) messagesContainer.appendChild(el);
            currentSession.messages.push(msg);
        });

        if (messagesContainer) messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // =============================================================
    // Health check
    // =============================================================

    async function checkHealth() {
        const ragStatusText = document.getElementById('rag-status-text');
        const statusBadge = document.querySelector('.status-badge');
        
        try {
            const response = await fetch(`${API_BASE_URL}/api/health`);
            if (!response.ok) throw new Error('API non disponible');
            const data = await response.json();
            
            if (ragStatusText) ragStatusText.textContent = `Index RAG : ${data.rag_chunks_loaded} chunks actifs (${data.rag_mode})`;
            if (statusBadge) {
                statusBadge.style.borderColor = 'rgba(16, 185, 129, 0.2)';
                statusBadge.style.backgroundColor = 'rgba(16, 185, 129, 0.06)';
                statusBadge.style.color = 'var(--accent-green)';
            }
            document.querySelectorAll('.pulse-dot').forEach(dot => dot.style.backgroundColor = 'var(--accent-green)');
        } catch (error) {
            console.warn('API Offline:', error);
            if (ragStatusText) ragStatusText.textContent = "Serveur déconnecté (mode démo)";
            if (statusBadge) {
                statusBadge.style.borderColor = 'rgba(239, 68, 68, 0.2)';
                statusBadge.style.backgroundColor = 'rgba(239, 68, 68, 0.06)';
                statusBadge.style.color = '#ef4444';
            }
            document.querySelectorAll('.pulse-dot').forEach(dot => dot.style.backgroundColor = '#ef4444');
        }
    }

    // =============================================================
    // Send message
    // =============================================================

    async function handleSendMessage() {
        if (!chatInput || !sendBtn || !messagesContainer) return;
        
        const query = chatInput.value.trim();
        if (!query) return;
        
        chatInput.value = '';
        chatInput.style.height = '38px';
        chatInput.disabled = true;
        sendBtn.disabled = true;
        
        const userMsgEl = createMessageElement('user', query);
        messagesContainer.appendChild(userMsgEl);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        const typingWrapper = buildTypingBubble();
        messagesContainer.appendChild(typingWrapper);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        const isAnalysisQuery = query.toLowerCase().includes('analyse') || 
                                query.toLowerCase().includes('analyser') || 
                                query.toLowerCase().includes('rapport');
        
        try {
            if (isAnalysisQuery) {
                const data = await callAnalyzeAPI(query);
                typingWrapper.remove();
                
                const reportStr = JSON.stringify(data.report);
                const assistantMsgEl = createMessageElement('assistant', reportStr, data.sources || []);
                messagesContainer.appendChild(assistantMsgEl);
                
                currentSession.messages.push({ role: 'user', content: query });
                currentSession.messages.push({ role: 'assistant', content: reportStr, sources: data.sources });
            } else {
                const data = await callChatAPI(query);
                typingWrapper.remove();
                
                const assistantMsgEl = createMessageElement('assistant', data.answer, data.sources || []);
                messagesContainer.appendChild(assistantMsgEl);
                
                currentSession.messages.push({ role: 'user', content: query });
                currentSession.messages.push({ role: 'assistant', content: data.answer, sources: data.sources });
            }
            saveSession();
            
        } catch (error) {
            console.error('Erreur API Chat:', error);
            typingWrapper.remove();
            const errorMsgEl = createMessageElement(
                'assistant', 
                `Impossible de contacter le service tactique. Vérifiez que le serveur backend est démarré sur http://127.0.0.1:8000. Détail : ${error.message}`, 
                [], true
            );
            messagesContainer.appendChild(errorMsgEl);
        } finally {
            chatInput.disabled = false;
            sendBtn.disabled = false;
            chatInput.focus();
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    }

    // =============================================================
    // Event Listeners
    // =============================================================

    // 1. Mode switch — resets session + clears localStorage
    modeCards.forEach(card => {
        card.addEventListener('click', () => {
            const newMode = card.getAttribute('data-mode');
            if (newMode === currentSession.mode) return;

            modeCards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');

            resetSession(newMode);
        });
    });

    // 2. New Session Button — resets + clears localStorage
    if (newSessionBtn) {
        newSessionBtn.addEventListener('click', () => {
            resetSession(currentSession.mode);
            if (window.innerWidth <= 768 && appSidebar) appSidebar.classList.remove('open');
        });
    }

    // 3. Auto-grow Textarea
    if (chatInput) {
        chatInput.addEventListener('input', () => {
            chatInput.style.height = '38px';
            const scrollHeight = chatInput.scrollHeight;
            if (scrollHeight > 38) chatInput.style.height = `${Math.min(scrollHeight, 150)}px`;
        });
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSendMessage();
            }
        });
    }

    // 4. Send button
    if (sendBtn) sendBtn.addEventListener('click', handleSendMessage);

    // 5. Mobile Menu
    if (mobileMenuToggle && appSidebar) mobileMenuToggle.addEventListener('click', () => appSidebar.classList.add('open'));
    if (mobileMenuClose && appSidebar) mobileMenuClose.addEventListener('click', () => appSidebar.classList.remove('open'));

    const sidebarItems = document.querySelectorAll('.sidebar-nav li, .new-chat-btn');
    sidebarItems.forEach(item => {
        item.addEventListener('click', () => {
            if (window.innerWidth <= 768) appSidebar.classList.remove('open');
        });
    });

    // =============================================================
    // Startup — restore or init fresh session
    // =============================================================

    const saved = loadStoredSession();
    if (saved && saved.messages.length > 0) {
        restoreSession(saved);
    } else {
        resetSession('coach');
    }
    checkHealth();
});
