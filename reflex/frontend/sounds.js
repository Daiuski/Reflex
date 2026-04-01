// ── Reflex Sound Engine (Web Audio API — no external files) ───────────────────
const SFX = (() => {
  let _ctx = null;
  function ctx() {
    if (!_ctx) _ctx = new (window.AudioContext || window.webkitAudioContext)();
    return _ctx;
  }

  // Low-level helpers
  function tone(freq, type, startTime, duration, gainPeak, ac) {
    const osc  = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.type = type;
    osc.frequency.setValueAtTime(freq, startTime);
    gain.gain.setValueAtTime(0, startTime);
    gain.gain.linearRampToValueAtTime(gainPeak, startTime + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
    osc.start(startTime);
    osc.stop(startTime + duration + 0.02);
  }

  function sweep(freqFrom, freqTo, type, startTime, duration, gainPeak, ac) {
    const osc  = ac.createOscillator();
    const gain = ac.createGain();
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.type = type;
    osc.frequency.setValueAtTime(freqFrom, startTime);
    osc.frequency.exponentialRampToValueAtTime(freqTo, startTime + duration);
    gain.gain.setValueAtTime(gainPeak, startTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
    osc.start(startTime);
    osc.stop(startTime + duration + 0.02);
  }

  function noise(startTime, duration, gainPeak, ac) {
    const bufSize = ac.sampleRate * duration;
    const buf     = ac.createBuffer(1, bufSize, ac.sampleRate);
    const data    = buf.getChannelData(0);
    for (let i = 0; i < bufSize; i++) data[i] = Math.random() * 2 - 1;
    const src  = ac.createBufferSource();
    const gain = ac.createGain();
    const fil  = ac.createBiquadFilter();
    src.buffer = buf;
    fil.type   = 'bandpass';
    fil.frequency.value = 2000;
    fil.Q.value = 0.5;
    src.connect(fil); fil.connect(gain); gain.connect(ac.destination);
    gain.gain.setValueAtTime(gainPeak, startTime);
    gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
    src.start(startTime);
    src.stop(startTime + duration + 0.02);
  }

  // ── Public sounds ─────────────────────────────────────────────────────────

  return {
    // Countdown tick (3, 2, 1) — descending woody click
    countdownTick(n) {
      const ac = ctx();
      const t  = ac.currentTime;
      const freq = 500 - (3 - n) * 60;   // 500, 440, 380
      tone(freq, 'sine', t, 0.08, 0.25, ac);
      noise(t, 0.04, 0.08, ac);
    },

    // Countdown go (0) — bright ascending sweep
    countdownGo() {
      const ac = ctx();
      const t  = ac.currentTime;
      sweep(300, 900, 'sine', t, 0.18, 0.3, ac);
      sweep(600, 1200, 'triangle', t + 0.05, 0.15, 0.15, ac);
    },

    // Recording start — two quick ascending beeps
    recordStart() {
      const ac = ctx();
      const t  = ac.currentTime;
      tone(600, 'sine', t,        0.1, 0.2, ac);
      tone(900, 'sine', t + 0.12, 0.1, 0.2, ac);
    },

    // Recording stop — two quick descending beeps
    recordStop() {
      const ac = ctx();
      const t  = ac.currentTime;
      tone(900, 'sine', t,        0.1, 0.2, ac);
      tone(600, 'sine', t + 0.12, 0.1, 0.2, ac);
    },

    // Keybind captured — soft, satisfying click
    keybindSet() {
      const ac = ctx();
      const t  = ac.currentTime;
      noise(t, 0.04, 0.12, ac);
      tone(1200, 'sine', t, 0.06, 0.1, ac);
    },

    // Playback start — short upward blip
    playbackStart() {
      const ac = ctx();
      sweep(400, 700, 'sine', ac.currentTime, 0.12, 0.2, ac);
    },

    // Playback stop — short downward blip
    playbackStop() {
      const ac = ctx();
      sweep(700, 300, 'sine', ac.currentTime, 0.12, 0.18, ac);
    },

    // Trigger fired — distinct chime (two harmonics)
    triggerFired() {
      const ac = ctx();
      const t  = ac.currentTime;
      tone(880,  'sine',     t,       0.4, 0.22, ac);
      tone(1320, 'triangle', t,       0.3, 0.12, ac);
      tone(660,  'sine',     t + 0.1, 0.25, 0.1, ac);
    },

    // UI element click — very subtle tick
    uiClick() {
      const ac = ctx();
      const t  = ac.currentTime;
      noise(t, 0.025, 0.055, ac);
      tone(1800, 'sine', t, 0.02, 0.04, ac);
    },

    // Macro saved — cheerful confirm
    macroSaved() {
      const ac = ctx();
      const t  = ac.currentTime;
      tone(523, 'sine', t,        0.1, 0.18, ac);
      tone(659, 'sine', t + 0.08, 0.1, 0.18, ac);
      tone(784, 'sine', t + 0.16, 0.15, 0.2, ac);
    },
  };
})();
