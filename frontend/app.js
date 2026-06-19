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

            // Consommation du flux de réponse chunk par chunk
            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            
            responseContent.innerHTML = '';
            responseContent.classList.remove('hidden');
            
            let fullText = '';
            let isFirstChunk = true;

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                if (isFirstChunk) {
                    responseLoading.classList.add('hidden');
                    isFirstChunk = false;
                }

                const chunk = decoder.decode(value, { stream: true });
                fullText += chunk;

                // Rendu progressif en HTML (Markdown)
                if (window.marked) {
                    responseContent.innerHTML = marked.parse(fullText);
                } else {
                    responseContent.innerHTML = `<pre style="white-space: pre-wrap; font-family: inherit;">${fullText}</pre>`;
                }
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
