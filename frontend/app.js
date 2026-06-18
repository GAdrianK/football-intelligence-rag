document.addEventListener('DOMContentLoaded', () => {
    // Dynamic base URL detection
    const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol.startsWith('file')
        ? 'http://127.0.0.1:8000'
        : 'https://football-iq-backend.onrender.com';

    const promptInput = document.getElementById('prompt-input');
    const seasonSelect = document.getElementById('season-select');
    const analyzeBtn = document.getElementById('analyze-btn');
    const errorBox = document.getElementById('error-box');
    const responseBox = document.getElementById('response-box');
    const responseLoading = document.getElementById('response-loading');
    const responseContent = document.getElementById('response-content');

    analyzeBtn.addEventListener('click', async () => {
        const prompt = promptInput.value.trim();
        if (!prompt) return;

        const season = seasonSelect.value;

        // UI State: Loading (conforming to the React template's CSS styles)
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = 'Analyse...';
        analyzeBtn.style.backgroundColor = '#27272a';
        analyzeBtn.style.color = '#a1a1aa';
        analyzeBtn.style.cursor = 'not-allowed';

        // Reset error
        errorBox.classList.add('hidden');
        errorBox.textContent = '';
        
        // Setup response area visibility
        responseContent.classList.add('hidden');
        responseContent.innerHTML = '';
        
        responseLoading.classList.remove('hidden');
        responseBox.classList.remove('hidden');

        try {
            const response = await fetch(`${API_BASE_URL}/api/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, season })
            });

            if (!response.ok) {
                let errMsg = `Erreur serveur: ${response.status}`;
                try {
                    const errData = await response.json();
                    if (errData && errData.detail) {
                        errMsg = errData.detail;
                    }
                } catch (_) {}
                throw new Error(errMsg);
            }

            const data = await response.json();
            if (data.status === 'success') {
                // Parse markdown content inside the response container if marked is available, otherwise default to innerHTML/text
                if (window.marked) {
                    responseContent.innerHTML = marked.parse(data.analysis || '');
                } else {
                    responseContent.innerHTML = `<pre style="white-space: pre-wrap; font-family: inherit;">${data.analysis || ''}</pre>`;
                }
                responseContent.classList.remove('hidden');
            } else {
                throw new Error(data.detail || "Une erreur est survenue");
            }
        } catch (err) {
            errorBox.textContent = `⚠️ ${err.message || "Impossible de contacter le serveur tactique."}`;
            errorBox.classList.remove('hidden');
            responseBox.classList.add('hidden');
        } finally {
            // Restore button states
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = 'Analyser';
            analyzeBtn.style.backgroundColor = '#fafafa';
            analyzeBtn.style.color = '#09090b';
            analyzeBtn.style.cursor = 'pointer';
            responseLoading.classList.add('hidden');
        }
    });

    // Keyboard shortcut (Ctrl + Enter or Cmd + Enter) to submit
    promptInput.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            analyzeBtn.click();
        }
    });
});
