document.addEventListener('DOMContentLoaded', () => {
    const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.protocol.startsWith('file')
        ? 'http://127.0.0.1:8000'
        : 'https://football-iq-backend.onrender.com'; // Fallback API URL

    const promptInput = document.getElementById('prompt-input');
    const seasonSelect = document.getElementById('season-select');
    const analyzeBtn = document.getElementById('analyze-btn');
    const loadingContainer = document.getElementById('loading');
    const resultsContainer = document.getElementById('results-container');
    const seasonBadge = document.getElementById('season-badge');
    const playersBadge = document.getElementById('players-badge');
    const analysisOutput = document.getElementById('analysis-output');

    analyzeBtn.addEventListener('click', async () => {
        const prompt = promptInput.value.trim();
        if (!prompt) return;

        const season = seasonSelect.value;

        // UI state: Loading
        analyzeBtn.disabled = true;
        loadingContainer.classList.remove('hidden');
        resultsContainer.classList.add('hidden');

        try {
            const response = await fetch(`${API_BASE_URL}/api/analyze`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ prompt, season })
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Erreur de communication avec le serveur backend');
            }

            const data = await response.json();

            // Meta update
            seasonBadge.textContent = season === 'season_2025_2026_summary' ? 'Saison 2025-2026' : 'Saison 2024-2025';
            
            const playersCount = data.players_found ? data.players_found.length : 0;
            playersBadge.textContent = `${playersCount} Joueur(s) détecté(s)`;

            // Render Markdown
            if (window.marked) {
                analysisOutput.innerHTML = marked.parse(data.analysis || '');
            } else {
                analysisOutput.textContent = data.analysis || '';
            }

            // UI state: Show Results
            resultsContainer.classList.remove('hidden');
        } catch (error) {
            console.error('Error during analysis request:', error);
            alert(`Erreur : ${error.message}`);
        } finally {
            analyzeBtn.disabled = false;
            loadingContainer.classList.add('hidden');
        }
    });

    // Keyboard shortcut (Ctrl + Enter or Cmd + Enter) to submit
    promptInput.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            analyzeBtn.click();
        }
    });
});
