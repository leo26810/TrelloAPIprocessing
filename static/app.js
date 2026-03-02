const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.panel');

for (const tab of tabs) {
  tab.addEventListener('click', () => {
    tabs.forEach((t) => t.classList.remove('active'));
    panels.forEach((p) => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.tab).classList.add('active');
  });
}

const renderCard = (app, showScore = false) => `
  <article class="result-card">
    <h3>${app.name}</h3>
    <p class="meta">${app.category} · ${app.pricing}</p>
    ${showScore ? `<p class="score">Score: ${app.score.toFixed(3)}</p><p class="meta">${app.reason ?? ''}</p>` : ''}
    <p>${app.description}</p>
    <div class="tags">${(app.strengths || []).map((s) => `<span class="tag">${s}</span>`).join('')}</div>
    <p><a href="${app.website}" target="_blank" rel="noreferrer">Website öffnen ↗</a></p>
  </article>
`;

const analysisForm = document.getElementById('analysisForm');
const analysisResults = document.getElementById('analysisResults');
analysisForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const prompt = document.getElementById('promptInput').value.trim();
  const top_k = Number(document.getElementById('topK').value || 5);

  if (prompt.length < 4) {
    analysisResults.innerHTML = '<p>Bitte gib einen längeren Prompt ein.</p>';
    return;
  }

  analysisResults.innerHTML = '<p>Analysiere Prompt...</p>';

  const response = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, top_k })
  });

  if (!response.ok) {
    const error = await response.json();
    analysisResults.innerHTML = `<p>Fehler: ${error.detail || 'Unbekannt'}</p>`;
    return;
  }

  const data = await response.json();
  analysisResults.innerHTML = data.map((app) => renderCard(app, true)).join('');
});

const searchForm = document.getElementById('searchForm');
const searchResults = document.getElementById('searchResults');

searchForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const params = new URLSearchParams({
    query: document.getElementById('searchQuery').value,
    category: document.getElementById('searchCategory').value,
    pricing: document.getElementById('searchPricing').value,
    min_popularity: document.getElementById('minPopularity').value || '0',
  });

  const response = await fetch(`/api/search?${params.toString()}`);
  const data = await response.json();

  if (!data.length) {
    searchResults.innerHTML = '<p>Keine Ergebnisse mit den aktuellen Filtern.</p>';
    return;
  }

  searchResults.innerHTML = data.map((app) => renderCard(app)).join('');
});

window.addEventListener('load', () => {
  searchForm.dispatchEvent(new Event('submit'));
});
