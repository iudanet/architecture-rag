const log = document.getElementById('log');
const form = document.getElementById('form');
const input = document.getElementById('q');
const send = document.getElementById('send');

function add(cls, text) {
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  el.textContent = text;
  log.appendChild(el);
  return el;
}

// Строит блок источников: кликабельная ссылка на документ + score + сниппет
function renderCitations(citations) {
  const box = document.createElement('div');
  box.className = 'citations';

  for (const c of citations) {
    const item = document.createElement('div');
    item.className = 'citation';

    const head = document.createElement('div');
    head.className = 'citation-head';

    const link = document.createElement('a');
    link.href = c.url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = c.title || c.source;
    head.appendChild(link);

    const score = document.createElement('span');
    score.className = 'citation-score';
    score.textContent = 'score: ' + Number(c.score).toFixed(3);
    head.appendChild(score);

    item.appendChild(head);

    const snippet = document.createElement('div');
    snippet.className = 'citation-snippet';
    snippet.textContent = c.snippet;
    item.appendChild(snippet);

    box.appendChild(item);
  }

  return box;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = input.value.trim();
  if (!question) return;

  add('user', question);
  input.value = '';
  send.disabled = true;
  const pending = add('bot', 'Ищу в базе знаний…');

  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({question})
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();

    pending.textContent = data.answer;

    if (data.citations && data.citations.length) {
      pending.appendChild(renderCitations(data.citations));
    }

    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.textContent = `фрагментов: ${data.chunks_used} · max_score: ${data.max_score.toFixed(3)}`;
    pending.appendChild(meta);
  } catch (err) {
    pending.textContent = 'Ошибка запроса: ' + err.message;
  } finally {
    send.disabled = false;
    input.focus();
  }
});
