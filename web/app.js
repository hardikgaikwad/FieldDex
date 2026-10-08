// Field Dex front end. Plain JS, no build step.
const $ = (sel, root = document) => root.querySelector(sel);
const RARITIES = ["common", "uncommon", "rare", "epic", "legendary"];
const KINDS = ["bird", "plant", "tree", "insect", "animal", "fungus"];
const DEBUG = new URLSearchParams(location.search).has("debug");
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const cssVar = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

let S = null;              // latest /api/state
let shown = null;          // the XP the HUD currently displays (animated towards S.player)
let tab = "today";
let reveal = { items: [], queue: 0, busy: false, stage: "back" };
let dexFilter = "all";
let storyPick = null;
let pollTimer = null;

// ---------------------------------------------------------------- theme
function applyTheme() {
  let t = "auto";
  try { t = localStorage.getItem("fd-theme") || "auto"; } catch {}
  if (t === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", t);
}
applyTheme();

// ---------------------------------------------------------------- HUD
function avatarCanvas(scale, cls = "") {
  const c = Sprites.drawAvatar(document.createElement("canvas"), S?.avatar, scale);
  if (cls) c.className = cls;
  return c;
}

function renderHud() {
  const p = shown || S.player;
  const hud = $("#hud");
  hud.innerHTML = "";
  hud.append(avatarCanvas(3));
  hud.append(el(`<div class="hud-main">
      <div class="hud-top"><span class="hud-name">${esc(S.name)}</span><span class="hud-lv">LV ${p.level}</span></div>
      <div class="xpbar">${segments(p.into, p.needed)}</div>
      <div class="hud-xp">${p.into} / ${p.needed} XP</div>
    </div>`));
}

function segments(into, needed, pop = -1) {
  const on = Math.floor((into / needed) * 20);
  return Array.from({ length: 20 }, (_, i) => `<i class="${i < on ? "on" : ""}${i === pop ? " pop" : ""}"></i>`).join("");
}

async function animateXp() {
  const target = S.player;
  if (!shown) { shown = { ...target }; renderHud(); return []; }
  const levelsGained = [];
  while (shown.level < target.level || shown.into < target.into) {
    const goal = shown.level < target.level ? shown.needed : target.into;
    const step = Math.max(1, Math.ceil(shown.needed / 20));
    shown.into = Math.min(goal, shown.into + step);
    $(".xpbar").innerHTML = segments(shown.into, shown.needed, Math.floor((shown.into / shown.needed) * 20) - 1);
    $(".hud-xp").textContent = `${shown.into} / ${shown.needed} XP`;
    Sfx.tick();
    await sleep(reducedMotion ? 0 : 45);
    if (shown.level < target.level && shown.into >= shown.needed) {
      shown = { level: shown.level + 1, into: 0, needed: Math.floor(60 * Math.pow(shown.level + 1, 1.4)) };  // matches game.xp_to_next
      levelsGained.push(shown.level);
      renderHud();
    }
  }
  shown = { ...target };
  renderHud();
  return levelsGained;
}

// ---------------------------------------------------------------- tabs
const TABS = [["today", "TODAY"], ["reveal", "REVEAL"], ["dex", "DEX"], ["story", "STORY"], ["me", "ME"]];

function renderTabs() {
  const box = $("#tabs");
  box.innerHTML = "";
  for (const [id, label] of TABS) {
    const b = el(`<button class="tab ${tab === id ? "on" : ""}" aria-label="${label}"></button>`);
    b.append(Sprites.icon(id, tab === id ? cssVar("--sun") : cssVar("--muted"), 3));
    b.append(document.createTextNode(label));
    const dot = (id === "reveal" && (S.unseen || S.queue)) || (id === "story" && S.new_chapter);
    if (dot) b.append(el(`<span class="dot"></span>`));
    b.onclick = () => { Sfx.tap(); go(id); };
    box.append(b);
  }
}

function go(id) {
  tab = id;
  window.scrollTo(0, 0);
  render();
}

function render() {
  renderTabs();
  renderHud();
  const view = $("#view");
  view.innerHTML = "";
  ({ today: renderToday, reveal: renderReveal, dex: renderDex, story: renderStory, me: renderMe })[tab](view);
}

// ---------------------------------------------------------------- today
function greeting() {
  const h = new Date().getHours();
  const outToday = S.days.find(d => d.day === S.today)?.out;
  if (S.queue) return "Your film is developing… check REVEAL in a moment!";
  if (S.unseen) return `${S.unseen} card${S.unseen > 1 ? "s" : ""} waiting to be opened!`;
  if (outToday) return "Great day out, Keeper! The Archive glows brighter.";
  if (h < 5) return "Rest up. Tomorrow's bounty is being written.";
  if (h < 10) return "Birds are loudest right now. Shall we go?";
  if (h < 16) return "The Archive feels faint today… a quick walk?";
  if (h < 19) return "Golden hour is coming. Best light, luckiest finds!";
  return "Still time for a short evening walk. Bugs love lamp light!";
}

function renderToday(view) {
  const stage = el(`<div class="stage"><div class="bubble">${esc(greeting())}</div></div>`);
  stage.append(avatarCanvas(8, "avatar-big"));
  stage.append(el(`<div class="ground"></div>`));
  view.append(stage);

  const w = S.wanted;
  view.append(w
    ? el(`<div class="poster">
        <p class="label">Today's bounty</p>
        <div class="wanted">WANTED</div>
        <div class="target">${esc(w.target)}</div>
        <div class="hint">${esc(w.hint || "")}</div>
        <div class="reward">REWARD +50 XP</div>
        ${w.photo_id ? `<div class="stamp">FOUND!</div>` : ""}
      </div>`)
    : el(`<div class="poster"><p class="label">Today's bounty</p><div class="loader"><i></i><i></i><i></i></div>
        <div class="hint">The bounty board is being written…</div></div>`));

  const up = el(`<div class="box">
      <p class="label">Back from outside?</p>
      <button class="btn go" id="upload">OPEN TODAY'S PACK</button>
      <p class="muted" style="margin:12px 0 0;font-size:16px">Pick today's photos of plants, birds, bugs and trees. Your laptop identifies them. Nothing leaves home.</p>
      <div class="progress hidden" id="upbar"><i></i></div>
    </div>`);
  $("#upload", up).onclick = () => { Sfx.tap(); $("#picker").click(); };
  view.append(up);

  view.append(el(`<div class="stats3">
      <div class="stat"><b>${S.species}</b><span>SPECIES</span></div>
      <div class="stat"><b>${S.days_out}</b><span>DAYS OUT</span></div>
      <div class="stat"><b>${S.player.level}</b><span>LEVEL</span></div>
    </div>`));

  view.append(el(`<div class="box"><p class="label">Last 30 days outside</p>
      <div class="days">${S.days.map(d => `<i class="${d.out ? "out" : ""} ${d.day === S.today ? "today" : ""}" title="${d.day}"></i>`).join("")}</div>
    </div>`));

  if (DEBUG) {
    const dbg = el(`<div class="box"><p class="label">Debug</p>
        ${S.debug ? `<button class="btn small" id="dbg-day">NEXT DAY ▶ (${esc(S.today)})</button>` : ""}
        <button class="btn small" data-r="legendary">FAKE LEGENDARY</button>
        <button class="btn small" data-r="rare">FAKE RARE</button>
        <button class="btn small" data-r="miss">FAKE MISS</button>
        <button class="btn small" id="dbg-lv">LEVEL UP</button></div>`);
    dbg.querySelectorAll("[data-r]").forEach(b => b.onclick = () => fakeReveal(b.dataset.r));
    $("#dbg-lv", dbg).onclick = () => levelUpOverlay(S.player.level + 1);
    const nextDay = $("#dbg-day", dbg);
    if (nextDay) nextDay.onclick = async () => {
      const r = await api("/api/debug/next-day", {});
      toast(`It's now ${r.today}. New bounty is being written…`);
      Sfx.coin();
      await refresh();
    };
    view.append(dbg);
  }
}

$("#picker").addEventListener("change", e => {
  const files = [...e.target.files];
  e.target.value = "";
  if (files.length) uploadFiles(files);
});

function uploadFiles(files) {
  const form = new FormData();
  files.forEach(f => form.append("files", f, f.name));
  const xhr = new XMLHttpRequest();
  const bar = $("#upbar");
  bar?.classList.remove("hidden");
  xhr.upload.onprogress = ev => { if (ev.lengthComputable && bar) bar.firstElementChild.style.width = `${(ev.loaded / ev.total) * 100}%`; };
  xhr.onload = async () => {
    if (xhr.status !== 200) { toast("Upload failed. Is the laptop still on the hotspot?"); return; }
    const r = JSON.parse(xhr.responseText);
    const parts = [`${r.added} new photo${r.added === 1 ? "" : "s"}`];
    if (r.duplicates) parts.push(`${r.duplicates} already opened`);
    if (r.failed) parts.push(`${r.failed} unreadable`);
    toast(parts.join(" · "));
    Sfx.coin();
    await refresh();
    go("reveal");
  };
  xhr.onerror = () => toast("Can't reach the laptop. Same hotspot?");
  xhr.open("POST", "/api/upload");
  xhr.send(form);
}

// ---------------------------------------------------------------- reveal
async function loadReveal() {
  const r = await api("/api/reveal");
  const fakes = reveal.items.filter(i => i.fake);
  reveal = { ...reveal, ...r, items: [...fakes, ...r.items] };
}

function renderReveal(view) {
  const wrap = el(`<div class="reveal-wrap"></div>`);
  view.append(wrap);
  const item = reveal.items[0];

  if (!item) {
    if (reveal.queue || reveal.busy) {
      wrap.append(el(`<div class="box" style="width:100%;text-align:center">
          <h2 class="title">DEVELOPING FILM…</h2>
          <div class="loader"><i></i><i></i><i></i></div>
          <p class="muted" style="margin:0">${reveal.queue} photo${reveal.queue === 1 ? "" : "s"} left · about 10 seconds each.<br>Your laptop's AI is identifying them, offline.</p>
        </div>`));
    } else {
      const box = el(`<div class="box" style="width:100%;text-align:center">
          <h2 class="title">NO PACKS LEFT</h2>
          <p class="muted">Go outside and photograph something alive. Every photo becomes a card.</p>
          <button class="btn go">SEE TODAY'S BOUNTY</button>
        </div>`);
      $("button", box).onclick = () => go("today");
      wrap.append(box);
      if (S.new_chapter) {
        const st = el(`<button class="btn gold" style="margin-top:6px">READ YOUR NEW CHAPTER</button>`);
        st.onclick = () => go("story");
        wrap.append(st);
      }
    }
    return;
  }

  const left = reveal.items.length - 1;
  wrap.append(el(`<div class="deck-count">${left ? `${left} MORE AFTER THIS` : "LAST CARD"}${reveal.queue ? ` · ${reveal.queue} DEVELOPING` : ""}</div>`));
  const back = el(`<div class="card-back wobble"><span>TAP TO REVEAL</span></div>`);
  back.prepend(Sprites.icon("reveal", "#ffffff", 8));
  back.onclick = () => flip(back, item, wrap);
  wrap.append(back);
}

async function flip(back, item, wrap) {
  if (reveal.stage !== "back") return;
  reveal.stage = "flipping";
  const tier = item.outcome === "rejected" || item.outcome === "error" ? -1 : RARITIES.indexOf(item.rolled);
  back.classList.remove("wobble");
  back.classList.add("charge");
  Sfx.charge();
  await sleep(reducedMotion ? 0 : 450 + Math.max(0, tier) * 180);
  if (tier >= 2) back.style.background = cssVar(`--r-${item.rolled}`);
  await sleep(reducedMotion ? 0 : 200);
  back.classList.remove("charge");
  back.classList.add("flip-out");
  Sfx.flip();
  await sleep(reducedMotion ? 0 : 190);

  const front = tier < 0 ? missCard(item) : revealCard(item);
  front.classList.add("flip-in");
  back.replaceWith(front);

  if (tier < 0) Sfx.miss();
  else if (tier >= 4) { Sfx.legendary(); shake(); burst(front, 46); jumpHud(); }
  else if (tier === 3) { Sfx.epic(); shake(); burst(front, 26); jumpHud(); }
  else if (tier === 2) { Sfx.rare(); burst(front, 14); jumpHud(); }
  else Sfx.coin();

  const xp = el(`<div class="xp-pop">+${item.xp || 0} XP${item.wanted ? " · BOUNTY!" : ""}</div>`);
  const btn = el(`<button class="btn go" style="max-width:300px">COLLECT ▶</button>`);
  btn.onclick = () => collect(item);
  wrap.append(xp, btn);
  reveal.stage = "front";
}

function revealCard(item) {
  const c = cardEl(item.card, { rolled: item.rolled });
  c.classList.add("reveal-card");
  c.prepend(el(`<div class="badge-new">${item.outcome === "new" ? "NEW!" : "★ +1"}</div>`));
  return c;
}

function missCard(item) {
  return el(`<div class="card reveal-card miss">
      <div class="card-top"><span class="card-name">${item.outcome === "error" ? "GLITCH" : "NO CATCH"}</span></div>
      <div class="art" style="display:flex;align-items:center;justify-content:center;font:28px var(--head);color:var(--muted)">?</div>
      <p class="flavour" style="margin-top:12px">${esc(item.outcome === "error" ? "The identifier hiccupped on this one. Try uploading it again later." : item.reason)}</p>
    </div>`);
}

async function collect(item) {
  if (reveal.stage !== "front") return;
  reveal.stage = "collecting";
  Sfx.tap();
  if (!item.fake) await api("/api/reveal/seen", { ids: [item.photo_id] });
  reveal.items.shift();
  await refresh(false);
  const levels = await animateXp();
  for (const lv of levels) await levelUpOverlay(lv);
  for (const u of item.unlocks || []) await unlockOverlay(u);
  reveal.stage = "back";
  if (!reveal.items.length && !reveal.queue && S.new_chapter) await chapterOverlay();
  render();
}

// ---------------------------------------------------------------- cards
function stars(n) { return "★".repeat(n) + "☆".repeat(Math.max(0, 5 - n)); }

function cardEl(card, { rolled } = {}) {
  const r = card.rarity;
  const c = el(`<div class="card r-${r}">
      <div class="card-top"><span class="card-name">${esc(card.name)}</span></div>
      <div class="art"><img class="px" alt="${esc(card.name)}" src="/photos/${card.photo_id}_px.png"></div>
      <div class="rarity-row"><span class="tag">${r.toUpperCase()}</span><span class="stars">${stars(card.stars)}</span></div>
      <p class="flavour">${esc(card.flavour)}</p>
      ${Object.entries(card.stats || {}).map(([k, v]) => `<div class="statrow"><span>${k.slice(0, 3).toUpperCase()}</span><div class="bar"><i style="width:${v}%"></i></div><b>${v}</b></div>`).join("")}
    </div>`);
  $(".card-top", c).append(Sprites.icon(card.kind in { bird: 1, plant: 1, tree: 1, insect: 1, fungus: 1, animal: 1 } ? card.kind : "all", cssVar(`--r-${r}`), 3));
  // Tap the art to flip between the pixel version and the real photo.
  const img = $("img", c);
  img.onclick = () => {
    const real = img.src.endsWith(".jpg");
    img.src = `/photos/${card.photo_id}${real ? "_px.png" : ".jpg"}`;
    img.classList.toggle("px", real);
  };
  return c;
}

// ---------------------------------------------------------------- dex
async function renderDex(view) {
  const d = await api("/api/dex");
  const total = Object.values(d.goals).reduce((a, b) => a + b, 0);
  const chips = el(`<div class="chips"></div>`);
  for (const k of ["all", ...KINDS]) {
    const n = k === "all" ? d.cards.length : d.counts[k] || 0;
    const of = k === "all" ? total : d.goals[k];
    const chip = el(`<button class="chip ${dexFilter === k ? "on" : ""}"></button>`);
    chip.append(Sprites.icon(k, dexFilter === k ? "#2a1d00" : cssVar("--text"), 2));
    chip.append(document.createTextNode(`${k.toUpperCase()} ${n}/${of}`));
    chip.onclick = () => { Sfx.tap(); dexFilter = k; render(); };
    chips.append(chip);
  }
  view.append(chips);

  const cards = d.cards
    .filter(c => dexFilter === "all" || c.kind === dexFilter)
    .sort((a, b) => RARITIES.indexOf(b.rarity) - RARITIES.indexOf(a.rarity));
  const grid = el(`<div class="grid"></div>`);
  for (const card of cards) {
    const m = el(`<div class="mini r-${card.rarity}"><img class="px" alt="" src="/photos/${card.photo_id}_px.png">
        <p>${esc(card.name)}</p>${card.stars > 1 ? `<span class="st">★${card.stars}</span>` : ""}</div>`);
    m.onclick = () => { Sfx.tap(); cardOverlay(card); };
    grid.append(m);
  }
  const goal = dexFilter === "all" ? Math.max(6, 9 - (cards.length % 3)) : Math.max(0, d.goals[dexFilter] - cards.length);
  for (let i = 0; i < Math.min(goal, 12); i++) grid.append(el(`<div class="mini empty"><div class="sil">?</div><p>???</p></div>`));
  view.append(grid);
  if (!d.cards.length) view.append(el(`<p class="muted" style="text-align:center;margin-top:20px">Your Dex is empty. Every ? is a creature waiting outside.</p>`));
}

// ---------------------------------------------------------------- story
async function renderStory(view) {
  const { chapters } = await api("/api/story");
  if (S.new_chapter) { api("/api/story/seen", {}); S.new_chapter = false; renderTabs(); }
  if (!chapters.length) {
    view.append(el(`<div class="box" style="text-align:center"><h2 class="title">THE GREEN ARCHIVE</h2>
        <p>An ancient living book remembers every creature of your city. Its pages are fading.</p>
        <p class="muted">Collect your first creature to unlock Chapter 1.</p></div>`));
    return;
  }
  const pick = chapters.find(c => c.n === storyPick) || chapters[chapters.length - 1];
  const dlg = el(`<div class="dialog"><div class="dialog-head"><div><div class="who">CHAPTER ${pick.n}</div><h3>${esc(pick.title)}</h3></div></div>
      <p></p><span class="more hidden">▼</span></div>`);
  $(".dialog-head", dlg).prepend(avatarCanvas(3));
  view.append(dlg);
  typewriter($("p", dlg), pick.text, $(".more", dlg), dlg);

  const list = el(`<div class="chapter-list"><p class="label">Chapters</p></div>`);
  for (const c of [...chapters].reverse()) {
    const b = el(`<button class="${c.n === pick.n ? "on" : ""}"><span>CH.${c.n} ${esc(c.title)}</span><span>${c.day.slice(5)}</span></button>`);
    b.onclick = () => { Sfx.tap(); storyPick = c.n; render(); };
    list.append(b);
  }
  list.insertBefore(el(`<button class="locked" disabled><span>CH.${chapters.length + 1} ???</span><span>🔒 GO OUTSIDE</span></button>`), list.children[1]);
  view.append(list);
}

function typewriter(p, text, more, box) {
  let i = 0;
  let done = false;
  const finish = () => { done = true; p.textContent = text; more.classList.remove("hidden"); };
  box.onclick = () => { if (!done) finish(); };
  if (reducedMotion) return finish();
  (function step() {
    if (done) return;
    p.textContent = text.slice(0, ++i);
    if (i % 3 === 0) Sfx.type();
    if (i >= text.length) return finish();
    setTimeout(step, /[.,!?…]/.test(text[i - 1]) ? 140 : 22);
  })();
}

// ---------------------------------------------------------------- me
function renderMe(view) {
  const first = !S.avatar;
  const a = { ...Sprites.DEFAULT, ...(S.avatar || {}), gear: { ...(S.avatar?.gear || {}) } };

  if (first) view.append(el(`<div class="box" style="text-align:center"><h2 class="title">CREATE YOUR KEEPER</h2>
      <p class="muted" style="margin:0">This is you. Your finds will dress them up.</p></div>`));

  const stage = el(`<div class="stage"></div>`);
  const big = avatarCanvas(8, "avatar-big");
  stage.append(big, el(`<div class="ground"></div>`));
  view.append(stage);

  const redraw = () => { S.avatar = a; Sprites.drawAvatar(big, a, 8); renderHud(); saveAvatarSoon(a); };
  const box = el(`<div class="box"><p class="label">Look</p></div>`);
  const pickers = [
    ["SKIN", "skin", Sprites.OPTIONS.skin.length, v => `<span class="swatch" style="background:${Sprites.OPTIONS.skin[v]}"></span>`],
    ["HAIR", "hair", Sprites.OPTIONS.hair.length, v => Sprites.OPTIONS.hair[v].toUpperCase()],
    ["COLOUR", "hairColor", Sprites.OPTIONS.hairColor.length, v => `<span class="swatch" style="background:${Sprites.OPTIONS.hairColor[v]}"></span>`],
    ["OUTFIT", "outfit", Sprites.OPTIONS.outfit.length, v => `<span class="swatch" style="background:${Sprites.OPTIONS.outfit[v]}"></span>`],
  ];
  for (const [label, key, n, show] of pickers) {
    const idx = () => key === "hair" ? Sprites.OPTIONS.hair.indexOf(a.hair) : a[key];
    const row = el(`<div class="picker"><span>${label}</span><button class="arrow">◀</button><b></b><button class="arrow">▶</button></div>`);
    const val = $("b", row);
    const set = d => {
      const v = (idx() + d + n) % n;
      if (key === "hair") a.hair = Sprites.OPTIONS.hair[v]; else a[key] = v;
      val.innerHTML = show(v);
    };
    set(0);
    const [prev, next] = row.querySelectorAll(".arrow");
    prev.onclick = () => { Sfx.tap(); set(-1); redraw(); };
    next.onclick = () => { Sfx.tap(); set(1); redraw(); };
    box.append(row);
  }
  view.append(box);

  if (first) {
    const start = el(`<button class="btn go" style="margin-bottom:18px">BEGIN ADVENTURE ▶</button>`);
    start.onclick = async () => { await saveAvatar(a); Sfx.unlock(); go("today"); };
    view.append(start);
    return;
  }

  const gear = el(`<div class="box"><p class="label">Gear & badges</p><div class="gear"></div></div>`);
  for (const u of S.unlocks) {
    const slot = Sprites.GEAR[u.id]?.slot;
    const on = slot && a.gear[slot] === u.id;
    const b = el(`<button class="${on ? "on" : ""}" ${u.have ? "" : "disabled"}>${u.have ? esc(u.name.toUpperCase()) : "🔒 ???"}<small>${esc(u.desc)}</small></button>`);
    b.onclick = () => {
      Sfx.tap();
      a.gear[slot] = a.gear[slot] === u.id ? null : u.id;
      redraw();
      render();
    };
    $(".gear", gear).append(b);
  }
  view.append(gear);

  let theme = "auto";
  try { theme = localStorage.getItem("fd-theme") || "auto"; } catch {}
  const settings = el(`<div class="box"><p class="label">Settings</p>
      <div class="row-between" style="margin-bottom:12px"><span>Sound</span><button class="btn small" id="snd">${Sfx.muted ? "OFF" : "ON"}</button></div>
      <div class="row-between"><span>Theme</span><button class="btn small" id="thm">${theme.toUpperCase()}</button></div>
    </div>`);
  $("#snd", settings).onclick = e => { e.target.textContent = Sfx.toggle() ? "OFF" : "ON"; Sfx.tap(); };
  $("#thm", settings).onclick = () => {
    const next = { auto: "dark", dark: "light", light: "auto" }[theme];
    try { localStorage.setItem("fd-theme", next); } catch {}
    applyTheme();
    render();
  };
  view.append(settings);
}

let saveTimer = null;
function saveAvatarSoon(a) { clearTimeout(saveTimer); saveTimer = setTimeout(() => saveAvatar(a), 400); }
async function saveAvatar(a) { S.avatar = a; await api("/api/avatar", a); }

// ---------------------------------------------------------------- overlays & effects
function overlay(inner) {
  return new Promise(resolve => {
    const o = el(`<div class="overlay"><div class="overlay-box"></div></div>`);
    $(".overlay-box", o).append(...inner);
    const ok = el(`<button class="btn gold" style="margin-top:16px">OK!</button>`);
    ok.onclick = () => { Sfx.tap(); o.remove(); resolve(); };
    $(".overlay-box", o).append(ok);
    document.body.append(o);
  });
}

function levelUpOverlay(level) {
  Sfx.levelup();
  const av = avatarCanvas(8, "jump");
  setTimeout(() => burst(av, 30), 50);
  return overlay([el(`<div class="big">LEVEL UP!</div>`), av, el(`<div class="sub">YOU ARE NOW LV ${level}</div>`)]);
}

function unlockOverlay(u) {
  const slot = Sprites.GEAR[u.id]?.slot;
  const a = { ...Sprites.DEFAULT, ...(S.avatar || {}), gear: { ...(S.avatar?.gear || {}) } };
  if (slot) { a.gear[slot] = u.id; saveAvatar(a); }
  Sfx.unlock();
  const av = Sprites.drawAvatar(document.createElement("canvas"), a, 8);
  av.className = "jump";
  return overlay([el(`<div class="big">NEW GEAR!</div>`), av,
    el(`<div class="sub">${esc(u.name.toUpperCase())}</div>`), el(`<p class="muted">${esc(u.desc)}. Equipped!</p>`)]);
}

function chapterOverlay() {
  Sfx.unlock();
  return new Promise(resolve => {
    const o = el(`<div class="overlay"><div class="overlay-box">
        <div class="big">NEW CHAPTER</div><p>The Archive remembers your finds. A new page of the story is written.</p>
        <button class="btn gold">READ NOW ▶</button><button class="btn">LATER</button></div></div>`);
    const [read, later] = o.querySelectorAll("button");
    read.onclick = () => { o.remove(); tab = "story"; resolve(); };
    later.onclick = () => { o.remove(); resolve(); };
    document.body.append(o);
  });
}

function cardOverlay(card) {
  const o = el(`<div class="overlay"><div class="overlay-box" style="text-align:left"></div></div>`);
  $(".overlay-box", o).append(cardEl(card), el(`<p class="muted" style="font-size:15px;margin:14px 0 0">First found ${esc(card.first_found.slice(0, 10))} · tap the art to see your photo</p>`));
  const close = el(`<button class="btn" style="margin-top:14px">CLOSE</button>`);
  close.onclick = () => o.remove();
  $(".overlay-box", o).append(close);
  o.onclick = e => { if (e.target === o) o.remove(); };
  document.body.append(o);
}

function toast(msg) {
  const t = el(`<div class="toast">${esc(msg)}</div>`);
  document.body.append(t);
  setTimeout(() => t.remove(), 2600);
}

function shake() {
  if (reducedMotion) return;
  const app = $("#app");
  app.classList.remove("shake");
  void app.offsetWidth;
  app.classList.add("shake");
}

function jumpHud() {
  const c = $("#hud canvas");
  if (!c || reducedMotion) return;
  c.classList.add("jump");
  setTimeout(() => c.classList.remove("jump"), 520);
}

function burst(target, count) {
  if (reducedMotion) return;
  const r = target.getBoundingClientRect();
  const colours = ["--sun", "--grass", "--sky", "--rose", "--violet", "--amber"].map(cssVar);
  for (let i = 0; i < count; i++) {
    const p = el(`<div class="particle"></div>`);
    p.style.background = colours[i % colours.length];
    p.style.left = `${r.left + r.width / 2}px`;
    p.style.top = `${r.top + r.height / 3}px`;
    document.body.append(p);
    const angle = Math.random() * Math.PI * 2;
    const dist = 80 + Math.random() * 160;
    const dx = Math.round(Math.cos(angle) * dist / 4) * 4;
    const dy = Math.round(Math.sin(angle) * dist / 4) * 4;
    p.animate([{ transform: "translate(0,0)", opacity: 1 }, { transform: `translate(${dx}px, ${dy + 60}px)`, opacity: 0 }],
      { duration: 700 + Math.random() * 500, easing: "steps(8)", fill: "forwards" }).onfinish = () => p.remove();
  }
}

// ---------------------------------------------------------------- debug
async function fakeReveal(kind) {
  const d = await api("/api/dex");
  const card = d.cards[0] || { name: "Test Sparrow", kind: "bird", rarity: "common", stars: 1, flavour: "A pretend bird for testing.", stats: { charm: 40, stealth: 70, grit: 55 }, photo_id: 0, first_found: "2026-01-01" };
  const item = kind === "miss"
    ? { fake: true, outcome: "rejected", reason: "Nice try. That's a screen! Real world only.", xp: 2 }
    : { fake: true, outcome: "new", rolled: kind, xp: 160, card: { ...card, rarity: kind }, unlocks: [] };
  reveal.items.unshift(item);
  go("reveal");
}

// ---------------------------------------------------------------- data & polling
async function refresh(rerender = true) {
  S = await api("/api/state");
  await loadReveal();
  if (rerender) render();
  schedulePoll();
}

function schedulePoll() {
  clearTimeout(pollTimer);
  const waiting = S.queue || S.worker.busy || !S.wanted;
  if (!waiting) return;
  pollTimer = setTimeout(async () => {
    const before = `${S.queue}|${S.unseen}|${!!S.wanted}|${S.new_chapter}`;
    S = await api("/api/state");
    await loadReveal();
    const after = `${S.queue}|${S.unseen}|${!!S.wanted}|${S.new_chapter}`;
    // Only redraw when something changed and the player isn't mid-reveal.
    if (before !== after && reveal.stage === "back" && !document.querySelector(".overlay")) render();
    schedulePoll();
  }, 3000);
}

(async function boot() {
  try {
    await refresh(false);
    shown = { ...S.player };
    const asked = new URLSearchParams(location.search).get("tab");
    if (!S.avatar) tab = "me";
    else if (TABS.some(([id]) => id === asked)) tab = asked;
    else if (S.unseen) tab = "reveal";
    render();
  } catch (e) {
    $("#view").innerHTML = `<div class="box"><h2 class="title">CAN'T REACH BASE</h2><p>Is the laptop running Field Dex and on the same hotspot?</p><p class="muted">${esc(e.message)}</p></div>`;
  }
})();
