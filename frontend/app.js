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
    const chartContainer = document.getElementById('chart-container');

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
        
        // Hide and clear chart
        chartContainer.classList.add('hidden');
        chartContainer.innerHTML = '';
        
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

                // Nettoyage de l'affichage du JSON brut en cours de frappe
                let displayText = fullText;
                const jsonMarkerIndex = fullText.indexOf('```json');
                if (jsonMarkerIndex !== -1) {
                    displayText = fullText.substring(0, jsonMarkerIndex).trim();
                }

                // Rendu progressif en HTML (Markdown)
                if (window.marked) {
                    responseContent.innerHTML = marked.parse(displayText);
                } else {
                    responseContent.innerHTML = `<pre style="white-space: pre-wrap; font-family: inherit;">${displayText}</pre>`;
                }
            }

            // Extraction finale du JSON pour le graphique
            const jsonMarkerIndex = fullText.indexOf('```json');
            if (jsonMarkerIndex !== -1) {
                const jsonEndIndex = fullText.indexOf('```', jsonMarkerIndex + 7);
                if (jsonEndIndex !== -1) {
                    const jsonStr = fullText.substring(jsonMarkerIndex + 7, jsonEndIndex).trim();
                    try {
                        const chartData = JSON.parse(jsonStr);
                        renderSvgChart(chartData);
                    } catch (e) {
                        console.error("Erreur lors de la lecture du JSON du graphique :", e);
                    }
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

const METRIC_LABELS = {
    'goals': 'Buts',
    'xg': 'Expected Goals (xG)',
    'xa': 'Expected Assists (xA)',
    'key_passes': 'Passes Clés',
    'dribbles_prog': 'Dribbles Progressifs',
    'pressions_def': 'Pressions Défensives'
};

const COLORS = [
    { fill: 'rgba(255, 255, 255, 0.12)', stroke: '#ffffff', shadow: 'rgba(255, 255, 255, 0.3)' }, // Blanc
    { fill: 'rgba(255, 214, 10, 0.12)', stroke: '#ffd60a', shadow: 'rgba(255, 214, 10, 0.3)' }, // Ambre
    { fill: 'rgba(10, 132, 255, 0.12)', stroke: '#0a84ff', shadow: 'rgba(10, 132, 255, 0.3)' }, // Bleu
    { fill: 'rgba(191, 90, 242, 0.12)', stroke: '#bf5af2', shadow: 'rgba(191, 90, 242, 0.3)' }  // Violet
];

function renderSvgChart(chartData) {
    const chartContainer = document.getElementById('chart-container');
    if (!chartContainer || !chartData || !chartData.metrics || !chartData.players || chartData.players.length === 0) {
        return;
    }

    const metrics = chartData.metrics;
    const players = chartData.players;
    const numMetrics = metrics.length;

    // Calcul des valeurs maximales pour normaliser chaque métrique
    const maxValues = metrics.map((_, i) => {
        const vals = players.map(p => p.data[i] || 0);
        const max = Math.max(...vals);
        return max > 0 ? max : 1.0;
    });

    const isBar = chartData.chart_type === 'bar';
    let svgHtml = '';
    let titleText = isBar ? "Comparatif des Performances" : "Radar Tactique de Performance";

    if (isBar) {
        // Horizontal Bar Chart
        let barHtml = '';
        metrics.forEach((metric, i) => {
            const metricLabel = METRIC_LABELS[metric] || metric;
            const yOffset = 25 + i * 65;

            // Nom de la métrique
            barHtml += `<text x="140" y="${yOffset + 14}" fill="#ffffff" font-size="12" font-weight="600" text-anchor="end" font-family="inherit">${metricLabel}</text>`;

            // Barres des joueurs pour cette métrique
            players.forEach((player, pIdx) => {
                const color = COLORS[pIdx % COLORS.length];
                const val = player.data[i] || 0;
                const normVal = val / maxValues[i];
                const barWidth = Math.max(normVal * 280, 2);
                const barY = yOffset + pIdx * 13;

                barHtml += `
                    <rect x="150" y="${barY}" width="${barWidth}" height="8" rx="4" fill="${color.stroke}" style="filter: drop-shadow(0 0 2px ${color.shadow});" />
                    <text x="${156 + barWidth}" y="${barY + 7}" fill="#a1a1aa" font-size="9" font-weight="500" font-family="inherit">${val}</text>
                `;
            });
        });

        svgHtml = `
            <svg class="chart-svg" width="500" height="${35 + numMetrics * 65}" viewBox="0 0 500 ${35 + numMetrics * 65}" xmlns="http://www.w3.org/2000/svg">
                ${barHtml}
            </svg>
        `;
    } else {
        // Radar Chart
        const CX = 250;
        const CY = 190;
        const R = 110;
        const angleStep = (Math.PI * 2) / numMetrics;

        // Anneaux concentriques
        let gridHtml = '';
        const levels = [0.25, 0.5, 0.75, 1.0];
        levels.forEach(level => {
            const points = [];
            for (let i = 0; i < numMetrics; i++) {
                const angle = -Math.PI / 2 + i * angleStep;
                const x = CX + R * level * Math.cos(angle);
                const y = CY + R * level * Math.sin(angle);
                points.push(`${x},${y}`);
            }
            gridHtml += `<polygon points="${points.join(' ')}" fill="none" stroke="rgba(255, 255, 255, 0.08)" stroke-width="1" stroke-dasharray="3,3" />`;
        });

        // Axes (spokes)
        let spokeHtml = '';
        for (let i = 0; i < numMetrics; i++) {
            const angle = -Math.PI / 2 + i * angleStep;
            const x = CX + R * Math.cos(angle);
            const y = CY + R * Math.sin(angle);
            spokeHtml += `<line x1="${CX}" y1="${CY}" x2="${x}" y2="${y}" stroke="rgba(255, 255, 255, 0.08)" stroke-width="1" />`;
        }

        // Polygones et points des joueurs
        let playersPolygons = '';
        let playersPoints = '';
        players.forEach((player, pIdx) => {
            const color = COLORS[pIdx % COLORS.length];
            const points = [];
            player.data.forEach((val, i) => {
                const angle = -Math.PI / 2 + i * angleStep;
                const normVal = (val || 0) / maxValues[i];
                const x = CX + R * normVal * Math.cos(angle);
                const y = CY + R * normVal * Math.sin(angle);
                points.push(`${x},${y}`);

                // Cercle sur chaque sommet
                playersPoints += `<circle cx="${x}" cy="${y}" r="3.5" fill="${color.stroke}" style="filter: drop-shadow(0 0 2px ${color.shadow});" />`;
            });

            playersPolygons += `<polygon points="${points.join(' ')}" fill="${color.fill}" stroke="${color.stroke}" stroke-width="2" style="filter: drop-shadow(0 0 3px ${color.shadow});" />`;
        });

        // Étiquettes textuelles
        let labelsHtml = '';
        for (let i = 0; i < numMetrics; i++) {
            const angle = -Math.PI / 2 + i * angleStep;
            const labelRadius = R + 22;
            const x = CX + labelRadius * Math.cos(angle);
            const y = CY + labelRadius * Math.sin(angle);
            const labelText = METRIC_LABELS[metrics[i]] || metrics[i];

            let textAnchor = 'middle';
            if (Math.abs(Math.cos(angle)) > 0.1) {
                textAnchor = Math.cos(angle) > 0 ? 'start' : 'end';
            }
            let dy = "0.35em";
            if (Math.sin(angle) < -0.9) dy = "-0.1em";
            if (Math.sin(angle) > 0.9) dy = "1.0em";

            labelsHtml += `<text x="${x}" y="${y}" fill="#a1a1aa" font-size="11" font-weight="500" text-anchor="${textAnchor}" dy="${dy}" font-family="inherit">${labelText}</text>`;
        }

        svgHtml = `
            <svg class="chart-svg" width="500" height="380" viewBox="0 0 500 380" xmlns="http://www.w3.org/2000/svg">
                <g>${gridHtml}${spokeHtml}</g>
                <g>${playersPolygons}${playersPoints}</g>
                <g>${labelsHtml}</g>
            </svg>
        `;
    }

    // Construction de la légende
    let legendHtml = '<div class="chart-legend">';
    players.forEach((player, pIdx) => {
        const color = COLORS[pIdx % COLORS.length];
        legendHtml += `
            <div class="legend-item">
                <span class="legend-color" style="background-color: ${color.stroke}; --shadow-color: ${color.shadow};"></span>
                <span>${player.name}</span>
            </div>
        `;
    });
    legendHtml += '</div>';

    chartContainer.innerHTML = `<div class="chart-title">${titleText}</div>` + svgHtml + legendHtml;
    chartContainer.classList.remove('hidden');
}
