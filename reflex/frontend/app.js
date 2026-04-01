// ── State ─────────────────────────────────────────────────────────────────────
const state = {
  recording:      false,
  recordStart:    null,
  timerInterval:  null,
  pendingEvents:  null,
  pendingDuration:null,
  macros:         [],
  selectedMacro:  null,
  playingMacro:   null,
  triggers:       [],
  monitoring:     false,
  pendingRegion:  null,
  pendingColor:   { r: 255, g: 255, b: 255 },
  screenshotData: null,
  keybinds:       { play_stop: '', record: '', monitoring: '' },
  capturingBind:  null,
  undoStack:      [],   // { type:'macro'|'trigger', index, data }
  settings:       { always_on_top: false, countdown_enabled: true },
};

// ── Panel navigation ──────────────────────────────────────────────────────────
function showPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`panel-${name}`).classList.add('active');
  document.querySelector(`[data-panel="${name}"]`).classList.add('active');
  if (name === 'trigger') refreshTriggerMacroSelect();
}

// ── Recording ─────────────────────────────────────────────────────────────────
function toggleRecord() {
  if (state.recording) stopRecord();
  else startRecord();
}

async function startRecord() {
  const res = await pywebview.api.start_recording();
  if (!res.ok) { toast(res.error, 'error'); return; }
  _applyRecordingUI(true);
  sfx('recordStart');
}

function _applyRecordingUI(on) {
  state.recording = on;
  const btn  = document.getElementById('recordBtn');
  const wrap = document.getElementById('recordWrap');
  if (on) {
    state.recordStart = Date.now();
    btn.classList.add('recording');
    wrap.classList.add('recording');
    document.getElementById('recordStatus').textContent = 'Recording…';
    document.getElementById('saveForm').style.display = 'none';
    state.timerInterval = setInterval(updateTimer, 100);
  } else {
    clearInterval(state.timerInterval);
    btn.classList.remove('recording');
    wrap.classList.remove('recording');
  }
}

function updateTimer() {
  const elapsed = (Date.now() - state.recordStart) / 1000;
  const m = Math.floor(elapsed / 60).toString().padStart(2, '0');
  const s = (elapsed % 60).toFixed(1).padStart(4, '0');
  document.getElementById('recordTimer').textContent = `${m}:${s}`;
}

async function stopRecord() {
  const res = await pywebview.api.stop_recording();
  _applyRecordingUI(false);
  if (!res.ok) { toast(res.error, 'error'); return; }
  sfx('recordStop');
  _showStopResult(res);
}

function _showStopResult(res) {
  state.pendingEvents   = res.events;
  state.pendingDuration = res.duration;
  document.getElementById('recordStatus').textContent =
    `${res.event_count} events · ${res.duration}s`;
  document.getElementById('saveForm').style.display = 'flex';
  document.getElementById('macroName').focus();
}

async function saveMacro() {
  const name = document.getElementById('macroName').value.trim();
  if (!name) { toast('Enter a macro name', 'error'); return; }
  const res = await pywebview.api.save_macro(name, state.pendingEvents, state.pendingDuration);
  if (!res.ok) { toast(res.error, 'error'); return; }
  state.macros = res.macros;
  document.getElementById('saveForm').style.display = 'none';
  document.getElementById('macroName').value = '';
  document.getElementById('recordTimer').textContent = '';
  document.getElementById('recordStatus').textContent = 'Click to record';
  renderMacroList();
  sfx('macroSaved');
  toast(`Saved "${name}"`, 'success');
}

function discardRecording() {
  state.pendingEvents = null;
  document.getElementById('saveForm').style.display = 'none';
  document.getElementById('recordTimer').textContent = '';
  document.getElementById('recordStatus').textContent = 'Click to record';
}

// ── Playback ──────────────────────────────────────────────────────────────────
async function playMacro(name) {
  const repeat = parseInt(document.getElementById('repeatCount').value) || 1;
  const macro  = state.macros.find(m => m.name === name);
  const loop   = !!(macro && macro.loop);
  const res = await pywebview.api.play_macro(name, loop ? 0 : repeat);
  if (!res.ok) { toast(res.error, 'error'); return; }
  state.playingMacro = name;
  renderMacroList();
  updatePlaybackBtn();
  if (!state.settings.countdown_enabled) {
    sfx('playbackStart');
    toast(`Playing "${name}" ${loop ? '∞ loop' : '×' + repeat}`, 'success');
  }
}

async function togglePlayback() {
  if (state.playingMacro) {
    await stopPlayback();
  } else {
    const name = state.selectedMacro || (state.macros[0] && state.macros[0].name);
    if (name) playMacro(name);
    else toast('No macro selected', 'error');
  }
}

async function stopPlayback() {
  await pywebview.api.stop_playback();
  state.playingMacro = null;
  renderMacroList();
  updatePlaybackBtn();
  hideCountdown();
  sfx('playbackStop');
  toast('Playback stopped');
}

function updatePlaybackBtn() {
  const btn = document.getElementById('playbackBtn');
  if (!btn) return;
  if (state.playingMacro) {
    btn.textContent = 'Stop Playback';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-ghost');
  } else {
    btn.textContent = 'Start Playback';
    btn.classList.remove('btn-ghost');
    btn.classList.add('btn-primary');
  }
}

// ── Countdown overlay ─────────────────────────────────────────────────────────
window.onPlaybackCountdown = function(n) {
  const overlay = document.getElementById('countdownOverlay');
  if (n === 0) {
    hideCountdown();
    sfx('countdownGo');
    sfx('playbackStart');
    const name   = state.playingMacro;
    const macro  = name && state.macros.find(m => m.name === name);
    const loop   = !!(macro && macro.loop);
    const repeat = parseInt(document.getElementById('repeatCount').value) || 1;
    if (name) toast(`Playing "${name}" ${loop ? '∞ loop' : '×' + repeat}`, 'success');
  } else {
    sfx('countdownTick', n);
    document.getElementById('countdownNum').textContent = n;
    overlay.style.display = 'flex';
  }
};

function hideCountdown() {
  document.getElementById('countdownOverlay').style.display = 'none';
}

window.onPlaybackComplete = function() {
  state.playingMacro = null;
  renderMacroList();
  updatePlaybackBtn();
  hideCountdown();
  sfx('playbackStop');
  toast('Playback complete', 'success');
};

window.onColorTrigger = function(macroName) {
  sfx('triggerFired');
  toast(`Trigger fired: "${macroName}"`, 'success');
};

window.onMonitorExhausted = function() {
  state.monitoring = false;
  updateMonitorUI();
  toast('All triggers fired — monitoring stopped', 'success');
};

// ── Hotkey JS callbacks ───────────────────────────────────────────────────────
window.hotkeyPlayStop = function() {
  if (state.playingMacro) {
    stopPlayback();
  } else {
    const name = state.selectedMacro || (state.macros[0] && state.macros[0].name);
    if (name) playMacro(name);
    else toast('No macro selected', 'error');
  }
};

window.hotkeyStartRecord = function() {
  if (state.recording) return;
  _applyRecordingUI(true);
  sfx('recordStart');
  toast('Recording started (hotkey)', 'success');
};

window.hotkeyStopRecord = function(result) {
  if (!state.recording) return;
  _applyRecordingUI(false);
  sfx('recordStop');
  _showStopResult(result);
  toast('Recording stopped (hotkey)', 'success');
};

window.hotkeyMonitoring = function() {
  toggleMonitoring();
};

window.hotkeyRecordCrashed = function() {
  _applyRecordingUI(false);
  document.getElementById('recordStatus').textContent = 'Click to record';
  toast('Recorder crashed — please re-launch', 'error');
};

// ── Macro List ────────────────────────────────────────────────────────────────
function renderMacroList() {
  const query = (document.getElementById('macroSearch')?.value || '').toLowerCase();
  const list  = document.getElementById('macroList');
  const empty = document.getElementById('macroEmpty');
  list.innerHTML = '';

  const filtered = state.macros.filter(m => m.name.toLowerCase().includes(query));
  document.getElementById('macroCount').textContent =
    query ? `${filtered.length}/${state.macros.length}` : state.macros.length;

  if (state.macros.length === 0) {
    list.style.display  = 'none';
    empty.style.display = 'flex';
  } else {
    list.style.display  = 'flex';
    empty.style.display = 'none';
  }

  filtered.forEach(m => {
    const div = document.createElement('div');
    div.className = 'macro-item';
    if (m.name === state.selectedMacro) div.classList.add('selected');
    if (m.name === state.playingMacro)  div.classList.add('playing');
    div.innerHTML = `
      <div class="macro-name">${escHtml(m.name)}</div>
      <div class="macro-meta">${m.event_count} events · ${m.duration}s</div>
      <label class="loop-label" onclick="event.stopPropagation()">
        <input type="checkbox" class="loop-check" ${m.loop ? 'checked' : ''}
               onchange="setMacroLoop('${escJs(m.name)}', this.checked)" />
        Loop
      </label>
      <button class="item-play" onclick="event.stopPropagation();playMacro('${escJs(m.name)}')" title="Play">▶</button>
      <button class="item-delete" onclick="event.stopPropagation();deleteMacro('${escJs(m.name)}')" title="Delete">×</button>
    `;

    let clickTimer = null;
    div.addEventListener('click', () => {
      clearTimeout(clickTimer);
      clickTimer = setTimeout(() => {
        state.selectedMacro = (state.selectedMacro === m.name) ? null : m.name;
        renderMacroList();
      }, 220);
    });

    div.addEventListener('dblclick', e => {
      if (e.target.closest('button, label, input')) return;
      clearTimeout(clickTimer);
      const nameEl = div.querySelector('.macro-name');
      startRename(nameEl, m.name);
    });

    list.appendChild(div);
  });
}

// ── Inline rename ─────────────────────────────────────────────────────────────
function startRename(nameEl, oldName) {
  event.stopPropagation();
  const input = document.createElement('input');
  input.className = 'macro-name-input';
  input.value = oldName;
  nameEl.replaceWith(input);
  input.focus();
  input.select();

  async function commit() {
    const newName = input.value.trim();
    if (!newName || newName === oldName) {
      const restored = document.createElement('div');
      restored.className = 'macro-name';
      restored.textContent = oldName;
      input.replaceWith(restored);
      return;
    }
    const res = await pywebview.api.rename_macro(oldName, newName);
    if (!res.ok) {
      toast(res.error, 'error');
      const restored = document.createElement('div');
      restored.className = 'macro-name';
      restored.textContent = oldName;
      input.replaceWith(restored);
      return;
    }
    if (state.selectedMacro === oldName) state.selectedMacro = newName;
    if (state.playingMacro  === oldName) state.playingMacro  = newName;
    if (state.loopMacros[oldName]) {
      state.loopMacros[newName] = true;
      delete state.loopMacros[oldName];
    }
    state.macros = res.macros;
    renderMacroList();
    toast(`Renamed to "${newName}"`, 'success');
  }

  input.addEventListener('blur', commit);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter')  { e.preventDefault(); input.blur(); }
    if (e.key === 'Escape') { input.value = oldName; input.blur(); }
  });
}

// ── Delete / Undo ─────────────────────────────────────────────────────────────
async function deleteMacro(name) {
  const idx = state.macros.findIndex(m => m.name === name);
  if (idx === -1) return;
  state.undoStack.push({ type: 'macro', index: idx, data: state.macros[idx] });
  const res = await pywebview.api.delete_macro(name);
  state.macros = res.macros;
  if (res.triggers !== undefined) {
    state.triggers = res.triggers;
    renderTriggerList();
  }
  if (state.selectedMacro === name) state.selectedMacro = null;
  renderMacroList();
  toast(`Deleted "${name}" — ⌘Z to undo`);
}

async function undoDelete() {
  if (!state.undoStack.length) return;
  const entry = state.undoStack.pop();

  if (entry.type === 'macro') {
    const res = await pywebview.api.restore_macro(entry.data, entry.index);
    if (!res.ok) { toast('Could not restore macro', 'error'); return; }
    state.macros = res.macros;
    renderMacroList();
    toast(`Restored "${entry.data.name}"`, 'success');
  } else if (entry.type === 'trigger') {
    const res = await pywebview.api.restore_trigger(entry.data, entry.index);
    if (!res.ok) { toast('Could not restore trigger', 'error'); return; }
    state.triggers = res.triggers;
    renderTriggerList();
    toast('Trigger restored', 'success');
  }
}

async function setMacroLoop(name, on) {
  const macro = state.macros.find(m => m.name === name);
  if (macro) macro.loop = !!on;
  await pywebview.api.set_macro_loop(name, on);
}

// ── File I/O ──────────────────────────────────────────────────────────────────
async function saveToFile() {
  const res = await pywebview.api.save_to_file(state.selectedMacro || '');
  if (res.ok) {
    const label = state.selectedMacro ? `"${state.selectedMacro}"` : 'all macros';
    toast(`Saved ${label} to file`, 'success');
  } else if (res.error !== 'Cancelled') {
    toast(res.error, 'error');
  }
}

async function loadFromFile() {
  const res = await pywebview.api.load_from_file();
  if (!res.ok) { if (res.error !== 'Cancelled') toast(res.error, 'error'); return; }
  state.macros   = res.macros;
  state.triggers = res.triggers || [];
  renderMacroList();
  renderTriggerList();
  const mc = res.imported_macros   ?? 0;
  const tc = res.imported_triggers ?? 0;
  const skipped = res.skipped_macros ?? 0;
  let msg = `Imported ${mc} macro${mc !== 1 ? 's' : ''}, ${tc} trigger${tc !== 1 ? 's' : ''}`;
  if (skipped > 0) msg += ` · ${skipped} skipped (name conflict)`;
  toast(msg, 'success');
}

// ── Monitoring ────────────────────────────────────────────────────────────────
async function toggleMonitoring() {
  if (state.monitoring) {
    await pywebview.api.stop_monitoring();
    state.monitoring = false;
  } else {
    await pywebview.api.start_monitoring();
    state.monitoring = true;
  }
  updateMonitorUI();
}

function updateMonitorUI() {
  const dot   = document.getElementById('statusDot');
  const label = document.getElementById('statusLabel');
  const btn   = document.getElementById('monitorToggle');
  if (state.monitoring) {
    dot.classList.add('active');
    label.textContent = 'Monitoring On';
    btn.textContent   = 'Disable';
    btn.classList.add('active');
  } else {
    dot.classList.remove('active');
    label.textContent = 'Monitoring Off';
    btn.textContent   = 'Enable';
    btn.classList.remove('active');
  }
}

// ── Trigger Form ──────────────────────────────────────────────────────────────
let _editingTriggerIndex = null;

function showAddTrigger() {
  _editingTriggerIndex = null;
  refreshTriggerMacroSelect();
  document.getElementById('triggerMacroRow').style.display   = '';
  document.getElementById('triggerEditInfo').style.display   = 'none';
  document.getElementById('triggerCaptureRow').style.display = '';
  document.getElementById('triggerSaveBtn').textContent = 'Save Trigger';
  document.getElementById('triggerForm').style.display = 'block';
  state.pendingRegion = null;
  state.pendingColor  = { r: 255, g: 255, b: 255 };
  document.getElementById('regionDisplay').style.display = 'none';
  document.getElementById('capturedPreview').style.background = '#555';
  document.getElementById('colorPicker').value  = '#ffffff';
  document.getElementById('colorPreview').style.background = '#ffffff';
  document.getElementById('triggerLoop').checked = false;
}

function showEditTrigger(index) {
  const t = state.triggers[index];
  if (!t) return;
  _editingTriggerIndex = index;
  document.getElementById('triggerMacroRow').style.display   = 'none';
  document.getElementById('triggerCaptureRow').style.display = 'none';
  document.getElementById('regionDisplay').style.display     = 'none';
  document.getElementById('triggerEditInfo').style.display   = '';
  document.getElementById('triggerEditLabel').textContent =
    `${t.macro_name} · (${t.region.x},${t.region.y}) ${t.region.w}×${t.region.h}px`;
  document.getElementById('triggerSaveBtn').textContent = 'Update Trigger';
  const hex = rgbToHex(t.color.r, t.color.g, t.color.b);
  state.pendingColor = { ...t.color };
  document.getElementById('colorPicker').value = hex;
  document.getElementById('colorPreview').style.background = hex;
  document.getElementById('capturedPreview').style.background = '#555';
  document.getElementById('triggerLoop').checked = !!t.loop;
  document.getElementById('triggerForm').style.display = 'block';
}

function cancelTrigger() {
  document.getElementById('triggerForm').style.display = 'none';
  state.pendingRegion = null;
  _editingTriggerIndex = null;
}

function refreshTriggerMacroSelect() {
  const sel = document.getElementById('triggerMacro');
  sel.innerHTML = state.macros.length
    ? state.macros.map(m => `<option value="${escHtml(m.name)}">${escHtml(m.name)}</option>`).join('')
    : '<option value="">No macros saved</option>';
}

async function captureScreen() {
  toast('Capturing screen…');
  const res = await pywebview.api.capture_screen();
  if (!res.ok) { toast(res.error, 'error'); return; }
  showScreenshotOverlay(res.image, res.width, res.height);
}

function onColorPick(hex) {
  const r = parseInt(hex.slice(1,3),16);
  const g = parseInt(hex.slice(3,5),16);
  const b = parseInt(hex.slice(5,7),16);
  state.pendingColor = {r,g,b};
  document.getElementById('colorPreview').style.background = hex;
}

async function saveTrigger() {
  const loop = document.getElementById('triggerLoop').checked;

  if (_editingTriggerIndex !== null) {
    const res = await pywebview.api.update_trigger(
      _editingTriggerIndex, state.pendingColor, loop);
    if (!res.ok) { toast(res.error, 'error'); return; }
    state.triggers = res.triggers;
    cancelTrigger();
    renderTriggerList();
    toast('Trigger updated', 'success');
    return;
  }

  const macroName = document.getElementById('triggerMacro').value;
  if (!macroName) { toast('Select a macro', 'error'); return; }
  if (!state.pendingRegion) { toast('Select a screen region first', 'error'); return; }
  const tolerance = parseInt(document.getElementById('toleranceSlider').value);
  const res = await pywebview.api.add_trigger(
    macroName, state.pendingRegion, state.pendingColor, tolerance, loop);
  if (!res.ok) { toast(res.error, 'error'); return; }
  state.triggers = res.triggers;
  cancelTrigger();
  renderTriggerList();
  toast('Trigger saved', 'success');
}

// ── Trigger List ──────────────────────────────────────────────────────────────
function renderTriggerList() {
  const query = (document.getElementById('triggerSearch')?.value || '').toLowerCase();
  const list  = document.getElementById('triggerList');
  const empty = document.getElementById('triggerEmpty');
  document.getElementById('triggerCount').textContent = state.triggers.length;
  list.innerHTML = '';

  const filtered = state.triggers.filter(t =>
    t.macro_name.toLowerCase().includes(query));

  if (state.triggers.length === 0) {
    list.style.display  = 'none';
    empty.style.display = 'flex';
  } else {
    list.style.display  = 'flex';
    empty.style.display = 'none';
  }

  filtered.forEach((t, i) => {
    const hex = rgbToHex(t.color.r, t.color.g, t.color.b);
    const div = document.createElement('div');
    div.className = 'trigger-item';
    div.style.cursor = 'pointer';
    div.innerHTML = `
      <div class="trigger-color-dot" style="background:${hex}"></div>
      <div style="flex:1">
        <div class="trigger-name">${escHtml(t.macro_name)}</div>
        <div class="trigger-meta">Region (${t.region.x},${t.region.y}) ${t.region.w}×${t.region.h} · tol ${t.tolerance}</div>
      </div>
      ${t.loop ? '<span class="trigger-loop-badge">Loop</span>' : ''}
      <button class="item-delete" onclick="event.stopPropagation();deleteTrigger(${i})" title="Delete">×</button>
    `;
    div.addEventListener('click', () => showEditTrigger(i));
    list.appendChild(div);
  });
}

async function deleteTrigger(index) {
  state.undoStack.push({ type: 'trigger', index, data: state.triggers[index] });
  const res = await pywebview.api.remove_trigger(index);
  state.triggers = res.triggers;
  renderTriggerList();
  toast('Trigger deleted — ⌘Z to undo');
}

// ── Trigger File I/O ──────────────────────────────────────────────────────────
async function saveTriggersToFile() {
  const res = await pywebview.api.save_triggers_to_file();
  if (res.ok) toast('Triggers saved to file', 'success');
  else if (res.error !== 'Cancelled') toast(res.error, 'error');
}

async function loadTriggersFromFile() {
  const res = await pywebview.api.load_triggers_from_file();
  if (!res.ok) { if (res.error !== 'Cancelled') toast(res.error, 'error'); return; }
  state.triggers = res.triggers;
  renderTriggerList();
  const n = res.imported ?? 0;
  toast(`Imported ${n} trigger${n !== 1 ? 's' : ''}`, 'success');
}

// ── Screenshot Overlay ────────────────────────────────────────────────────────
let overlayCtx, overlayImg, dragStart = null, dragRect = null;

function showScreenshotOverlay(b64, imgW, imgH) {
  state.screenshotData = { b64, imgW, imgH };
  const overlay = document.getElementById('screenshotOverlay');
  const canvas  = document.getElementById('screenshotCanvas');
  canvas.width  = window.innerWidth;
  canvas.height = window.innerHeight;
  overlayCtx = canvas.getContext('2d');
  const img = new Image();
  img.onload = () => {
    overlayImg = img;
    drawOverlay(null);
    overlay.style.display = 'block';
  };
  img.src = 'data:image/png;base64,' + b64;
  canvas.onmousedown = overlayMouseDown;
  canvas.onmousemove = overlayMouseMove;
  canvas.onmouseup   = overlayMouseUp;
}

function hideScreenshotOverlay() {
  document.getElementById('screenshotOverlay').style.display = 'none';
  dragStart = null;
  dragRect  = null;
}

function drawOverlay(rect) {
  const c  = overlayCtx;
  const cw = c.canvas.width, ch = c.canvas.height;
  c.clearRect(0, 0, cw, ch);
  c.drawImage(overlayImg, 0, 0, cw, ch);
  c.fillStyle = 'rgba(6,10,16,0.65)';
  if (rect) {
    const {x,y,w,h} = rect;
    c.fillRect(0, 0, cw, y);
    c.fillRect(0, y+h, cw, ch-(y+h));
    c.fillRect(0, y, x, h);
    c.fillRect(x+w, y, cw-(x+w), h);
    c.strokeStyle = '#3b82f6';
    c.lineWidth   = 2;
    c.strokeRect(x, y, w, h);
  } else {
    c.fillRect(0, 0, cw, ch);
  }
}

function overlayMouseDown(e) { dragStart = { x: e.offsetX, y: e.offsetY }; dragRect = null; }
function overlayMouseMove(e) {
  if (!dragStart) return;
  dragRect = { x: Math.min(dragStart.x, e.offsetX), y: Math.min(dragStart.y, e.offsetY),
               w: Math.abs(e.offsetX - dragStart.x), h: Math.abs(e.offsetY - dragStart.y) };
  drawOverlay(dragRect);
}
function overlayMouseUp(e) {
  if (!dragStart) return;
  const x = Math.min(dragStart.x, e.offsetX), y = Math.min(dragStart.y, e.offsetY);
  const w = Math.abs(e.offsetX - dragStart.x), h = Math.abs(e.offsetY - dragStart.y);
  dragStart = null;
  if (w < 4 || h < 4) { dragRect = null; return; }
  dragRect = {x,y,w,h};
  drawOverlay(dragRect);
  const cw = overlayCtx.canvas.width, ch = overlayCtx.canvas.height;
  const { imgW, imgH } = state.screenshotData;
  state.pendingRegion = {
    x: Math.round(x * imgW/cw), y: Math.round(y * imgH/ch),
    w: Math.round(w * imgW/cw), h: Math.round(h * imgH/ch),
  };
  const imgData = overlayCtx.getImageData(x, y, w, h);
  let r=0, g=0, b=0;
  const n = imgData.data.length/4;
  for (let i=0; i<imgData.data.length; i+=4) { r+=imgData.data[i]; g+=imgData.data[i+1]; b+=imgData.data[i+2]; }
  r=Math.round(r/n); g=Math.round(g/n); b=Math.round(b/n);
  document.getElementById('capturedPreview').style.background = rgbToHex(r, g, b);
  document.getElementById('regionText').textContent =
    `(${state.pendingRegion.x}, ${state.pendingRegion.y}) ${state.pendingRegion.w}×${state.pendingRegion.h}px`;
  document.getElementById('regionDisplay').style.display = 'flex';
  hideScreenshotOverlay();
}

// ── Sound ─────────────────────────────────────────────────────────────────────
function sfx(name, ...args) {
  if (!state.settings.sounds_enabled) return;
  if (name === 'triggerFired' && !state.settings.trigger_sound_enabled) return;
  try { SFX[name] && SFX[name](...args); } catch(e) {}
}

// ── Options ───────────────────────────────────────────────────────────────────
async function setSetting(key, value) {
  state.settings[key] = value;
  await pywebview.api.set_settings(state.settings);
}

function onSoundsToggle(enabled) {
  setSetting('sounds_enabled', enabled);
  const row = document.getElementById('opt-trigger-sound-row');
  row.classList.toggle('disabled', !enabled);
  document.getElementById('opt-trigger-sound').disabled = !enabled;
}

function applySettingsToUI() {
  document.getElementById('opt-always-on-top').checked  = !!state.settings.always_on_top;
  document.getElementById('opt-countdown').checked      = state.settings.countdown_enabled !== false;
  const soundsOn = state.settings.sounds_enabled !== false;
  document.getElementById('opt-sounds').checked         = soundsOn;
  document.getElementById('opt-trigger-sound').checked  = state.settings.trigger_sound_enabled !== false;
  const row = document.getElementById('opt-trigger-sound-row');
  row.classList.toggle('disabled', !soundsOn);
  document.getElementById('opt-trigger-sound').disabled = !soundsOn;
}

function showClearConfirm() {
  document.getElementById('confirmOverlay').style.display = 'flex';
}

function hideClearConfirm() {
  document.getElementById('confirmOverlay').style.display = 'none';
}

async function clearAllData() {
  hideClearConfirm();
  await pywebview.api.clear_all_data();
  state.macros        = [];
  state.triggers      = [];
  state.undoStack     = [];
  state.selectedMacro = null;
  state.playingMacro  = null;
  state.settings      = { always_on_top: false, countdown_enabled: true };
  state.keybinds      = { play_stop: '', record: '', monitoring: '' };
  renderMacroList();
  renderTriggerList();
  applySettingsToUI();
  // Reset keybind chips
  for (const action of ['play_stop', 'record', 'monitoring']) {
    const el = document.getElementById(`kb-${action.replace(/_/g, '-')}`);
    if (el) { el.textContent = '—'; el.classList.add('none'); }
  }
  toast('All data cleared', 'success');
}

// ── Keybind capture ───────────────────────────────────────────────────────────
function keyEventToPynput(e) {
  const specialMap = {
    'F1':['Key.f1','F1'],  'F2':['Key.f2','F2'],  'F3':['Key.f3','F3'],
    'F4':['Key.f4','F4'],  'F5':['Key.f5','F5'],  'F6':['Key.f6','F6'],
    'F7':['Key.f7','F7'],  'F8':['Key.f8','F8'],  'F9':['Key.f9','F9'],
    'F10':['Key.f10','F10'], 'F11':['Key.f11','F11'], 'F12':['Key.f12','F12'],
    'Control':['Key.ctrl','Ctrl'], 'Alt':['Key.alt','Alt'],
    'Shift':['Key.shift','Shift'], 'Meta':['Key.cmd','⌘'],
    'Tab':['Key.tab','Tab'], 'Backspace':['Key.backspace','Bksp'],
    'Delete':['Key.delete','Del'], 'Home':['Key.home','Home'],
    'End':['Key.end','End'], 'PageUp':['Key.page_up','PgUp'],
    'PageDown':['Key.page_down','PgDn'],
    'ArrowUp':['Key.up','↑'], 'ArrowDown':['Key.down','↓'],
    'ArrowLeft':['Key.left','←'], 'ArrowRight':['Key.right','→'],
    'Enter':['Key.enter','Enter'], ' ':['Key.space','Space'],
  };
  if (e.key in specialMap) return { pyKey: specialMap[e.key][0], display: specialMap[e.key][1] };
  if (e.key.length === 1)  return { pyKey: e.key.toLowerCase(), display: e.key.toUpperCase() };
  return { pyKey: null, display: null };
}

function pyKeyToDisplay(k) {
  if (!k) return 'None';
  const map = {
    'Key.f1':'F1',  'Key.f2':'F2',  'Key.f3':'F3',  'Key.f4':'F4',
    'Key.f5':'F5',  'Key.f6':'F6',  'Key.f7':'F7',  'Key.f8':'F8',
    'Key.f9':'F9',  'Key.f10':'F10','Key.f11':'F11','Key.f12':'F12',
    'Key.ctrl':'Ctrl', 'Key.alt':'Alt', 'Key.shift':'Shift', 'Key.cmd':'⌘',
    'Key.tab':'Tab',   'Key.backspace':'Bksp', 'Key.delete':'Del',
    'Key.home':'Home', 'Key.end':'End',
    'Key.page_up':'PgUp', 'Key.page_down':'PgDn',
    'Key.up':'↑', 'Key.down':'↓', 'Key.left':'←', 'Key.right':'→',
    'Key.enter':'Enter', 'Key.esc':'Esc', 'Key.space':'Space',
  };
  if (k in map) return map[k];
  if (k.length === 1) return k.toUpperCase();
  return k;
}

function armKeybind(action) {
  if (state.capturingBind) cancelCapture();
  state.capturingBind = action;
  const el = document.getElementById(`kb-${action.replace(/_/g, '-')}`);
  el.textContent = '…';
  el.classList.add('capturing');
  document.getElementById('keybindHint').style.display = 'block';
}

function cancelCapture() {
  if (!state.capturingBind) return;
  const el = document.getElementById(`kb-${state.capturingBind.replace(/_/g, '-')}`);
  el.classList.remove('capturing');
  el.textContent = pyKeyToDisplay(state.keybinds[state.capturingBind]) || 'None';
  _updateNoneStyle(state.capturingBind);
  state.capturingBind = null;
  document.getElementById('keybindHint').style.display = 'none';
}

function _updateNoneStyle(action) {
  const el = document.getElementById(`kb-${action.replace(/_/g, '-')}`);
  if (!el) return;
  if (!state.keybinds[action]) el.classList.add('none');
  else                          el.classList.remove('none');
}

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    if (document.getElementById('screenshotOverlay').style.display !== 'none') {
      hideScreenshotOverlay(); return;
    }
    if (document.getElementById('confirmOverlay').style.display !== 'none') {
      hideClearConfirm(); return;
    }
  }

  if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !state.capturingBind) {
    e.preventDefault();
    undoDelete();
    return;
  }

  if (state.capturingBind) {
    e.preventDefault();
    e.stopPropagation();
    if (e.key === 'Escape') { cancelCapture(); return; }
    if (e.key === 'Backspace' || e.key === 'Delete') {
      const action = state.capturingBind;
      state.keybinds[action] = '';
      const el = document.getElementById(`kb-${action.replace(/_/g, '-')}`);
      el.textContent = 'None';
      el.classList.remove('capturing');
      el.classList.add('none');
      document.getElementById('keybindHint').style.display = 'none';
      state.capturingBind = null;
      pywebview.api.set_keybinds(state.keybinds);
      toast('Hotkey cleared', 'success');
      return;
    }
    const { pyKey, display } = keyEventToPynput(e);
    if (!pyKey) return;
    const action = state.capturingBind;
    state.keybinds[action] = pyKey;
    const el = document.getElementById(`kb-${action.replace(/_/g, '-')}`);
    el.textContent = display;
    el.classList.remove('capturing');
    _updateNoneStyle(action);
    document.getElementById('keybindHint').style.display = 'none';
    state.capturingBind = null;
    pywebview.api.set_keybinds(state.keybinds);
    sfx('keybindSet');
    toast(`Hotkey set to ${display}`, 'success');
  }
}, true);

document.addEventListener('mousedown', e => {
  if (!state.capturingBind) return;
  const ids = ['kb-play-stop', 'kb-record', 'kb-monitoring'];
  if (!ids.includes(e.target.id)) cancelCapture();
});

// ── Helpers ───────────────────────────────────────────────────────────────────
function rgbToHex(r,g,b) {
  return '#' + [r,g,b].map(v => v.toString(16).padStart(2,'0')).join('');
}
function escHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escJs(s) {
  return String(s).replace(/\\/g,'\\\\').replace(/'/g,"\\'");
}
function toast(msg, type='') {
  const c = document.getElementById('toastContainer');
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  c.appendChild(t);
  setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, 3000);
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
  const macRes = await pywebview.api.get_macros();
  if (macRes.ok) { state.macros = macRes.macros; renderMacroList(); }

  const tRes = await pywebview.api.get_triggers();
  if (tRes.ok) { state.triggers = tRes.triggers; renderTriggerList(); }

  const mRes = await pywebview.api.is_monitoring();
  if (mRes.ok && mRes.monitoring) { state.monitoring = true; updateMonitorUI(); }

  const kRes = await pywebview.api.get_keybinds();
  if (kRes.ok) {
    state.keybinds = kRes.keybinds;
    for (const [action, pyKey] of Object.entries(state.keybinds)) {
      const el = document.getElementById(`kb-${action.replace(/_/g, '-')}`);
      if (el) { el.textContent = pyKeyToDisplay(pyKey) || 'None'; _updateNoneStyle(action); }
    }
  }

  const sRes = await pywebview.api.get_settings();
  if (sRes.ok) { state.settings = sRes.settings; applySettingsToUI(); }
}

// ── Global UI click sound ─────────────────────────────────────────────────────
document.addEventListener('click', e => {
  const el = e.target.closest('button, .nav-btn, .keybind-input, .monitor-toggle, input[type="checkbox"], .item-play, .item-delete, .loop-label');
  if (el) sfx('uiClick');
}, true);

window.addEventListener('pywebviewready', init);
