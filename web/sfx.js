// 8-bit sound effects synthesised on the fly with WebAudio. No audio files.
const Sfx = (() => {
  let ctx = null;
  let muted = false;
  try { muted = localStorage.getItem("fd-muted") === "1"; } catch {}

  // iOS only allows audio after a user gesture, so the context is created on the first tap.
  function unlock() {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (AC) ctx = new AC();
    }
    if (ctx && ctx.state === "suspended") ctx.resume();
  }
  document.addEventListener("pointerdown", unlock, { capture: true });

  function tone(freq, start, dur, { type = "square", vol = 0.06, slide = 0 } = {}) {
    if (muted || !ctx) return;
    const t = ctx.currentTime + start;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t);
    if (slide) osc.frequency.linearRampToValueAtTime(freq + slide, t + dur);
    gain.gain.setValueAtTime(vol, t);
    gain.gain.setValueAtTime(vol, t + dur * 0.7);
    gain.gain.linearRampToValueAtTime(0, t + dur);
    osc.connect(gain).connect(ctx.destination);
    osc.start(t);
    osc.stop(t + dur + 0.02);
  }

  const notes = (seq, step, opts) => seq.forEach((f, i) => f && tone(f, i * step, step * 0.95, opts));

  return {
    tap: () => tone(660, 0, 0.04, { vol: 0.04 }),
    tick: () => tone(1320, 0, 0.025, { vol: 0.03 }),
    type: () => tone(520 + Math.random() * 80, 0, 0.02, { vol: 0.02 }),
    flip: () => tone(300, 0, 0.12, { slide: 600 }),
    charge: () => tone(200, 0, 0.5, { slide: 700, type: "sawtooth", vol: 0.035 }),
    coin: () => notes([988, 1319], 0.08),
    miss: () => notes([392, 330, 262], 0.1, { type: "triangle", vol: 0.08 }),
    rare: () => notes([659, 784, 988, 1319], 0.07),
    epic: () => notes([523, 659, 784, 1047, 784, 1047, 1319], 0.07),
    legendary: () => { notes([523, 659, 784, 1047, 1319, 1568, 2093], 0.08); notes([262, 0, 330, 0, 392, 0, 523], 0.08, { type: "triangle", vol: 0.08 }); },
    levelup: () => notes([523, 523, 784, 784, 1047, 0, 1047, 1319], 0.09),
    unlock: () => notes([784, 988, 1175, 1568], 0.1, { type: "triangle", vol: 0.09 }),
    get muted() { return muted; },
    toggle() { muted = !muted; try { localStorage.setItem("fd-muted", muted ? "1" : "0"); } catch {} return muted; },
  };
})();
