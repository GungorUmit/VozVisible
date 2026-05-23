// Emission + polling logic and keyboard helpers for VozVisible
(function(){
  let isGenerating = false;
  const POLL_INTERVAL = 2000;
  const MAX_WAIT = 120000; // ms

  function isTyping() {
    const el = document.activeElement;
    return el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable);
  }

  function pressPhrase(n) {
    try {
      const active = window.activeTab || 'cercanias';
      const panel = document.getElementById(`panel-${active}`);
      if (!panel) return;
      const buttons = panel.querySelectorAll('.phrase-card');
      if (buttons && buttons[n-1]) buttons[n-1].click();
    } catch(e) { /* ignore */ }
  }

  async function postGenerate(payload){
    const res = await fetch('/api/generate', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const j = await res.json().catch(()=>({}));
      throw new Error(j.error || 'Error starting generation');
    }
    return res.json();
  }

  function pollStatus(jobId, onUpdate){
    const start = Date.now();
    let stopped = false;
    const tick = async ()=>{
      if (stopped) return;
      try {
        const r = await fetch(`/api/status/${jobId}`);
        if (!r.ok) { const e = await r.json().catch(()=>({})); onUpdate({ error: e.error || 'Estado no disponible' }); stopped=true; return; }
        const s = await r.json();
        if (s.logs && s.logs.length > 0 && typeof window.renderAgentLogs === 'function') {
            window.renderAgentLogs(s.logs);
        }
        onUpdate(s);
        if (s.status === 'completed' || s.status === 'failed') { stopped = true; return; }
        if (Date.now() - start > MAX_WAIT) { onUpdate({ error: 'Tiempo excedido' }); stopped = true; return; }
      } catch(err){ onUpdate({ error: 'Error de red durante polling' }); stopped = true; return; }
      setTimeout(tick, POLL_INTERVAL);
    };
    setTimeout(tick, POLL_INTERVAL);
    return ()=>{ stopped = true; };
  }

  // Public emit functions used by template
  window.emitirAviso = async function(tipo, btnEl){
    if (isGenerating) return;
    isGenerating = true; window.currentTipo = tipo;
    document.querySelectorAll('.action-card').forEach(c=>c.classList.remove('card-active')); if (btnEl) btnEl.classList.add('card-active');
    if (typeof showLoading === 'function') showLoading();
    try{
      const payload = { tipo, api_key: window.apiKey || '' };
      const data = await postGenerate(payload);
      const jobId = data.job_id; if (!jobId) throw new Error('No job_id');
      pollStatus(jobId, (s)=>{
        if (s.error) { if (typeof showError === 'function') showError(s.error); isGenerating=false; }
        else if (s.status === 'completed') { if (typeof showSuccess === 'function') showSuccess(s.texto||'', s.video_url); isGenerating=false; }
        else if (s.status === 'failed') { if (typeof showError === 'function') showError(s.error||'Generación fallida'); isGenerating=false; }
      });
    } catch(err){ if (typeof showError === 'function') showError(err.message||'Error de conexión con el servidor.'); isGenerating=false; }
  };

  window.emitirCustom = async function(){
    const texto = document.getElementById('customText').value.trim(); if (!texto || isGenerating) return;
    const fb = document.getElementById('customFeedback'); if (fb){ fb.classList.remove('hidden','text-feedback-fade'); fb.innerText='Preparando conexión LSE...'; void fb.offsetWidth; fb.classList.add('text-feedback-fade'); }
    isGenerating = true; document.querySelectorAll('.action-card').forEach(c=>c.classList.remove('card-active')); if (typeof showLoading === 'function') showLoading();
    try{
      const payload = { texto, api_key: window.apiKey || '' };
      const data = await postGenerate(payload);
      const jobId = data.job_id; if (!jobId) throw new Error('No job_id');
      pollStatus(jobId, (s)=>{
        if (s.error) { if (typeof showError === 'function') showError(s.error); isGenerating=false; }
        else if (s.status === 'completed') { if (typeof showSuccess === 'function') showSuccess(s.texto||texto, s.video_url); document.getElementById('customText').value=''; isGenerating=false; }
        else if (s.status === 'failed') { if (typeof showError === 'function') showError(s.error||'Generación fallida'); isGenerating=false; }
      });
    } catch(err){ if (typeof showError === 'function') showError(err.message||'Error de conexión con el servidor.'); isGenerating=false; }
  };

  window.emitirAlerta = async function(texto){
    if (isGenerating) return; isGenerating = true; window.currentTipo = '';
    if (typeof showLoading === 'function') showLoading();
    try{
      const payload = { texto, api_key: window.apiKey || '' };
      const data = await postGenerate(payload);
      const jobId = data.job_id; if (!jobId) throw new Error('No job_id');
      pollStatus(jobId, (s)=>{
        if (s.error) { if (typeof showError === 'function') showError(s.error); isGenerating=false; }
        else if (s.status === 'completed') { if (typeof showSuccess === 'function') showSuccess(s.texto||texto, s.video_url); isGenerating=false; }
        else if (s.status === 'failed') { if (typeof showError === 'function') showError(s.error||'Generación fallida'); isGenerating=false; }
      });
    } catch(err){ if (typeof showError === 'function') showError(err.message||'Error de conexión con el servidor.'); isGenerating=false; }
  };

  window.triggerCustomEmission = async function(texto){ if (!texto) return; document.getElementById('customText').value = texto; window.emitirCustom(); };

  // Hotkeys
  document.addEventListener('keydown', (ev)=>{
    if (isTyping()) return; const key = ev.key.toLowerCase();
    if (key === 'escape') { if (typeof detenerMegafonia === 'function') detenerMegafonia(); }
    else if (key === 'f') { if (typeof toggleFullscreen === 'function') toggleFullscreen(); }
    else if (key === 'c') { const t = document.getElementById('customText'); if (t){ t.focus(); t.select && t.select(); } }
    else if (key === '1') { pressPhrase(1); }
    else if (key === '2') { pressPhrase(2); }
    else if (key === '3') { pressPhrase(3); }
  });

})();
