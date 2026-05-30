// Emission + polling logic and keyboard helpers for VozVisible
(function(){
  let isGenerating = false;
  const POLL_INTERVAL = 2000;
  // Keep frontend polling aligned with backend task timeout (default 900s).
  const MAX_WAIT = Number(window.MAX_WAIT_MS || 900000); // ms
  const FORCE_LOCAL = ['localhost', '127.0.0.1'].includes(window.location.hostname);

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
    const finalPayload = { ...payload };
      if (FORCE_LOCAL) { finalPayload.force_local = '1'; finalPayload.mode = 'fast'; }
    const res = await fetch('/api/generate', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(finalPayload)
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
    let transientFailures = 0;
    const tick = async ()=>{
      if (stopped) return;
      try {
        const r = await fetch(`/api/status/${jobId}`);
        if (!r.ok) {
          transientFailures += 1;
          if (transientFailures < 3) {
            setTimeout(tick, POLL_INTERVAL);
            return;
          }
          const e = await r.json().catch(()=>({}));
          onUpdate({ error: e.error || 'Estado no disponible' });
          stopped=true;
          return;
        }
        const s = await r.json();
        if (s.logs && s.logs.length > 0 && typeof window.renderAgentLogs === 'function') {
            window.renderAgentLogs(s.logs);
        }
        transientFailures = 0;
        onUpdate(s);
        if (s.status === 'completed' || s.status === 'failed') { stopped = true; return; }
        if (Date.now() - start > MAX_WAIT) { onUpdate({ error: 'Tiempo excedido. El proceso tarda más de lo esperado; inténtalo de nuevo en unos segundos.' }); stopped = true; return; }
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

  // Fast emit - explicit fast mode (skip heavy LLM pipeline)
  window.emitirCustomFast = async function(){
    const texto = document.getElementById('customText').value.trim(); if (!texto || isGenerating) return;
    const fb = document.getElementById('customFeedback'); if (fb){ fb.classList.remove('hidden','text-feedback-fade'); fb.innerText='Preparando emisión rápida...'; void fb.offsetWidth; fb.classList.add('text-feedback-fade'); }
    isGenerating = true; document.querySelectorAll('.action-card').forEach(c=>c.classList.remove('card-active')); if (typeof showLoading === 'function') showLoading();
    try{
      const payload = { texto, api_key: window.apiKey || '', mode: 'fast' };
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

  async function setAudioFeedback(message, kind='info') {
    const fb = document.getElementById('customFeedback');
    if (!fb) return;
    fb.classList.remove('hidden', 'text-feedback-fade');
    fb.innerText = message;
    fb.className = `text-[10px] ${kind === 'error' ? 'text-error' : kind === 'success' ? 'text-primary-container' : 'text-outline'} text-feedback-fade`;
    void fb.offsetWidth;
    fb.classList.add('text-feedback-fade');
  }

  window.transcribirAudio = async function(){
    if (isGenerating) return;
    const inp = document.getElementById('audioFileInput'); if (!inp || !inp.files || inp.files.length===0) return;
    const file = inp.files[0];
    try{
      isGenerating = true;
      await setAudioFeedback('Transcribiendo audio...', 'info');
      const form = new FormData(); form.append('file', file);
      if (window.apiKey) form.append('api_key', window.apiKey);
      const res = await fetch('/api/transcribe', { method: 'POST', body: form });
      if (!res.ok) { const j = await res.json().catch(()=>({})); throw new Error(j.error || 'Error starting generation'); }
      const data = await res.json();
      const texto = (data.text || '').trim();
      if (!texto) throw new Error('La transcripción llegó vacía');
      const input = document.getElementById('customText');
      if (input) {
        input.value = texto;
        input.focus();
        input.select && input.select();
      }
      window.currentTipo = '';
      await setAudioFeedback('Texto transcrito. Revísalo y pulsa Emitir.', 'success');
      if (typeof addToLog === 'function') addToLog(texto);
    } catch(err){
      await setAudioFeedback(err.message || 'No se pudo transcribir el audio.', 'error');
      if (typeof showError === 'function') showError(err.message||'Error de transcripción');
    } finally {
      isGenerating = false;
    }
  };

  window.emitirDesdeAudio = window.transcribirAudio;

  // Browser recording helpers
  let _mediaRecorder = null;
  let _recordedChunks = [];

  window.toggleRecord = async function(btn){
    if (_mediaRecorder && _mediaRecorder.state === 'recording'){
      // stop
      _mediaRecorder.stop();
      btn.innerText = 'Grabar';
      return;
    }
    // start
    try{
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _recordedChunks = [];
      _mediaRecorder = new MediaRecorder(stream);
      _mediaRecorder.ondataavailable = (e)=>{ if (e.data && e.data.size>0) _recordedChunks.push(e.data); };
      _mediaRecorder.onstop = ()=>{
        const blob = new Blob(_recordedChunks, { type: 'audio/webm' });
        const file = new File([blob], 'recording.webm', { type: blob.type });
        // populate file input
        try{
          const dt = new DataTransfer(); dt.items.add(file);
          const inp = document.getElementById('audioFileInput'); inp.files = dt.files;
        }catch(e){ /* ignore */ }
        // transcribe first, then let the user review the text before emitting
        if (typeof window.transcribirAudio === 'function') window.transcribirAudio();
      };
      _mediaRecorder.start();
      btn.innerText = 'Detener';
    }catch(err){ if (typeof showError === 'function') showError('No se pudo acceder al micrófono: '+err.message); }
  };

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
