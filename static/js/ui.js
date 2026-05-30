// UI helpers for VozVisible (showLoading, showSuccess, alerts, clock, etc.)
(function(){
  window.apiKey = localStorage.getItem("groq_api_key") || "";

  const SUBTITLES = {
    "cercanias_1": "🚉 Destino: Atocha",
    "cercanias_2": "🚉 Destino: Alcalá de Henares  ▸  Parada: Méndez Álvaro",
    "cercanias_3": "",
    "ave_1": "🚄 Destino: Barcelona  ▸  Vía 2",
    "ave_2": "",
    "ave_3": "🚄 Vía 1",
    "metro_1": "Ⓜ️ Estación: Sol  ▸  Líneas 1 y 3",
    "metro_2": "",
    "metro_3": "",
  };

  async function saveApiKey(){
    const key = document.getElementById('apiKeyInput').value;
    window.apiKey = key;
    localStorage.setItem('groq_api_key', key);
    try{
      const res = await fetch('/api/save-api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key })
      });
      const data = await res.json();
      if (res.ok){ showSuccess('Clave API guardada'); }
      else { showError(data.error || 'Error al guardar la clave'); }
    } catch(err){ showError(err.message); }
    document.getElementById('apiModal').classList.add('hidden');
  }

  function toggleFullscreen(){
    const monitor = document.getElementById('monitorSection');
    if (!document.fullscreenElement){ monitor.requestFullscreen().catch(err=>alert(`Error al intentar pantalla completa: ${err.message}`)); }
    else document.exitFullscreen();
  }

  document.addEventListener('fullscreenchange', ()=>{
    const isFs = !!document.fullscreenElement;
    const fsIcon = document.getElementById('fsIcon'); if (fsIcon) fsIcon.innerText = isFs ? 'fullscreen_exit' : 'fullscreen';
    const monitor = document.getElementById('monitorSection');
    const container = document.getElementById('monitorContainer');
    const subtitleText = document.getElementById('subtitleText');
    const subtitleBar = document.getElementById('subtitleBar');
    if (isFs){
      monitor.classList.remove('rounded-xl','border','border-primary/20','max-h-[600px]','p-2','aspect-video');
      monitor.classList.add('h-screen','w-screen','p-0','bg-black');
      if (container) {
          container.classList.remove('rounded-lg');
          // Hide left panel in fullscreen to make video 100%
          const leftPanel = container.querySelector('.lg\\:w-1\\/3');
          if (leftPanel) leftPanel.classList.add('hidden');
      }
      if (subtitleText) {
          subtitleText.classList.remove('text-lg');
          subtitleText.classList.add('text-4xl', 'md:text-6xl', 'leading-relaxed');
      }
      if (subtitleBar) subtitleBar.classList.replace('py-4', 'py-12');
    } else {
      monitor.classList.add('rounded-xl','border','border-primary/20','max-h-[600px]','p-2','aspect-video');
      monitor.classList.remove('h-screen','w-screen','p-0','bg-black');
      if (container) {
          container.classList.add('rounded-lg');
          const leftPanel = container.querySelector('.lg\\:w-1\\/3');
          if (leftPanel) leftPanel.classList.remove('hidden');
      }
      if (subtitleText) {
          subtitleText.classList.add('text-lg');
          subtitleText.classList.remove('text-4xl', 'md:text-6xl', 'leading-relaxed');
      }
      if (subtitleBar) subtitleBar.classList.replace('py-12', 'py-4');
    }
  });

  function switchTab(tab){
    window.activeTab = tab;
    ['cercanias','ave','metro'].forEach(t=>{
      const panel = document.getElementById('panel-'+t);
      if (panel) panel.classList.toggle('hidden', t!==tab);
      const tabBtn = document.getElementById('tab-'+t);
      if (tabBtn) tabBtn.className = (t===tab) ? "tab-active flex items-center gap-3 px-4 py-3 rounded-xl font-headline-md text-sm transition-all w-full text-left" : "tab-inactive flex items-center gap-3 px-4 py-3 rounded-xl font-headline-md text-sm transition-all w-full text-left";
    });
  }

  function showLoading(){
    const ls = document.getElementById('loadingSpinner'); if (ls) ls.classList.remove('hidden');
    const statusDot = document.getElementById('statusDot'); if (statusDot) statusDot.className = 'w-2 h-2 rounded-full bg-tertiary-fixed-dim pulse-dot';
    const statusLabel = document.getElementById('statusLabel'); if (statusLabel){ statusLabel.textContent='PROCESANDO AVISO...'; statusLabel.className='font-label-caps text-label-caps text-tertiary-fixed-dim'; }
    const live = document.getElementById('liveBadge'); if (live) live.classList.add('hidden');
    const subtitle = document.getElementById('subtitleBar'); if (subtitle) subtitle.classList.remove('visible');
    const placeholder = document.getElementById('videoPlaceholder'); if (placeholder) placeholder.classList.remove('hidden');
    const player = document.getElementById('videoPlayer'); if (player) player.classList.add('hidden');
    const phText = document.querySelector('#videoPlaceholder span:last-child'); if (phText) phText.textContent = 'GLOSANDO TEXTO LSE...';
    const logContainer = document.getElementById('emissionLog');
    if (logContainer) {
        logContainer.dataset.renderedCount = '0';
        logContainer.innerHTML = '<div class="text-outline/40 text-xs text-center py-4">Iniciando pipeline Multi-Agente...</div>';
    }
  }

  function playDingDong() {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const playTone = (freq, startTime, duration) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime + startTime);
        gain.gain.setValueAtTime(0, audioCtx.currentTime + startTime);
        gain.gain.linearRampToValueAtTime(0.3, audioCtx.currentTime + startTime + 0.05);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + startTime + duration);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(audioCtx.currentTime + startTime);
        osc.stop(audioCtx.currentTime + startTime + duration);
      };
      playTone(659.25, 0, 0.6); // E5
      playTone(523.25, 0.4, 0.8); // C5
    } catch(e) { console.log('Audio no soportado', e); }
  }

  function showSuccess(texto, videoUrl, whatsappText){
    playDingDong();
    const ls = document.getElementById('loadingSpinner'); if (ls) ls.classList.add('hidden');
    const monitorText = document.getElementById('monitor-text'); if (monitorText){ monitorText.textContent = (texto||'').toUpperCase(); monitorText.style.color = '#ffba27'; monitorText.style.textShadow = '0 0 10px rgba(255,186,39,0.5)'; }
    const statusDot = document.getElementById('statusDot'); if (statusDot) statusDot.className = 'w-2 h-2 rounded-full bg-error pulse-dot';
    const statusLabel = document.getElementById('statusLabel'); if (statusLabel){ statusLabel.textContent='EMITIENDO EN PANTALLAS'; statusLabel.className='font-label-caps text-label-caps text-error'; }
    const live = document.getElementById('liveBadge'); if (live) live.classList.remove('hidden');
    const fb = document.getElementById('customFeedback'); if (fb) fb.classList.add('hidden');
    const player = document.getElementById('videoPlayer');
    if (player && videoUrl){ 
      const safeUrl = (videoUrl||'') + '?t=' + Date.now();
      player.pause();
      player.classList.add('hidden');
      player.onerror = null;
      player.onloadeddata = null;
      player.oncanplay = null;
      player.src = safeUrl;
      player.load();
      player.playbackRate = 1.4; 
      const revealPlayer = () => {
        player.classList.remove('hidden');
        const placeholder = document.getElementById('videoPlaceholder'); if (placeholder) placeholder.classList.add('hidden');
        player.play().catch(() => {});
      };
      player.onloadeddata = revealPlayer;
      player.oncanplay = revealPlayer;
      player.onerror = () => {
        const placeholder = document.getElementById('videoPlaceholder'); if (placeholder) placeholder.classList.remove('hidden');
        showError('No se pudo cargar el vídeo generado.');
      };
      setTimeout(() => { if (!player.classList.contains('hidden')) return; player.play().catch(() => {}); }, 800); 
    }
    const sub = SUBTITLES[window.currentTipo] || '';
    if (sub){ const st = document.getElementById('subtitleText'); if (st) st.textContent = sub; triggerSubtitle(); const playerEl = document.getElementById('videoPlayer'); if (playerEl){ playerEl.removeEventListener('seeked', triggerSubtitle); playerEl.addEventListener('seeked', triggerSubtitle); } }
    else { const subBar = document.getElementById('subtitleBar'); if (subBar) subBar.classList.remove('visible'); const playerEl = document.getElementById('videoPlayer'); if (playerEl) playerEl.removeEventListener('seeked', triggerSubtitle); }
    
    addToLog(texto);
  }

  async function probarDemoLocal(){
    try {
      if (typeof showLoading === 'function') showLoading();
      const res = await fetch('/api/local-demo-video');
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'No se pudo preparar el demo local');
      window.currentTipo = 'cercanias_1';
      showSuccess(data.texto || 'DEMO LOCAL VOZVISIBLE', data.video_url);
    } catch (err) {
      showError(err.message || 'No se pudo cargar el demo local');
    }
  }

  let subtitleTimeout=null, subtitleTimeout2=null;
  function triggerSubtitle(){
    const subBar = document.getElementById('subtitleBar'); if (!subBar) return; subBar.classList.remove('visible'); if (subtitleTimeout) clearTimeout(subtitleTimeout); if (subtitleTimeout2) clearTimeout(subtitleTimeout2);
    subtitleTimeout = setTimeout(()=>{ subBar.classList.add('visible'); }, 1500);
    subtitleTimeout2 = setTimeout(()=>{ subBar.classList.remove('visible'); }, 4500);
  }

  function showError(msg){
    const ls = document.getElementById('loadingSpinner'); if (ls) ls.classList.add('hidden');
    const fb = document.getElementById('customFeedback'); if (fb) fb.classList.add('hidden');
    const ph = document.querySelector('#videoPlaceholder span:last-child'); if (ph) ph.textContent = 'SISTEMA LSE EN ESPERA';
    const monitorText = document.getElementById('monitor-text'); if (monitorText){ monitorText.textContent = '⚠ ' + (msg||'').toUpperCase(); monitorText.style.color = '#ffb4ab'; monitorText.style.textShadow = '0 0 10px rgba(255,180,171,0.3)'; }
    const statusDot = document.getElementById('statusDot'); if (statusDot) statusDot.className='w-2 h-2 rounded-full bg-error';
    const statusLabel = document.getElementById('statusLabel'); if (statusLabel){ statusLabel.textContent='ERROR EN SISTEMA'; statusLabel.className='font-label-caps text-label-caps text-error'; }
  }

  function detenerMegafonia(){
    const player = document.getElementById('videoPlayer'); if (player){ player.pause(); player.classList.add('hidden'); }
    const placeholder = document.getElementById('videoPlaceholder'); if (placeholder) placeholder.classList.remove('hidden');
    const phText = document.querySelector('#videoPlaceholder span:last-child'); if (phText) phText.textContent = 'SISTEMA LSE EN ESPERA';
    const live = document.getElementById('liveBadge'); if (live) live.classList.add('hidden');
    const subBar = document.getElementById('subtitleBar'); if (subBar) subBar.classList.remove('visible');
    const monitorText = document.getElementById('monitor-text'); if (monitorText) { monitorText.textContent = 'MEGAFONÍA DETENIDA. SELECCIONE UN AVISO.'; monitorText.style.color=''; monitorText.style.textShadow=''; }
    const statusDot = document.getElementById('statusDot'); if (statusDot) statusDot.className='w-2 h-2 rounded-full bg-outline';
    const statusLabel = document.getElementById('statusLabel'); if (statusLabel) { statusLabel.textContent='SISTEMA EN ESPERA'; statusLabel.className='font-label-caps text-label-caps text-outline'; }
    document.querySelectorAll('.action-card').forEach(c=>c.classList.remove('card-active'));
  }

  function addToLog(texto){
    const log = document.getElementById('emissionLog'); if (!log) return; const now = new Date().toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
    const entry = document.createElement('div'); entry.className='flex items-center gap-3 text-xs bg-surface-container-lowest/50 rounded-lg px-3 py-2';
    entry.innerHTML = `<span class="w-2 h-2 rounded-full bg-primary-container flex-shrink-0"></span><span class="font-data-point text-xs text-primary-container flex-shrink-0">${now}</span><span class="text-on-surface truncate flex-1">${texto}</span><span class="font-label-caps text-label-caps text-primary-container/60 flex-shrink-0">EMITIDO</span>`;
    if (log.children.length === 1 && log.children[0].textContent.includes('Sin emisiones')) log.innerHTML='';
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
  }

  window.renderAgentLogs = function(logs) {
    const logContainer = document.getElementById('emissionLog');
    if (!logContainer) return;
    
    let renderedCount = logContainer.dataset.renderedCount ? parseInt(logContainer.dataset.renderedCount) : 0;
    
    if (renderedCount === 0 || logs.length < renderedCount) {
        logContainer.innerHTML = '';
        renderedCount = 0;
    }
    
    for (let i = renderedCount; i < logs.length; i++) {
      const l = logs[i];
      let icon = "🤖";
      let color = "text-outline";
      if (l.role === "filtro") { icon = "🧹"; color = "text-[#1DA1F2]"; }
      else if (l.role === "traductor") { icon = "🧠"; color = "text-[#D0BCFF]"; }
      else if (l.role === "critico") { icon = "🕵️"; color = "text-[#F2B8B5]"; }
      else if (l.role === "animador") { icon = "🎬"; color = "text-[#25D366]"; }
      else if (l.role === "error") { icon = "❌"; color = "text-error font-bold"; }
      
      const entry = document.createElement('div');
      entry.className = 'flex items-start gap-2 text-xs bg-surface-container-lowest/50 rounded-lg px-2 py-1.5 border border-outline-variant/10';
      entry.innerHTML = `<span class="flex-shrink-0 text-sm">${icon}</span><span class="${color} break-words flex-1 leading-relaxed type-writer"></span>`;
      logContainer.appendChild(entry);
      
      const span = entry.querySelector('.type-writer');
      let j = 0;
      const text = l.msg;
      function type() {
          if (j < text.length) {
              span.textContent += text.charAt(j);
              j++;
              logContainer.scrollTop = logContainer.scrollHeight;
              setTimeout(type, 15);
          }
      }
      type();
    }
    
    logContainer.dataset.renderedCount = logs.length;
  };


  async function loadAlerts(){
    try{
      const res = await fetch('/api/alerts'); const data = await res.json(); const list = document.getElementById('alertsList');
      const madridAlerts = (data.alerts||[]).filter(a=>a.es_madrid);
      const badge = document.getElementById('alertBadge'); if (badge) badge.textContent = madridAlerts.length;
      const pulse = document.getElementById('alertPulse'); if (pulse) pulse.className = 'w-2 h-2 rounded-full bg-error pulse-dot';
      const ts = data.timestamp ? new Date(parseInt(data.timestamp)*1000) : new Date(); const at = document.getElementById('alertTime'); if (at) at.textContent = ts.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'}) + ' · LIVE';
      if (!madridAlerts || madridAlerts.length===0){ if (list) list.innerHTML = '<div class="text-primary-container/60 text-xs text-center py-3">✅ Sin incidencias activas en Madrid</div>'; return; }
      if (list) list.innerHTML = madridAlerts.slice(0,8).map(a=>`<div class="bg-surface-container-lowest/50 border border-outline-variant/20 rounded-lg px-3 py-2.5 flex flex-col relative group hover:border-error/30 transition"><div class="flex items-center gap-1.5 mb-1 pr-8">${a.lineas.map(l=>`<span class="bg-error/20 text-error text-[10px] font-bold px-1.5 py-0.5 rounded">${l}</span>`).join('')}</div><p class="text-on-surface text-xs font-medium leading-relaxed line-clamp-2 uppercase tracking-wide pr-8">${a.texto.slice(0,180)}${a.texto.length>180?'...':''}</p><div class="absolute top-2 right-2 flex flex-col gap-1"><button onclick="emitirAlerta('${(a.texto.replace(/'/g, "\\'")).slice(0,200)}')" class="bg-primary-container/10 hover:bg-primary-container/30 text-primary-container p-1.5 rounded-lg transition opacity-60 group-hover:opacity-100" title="Emitir en LSE"><span class="material-symbols-outlined text-base">sign_language</span></button></div></div>` ).join('');
    } catch(err){ const list = document.getElementById('alertsList'); if (list) list.innerHTML = '<div class="text-error/60 text-xs text-center py-3">Error de conexión</div>'; }
  }

  async function loadWhatsapp(){
    try{
      const res = await fetch('/api/whatsapp'); 
      const data = await res.json(); 
      const list = document.getElementById('whatsappList');
      if (!data.messages || data.messages.length===0){ if (list) list.innerHTML = '<div class="text-primary-container/60 text-xs text-center py-3">Sin mensajes recientes</div>'; return; }
      if (list) {
          list.innerHTML = data.messages.map(m=>
          `<div class="bg-surface-container-lowest/50 border border-outline-variant/20 rounded-lg px-3 py-2.5 flex flex-col relative group hover:border-[#25D366]/30 transition">
              <button onclick="emitirCustomText('${(m.texto.replace(/'/g, "\\'").replace(/\n/g, " "))}')" class="absolute top-2 right-2 bg-[#25D366]/10 hover:bg-[#25D366]/30 text-[#25D366] p-1.5 rounded-lg transition opacity-60 group-hover:opacity-100" title="Emitir en LSE">
                  <span class="material-symbols-outlined text-base">sign_language</span>
              </button>
              <p class="text-on-surface text-xs font-medium leading-relaxed uppercase tracking-wide whitespace-pre-wrap pr-8">${m.texto}</p>
          </div>`
          ).join('');
      }
    } catch(err){ const list = document.getElementById('whatsappList'); if (list) list.innerHTML = '<div class="text-error/60 text-xs text-center py-3">Error de conexión</div>'; }
  }

  async function loadMetroX(){
    try{
      const res = await fetch('/api/metro_x'); 
      const data = await res.json(); 
      const list = document.getElementById('metroXList');
      if (!data.messages || data.messages.length===0){ if (list) list.innerHTML = '<div class="text-primary-container/60 text-xs text-center py-3">Sin mensajes recientes</div>'; return; }
      if (list) {
          list.innerHTML = data.messages.map(m=>
          `<div class="bg-surface-container-lowest/50 border border-outline-variant/20 rounded-lg px-3 py-2.5 flex flex-col relative group hover:border-[#1DA1F2]/30 transition">
              <button onclick="emitirCustomText('${(m.texto.replace(/'/g, "\\'").replace(/\n/g, " "))}')" class="absolute top-2 right-2 bg-[#1DA1F2]/10 hover:bg-[#1DA1F2]/30 text-[#1DA1F2] p-1.5 rounded-lg transition opacity-60 group-hover:opacity-100" title="Emitir en LSE">
                  <span class="material-symbols-outlined text-base">sign_language</span>
              </button>
              <p class="text-on-surface text-xs font-medium leading-relaxed uppercase tracking-wide whitespace-pre-wrap pr-8">${m.texto}</p>
          </div>`
          ).join('');
      }
    } catch(err){ const list = document.getElementById('metroXList'); if (list) list.innerHTML = '<div class="text-error/60 text-xs text-center py-3">Error de conexión</div>'; }
  }

  // Init
  document.addEventListener('DOMContentLoaded', ()=>{
    const apiEl = document.getElementById('apiKeyInput'); if (apiEl && window.apiKey) apiEl.value = window.apiKey;
    loadAlerts(); setInterval(loadAlerts, 60000);
    loadWhatsapp(); setInterval(loadWhatsapp, 60000);
    loadMetroX(); setInterval(loadMetroX, 60000);
    function updateTime(){ const now = new Date(); const timeEl = document.getElementById('currentTime'); const dateEl = document.getElementById('currentDate'); if (timeEl) timeEl.textContent = now.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit',second:'2-digit'}); if (dateEl) dateEl.textContent = now.toLocaleDateString('es-ES',{day:'2-digit',month:'short',year:'numeric'}); }
    updateTime(); setInterval(updateTime, 1000);
    // attach modal buttons directly to ensure clicks always invoke handlers
    const saveBtn = document.getElementById('apiSaveBtn'); if (saveBtn) saveBtn.addEventListener('click', (e)=>{ e.stopPropagation(); saveApiKey(); });
    const closeBtn = document.getElementById('apiCloseBtn'); if (closeBtn) closeBtn.addEventListener('click', (e)=>{ e.stopPropagation(); document.getElementById('apiModal').classList.add('hidden'); });

    // expose saveApiKey and switchTab and toggleFullscreen globally
    window.saveApiKey = saveApiKey; window.switchTab = switchTab; window.toggleFullscreen = toggleFullscreen; window.showLoading = showLoading; window.showSuccess = showSuccess; window.showError = showError; window.addToLog = addToLog; window.detenerMegafonia = detenerMegafonia; window.triggerSubtitle = triggerSubtitle;
    window.probarDemoLocal = probarDemoLocal;
  });

  // Also expose immediately to ensure handlers bound via onclick attributes work
  window.saveApiKey = saveApiKey; window.switchTab = switchTab; window.toggleFullscreen = toggleFullscreen; window.showLoading = showLoading; window.showSuccess = showSuccess; window.showError = showError; window.addToLog = addToLog; window.detenerMegafonia = detenerMegafonia; window.triggerSubtitle = triggerSubtitle; window.loadAlerts = loadAlerts; window.loadWhatsapp = loadWhatsapp; window.loadMetroX = loadMetroX; window.probarDemoLocal = probarDemoLocal;
  
  window.emitirCustomText = function(texto) {
      const input = document.getElementById('customText');
      if (input) input.value = texto;
      if (typeof window.emitirCustom === 'function') window.emitirCustom();
  };
})();
