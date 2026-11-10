/* CINEFORGE front end: plain JavaScript, no build step. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Request failed (${r.status})`);
  return data;
}
const send = (path, body, method = "POST") =>
  api(path, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

/* ---------- icons ---------- */
const svg = (d) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
const ICON = {
  clapper: svg('<path d="M3 9h18v11H3z"/><path d="M3 9l2-5 4 1-2 4M9 5l4 1-2 4M13 6l4 1-2 4M17 7l3 1-1.5 3"/>'),
  film: svg('<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 3v18M17 3v18M3 8h4M3 12h4M3 16h4M17 8h4M17 12h4M17 16h4"/>'),
  reel: svg('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="6.5" r="1.4"/><circle cx="17" cy="14.5" r="1.4"/><circle cx="7" cy="14.5" r="1.4"/>'),
  gauge: svg('<path d="M4 18a9 9 0 1 1 16 0"/><path d="M12 14l4-5"/><circle cx="12" cy="14" r="1.2"/>'),
  gear: svg('<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1.3l2-1.5-2-3.4-2.4 1a7 7 0 0 0-2.2-1.3L14 3h-4l-.4 2.5a7 7 0 0 0-2.2 1.3l-2.4-1-2 3.4 2 1.5A7 7 0 0 0 5 12c0 .4 0 .9.1 1.3l-2 1.5 2 3.4 2.4-1a7 7 0 0 0 2.2 1.3L10 21h4l.4-2.5a7 7 0 0 0 2.2-1.3l2.4 1 2-3.4-2-1.5c.1-.4.1-.9 0-1.3z"/>'),
  pen: svg('<path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/>'),
  play: svg('<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M10 9l5 3-5 3z"/>'),
  mic: svg('<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>'),
  wand: svg('<path d="M5 19L17 7"/><path d="M15 5l4 4M18 2v3M20 4h-3M6 4v2M5 5h2M20 15v2M19 16h2"/>'),
  music: svg('<path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/>'),
  scissors: svg('<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8.5 8l11 11M8.5 16l11-11"/>'),
  image: svg('<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-8 9"/>'),
};
$$("[data-icon]").forEach((el) => (el.innerHTML = ICON[el.dataset.icon] || ""));

/* ---------- atmosphere ---------- */
(function dust() {
  if (REDUCED) return;
  const box = $("#dust");
  for (let i = 0; i < 22; i++) {
    const p = document.createElement("i");
    p.style.cssText = `left:${Math.random() * 100}%;--dx:${(Math.random() - 0.5) * 160}px;` +
      `animation-duration:${14 + Math.random() * 22}s;animation-delay:${-Math.random() * 30}s;` +
      `width:${2 + Math.random() * 3}px;height:${2 + Math.random() * 3}px`;
    box.appendChild(p);
  }
})();

/* ---------- intro: curtains + film-leader countdown (once per visit) ---------- */
(function intro() {
  const splash = $("#splash"), body = document.body;
  const finish = () => { splash.classList.add("out"); body.classList.add("opened"); sessionStorage.setItem("cf-seen", "1"); };
  if (REDUCED || sessionStorage.getItem("cf-seen")) { splash.remove(); body.classList.add("opened"); $$(".curtain").forEach((c) => (c.style.display = "none")); heroIn(); return; }
  let n = 3; const count = $("#count");
  const tick = () => { if (splash.classList.contains("out")) return; if (n === 0) { finish(); setTimeout(heroIn, 500); return; } count.textContent = n--; setTimeout(tick, 650); };
  splash.addEventListener("click", () => { finish(); setTimeout(heroIn, 400); n = -1; });
  tick();
})();

function heroIn() {
  const parts = [["Lights.", true], ["Camera.", false], ["Automate.", false]];
  $("#hero-title").innerHTML = parts.map(([w, hot], i) =>
    `<span class="w"><span class="${hot ? "hot" : ""}" style="animation-delay:${i * 0.14}s">${w}</span></span>`).join(" ");
}

const GENRES = ["THRILLER", "HORROR", "SCI-FI", "NOIR", "ACTION", "ROMANCE", "COMEDY", "MYSTERY", "DRAMA", "FANTASY", "CRIME", "ANIMATION"];
$("#marquee").innerHTML = [...GENRES, ...GENRES].map((g) => `<span>${g} <em>●</em></span>`).join("");

/* ---------- navigation ---------- */
let timer = null, selected = null, mode = "title";
$$("#nav button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
function show(view) {
  $$("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.view === view));
  ["new", "jobs", "library", "usage", "settings"].forEach((v) => {
    const el = $(`#view-${v}`); el.hidden = v !== view;
    if (v === view) { el.classList.remove("view"); void el.offsetWidth; el.classList.add("view"); }
  });
  clearInterval(timer);
  if (view === "new") { loadStats(); placePill($("#mode-seg")); }
  if (view === "jobs") { loadUsed(); loadJobs(); timer = setInterval(loadJobs, 2500); }
  if (view === "library") loadLibrary();
  if (view === "usage") loadUsage();
  if (view === "settings") loadSettings();
  scrollTo({ top: 0, behavior: "smooth" });
}

/* sliding pill for segmented controls */
function placePill(seg) {
  const on = $("button.on", seg), pill = $(".pill", seg);
  if (!on || !pill) return;
  pill.style.width = on.offsetWidth + "px";
  pill.style.transform = `translateX(${on.offsetLeft - 4}px)`;
}
addEventListener("resize", () => placePill($("#mode-seg")));
setTimeout(() => placePill($("#mode-seg")), 80);

/* ---------- stats + REC light ---------- */
function countUp(el, to, dec = 0) {
  if (REDUCED) { el.textContent = to.toFixed(dec); return; }
  const t0 = performance.now(), dur = 900;
  const step = (t) => { const k = Math.min(1, (t - t0) / dur), e = 1 - Math.pow(1 - k, 3); el.textContent = (to * e).toFixed(dec); if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}
async function loadStats() {
  try {
    const s = await api("/api/stats");
    $("#stats").innerHTML = [["videos", "Videos made", s.videos, 0], ["minutes", "Minutes of film", s.minutes, 1], ["movies", "Movies covered", s.movies, 0], ["uploaded", "Published", s.uploaded, 0]]
      .map(([id, label, v, d]) => `<div class="stat"><b id="st-${id}">0</b><span>${label}</span></div>`).join("");
    [["videos", s.videos, 0], ["minutes", s.minutes, 1], ["movies", s.movies, 0], ["uploaded", s.uploaded, 0]].forEach(([id, v, d]) => countUp($(`#st-${id}`), v, d));
    setRec(s.running);
  } catch (e) { /* the hero still works without numbers */ }
}
function setRec(n) {
  document.body.classList.toggle("rec-on", n > 0);
  $("#rec-text").textContent = n > 0 ? `Recording (${n})` : "Standby";
}
setInterval(async () => { try { setRec((await api("/api/stats")).running); } catch (e) {} }, 5000);

/* ---------- config / sidebar chips / new job form ---------- */
let CFG = {};
async function loadConfig() {
  CFG = await api("/api/config");
  const row = (label, on) => `<span><i class="dot ${on ? "on" : ""}"></i>${esc(label)}</span>`;
  $("#keys").innerHTML = row(CFG.llm_label + " (scripts)", CFG.llm) + row(CFG.voice_label, CFG.voice) +
    row("Stock footage", CFG.stock) + row("AI posters", CFG.openai_images) + row("YouTube upload", CFG.youtube_connected) + row("Instagram upload", CFG.instagram) + row("Facebook upload", CFG.facebook);
  $("#f-channel").innerHTML = CFG.channels.map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join("");
  applyChannelDefaults();
}
function applyChannelDefaults() {
  const c = CFG.channels.find((x) => x.id === $("#f-channel").value);
  if (c) { $("#f-format").value = c.default_format; $("#f-lang").value = c.language || ""; }
}
$("#f-channel").addEventListener("change", applyChannelDefaults);

$("#mode-seg").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  mode = b.dataset.mode;
  $$("#mode-seg button").forEach((x) => x.classList.toggle("on", x === b));
  placePill($("#mode-seg"));
  $("#url-row").hidden = $("#rights-row").hidden = mode !== "link";
  $("#title-label").textContent = mode === "link" ? "Title for the new video (optional)" : "Video title or topic";
});

$("#new-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = $("#new-msg"), btn = e.target.querySelector("button.primary");
  msg.className = "msg"; msg.innerHTML = '<span class="spin"></span> Rolling…'; btn.disabled = true;
  try {
    const out = await send("/api/jobs", {
      mode, title: $("#f-title").value, url: $("#f-url").value, channel_id: $("#f-channel").value,
      format: $("#f-format").value, language: $("#f-lang").value, voice_id: $("#f-voice").value,
      voice_provider: $("#f-vprov").value, use_pexels: $("#f-pexels").checked, rights_confirmed: $("#f-rights").checked,
      use_trailers: $("#f-trailers").checked, unique_movies: $("#f-unique").checked, movie_count: $("#f-count").value,
    });
    selected = out.id; msg.textContent = ""; show("jobs");
  } catch (err) { msg.className = "msg err"; msg.textContent = err.message; }
  btn.disabled = false;
});

/* ---------- projects ---------- */
const STAGES = [
  { label: "Script", icon: "pen", re: /script|download|analys/i },
  { label: "Trailers", icon: "play", re: /trailer/i },
  { label: "Voice", icon: "mic", re: /narration|voice/i },
  { label: "Scenes", icon: "wand", re: /matching/i },
  { label: "Music", icon: "music", re: /music/i },
  { label: "Edit", icon: "scissors", re: /editing/i },
  { label: "Posters", icon: "image", re: /thumbnail/i },
];
function stageIndex(j) {
  if (j.status === "review" || j.status === "uploaded") return STAGES.length;
  if (j.status === "queued") return -1;
  return STAGES.findIndex((s) => s.re.test(j.stage || ""));
}
function pipeHTML(j) {
  const idx = stageIndex(j);
  return `<div class="pipe">${STAGES.map((s, i) => `<div class="frame ${i < idx ? "done" : i === idx ? "active" : ""}">${ICON[s.icon]}${s.label}</div>`).join("")}</div>`;
}
function stripHTML(p, active) {
  const n = 40, filled = Math.round((p / 100) * n);
  return `<div class="strip" aria-label="${p}% complete">` +
    Array.from({ length: n }, (_, i) => `<i class="${i < filled ? "f" : ""}${active && i === filled - 1 ? " last" : ""}"></i>`).join("") + "</div>";
}

const jobTitle = (j) => j.result?.metadata?.title || j.input.title || j.input.url || "Untitled";
function cardHTML(j) {
  const active = j.status === "running" || j.status === "queued";
  return `<div class="top"><span class="t">${esc(jobTitle(j))}</span><span class="badge ${j.status}">${esc(j.status === "review" ? "ready to review" : j.status)}</span></div>
    ${active ? stripHTML(j.progress, true) : ""}<small class="muted">${esc(j.stage)}</small>`;
}

async function loadJobs() {
  let jobs;
  try { jobs = await api("/api/jobs"); } catch (e) { return; }
  const box = $("#jobs-list");
  const ids = jobs.map((j) => j.id).join(",");
  if (box.dataset.ids !== ids) {  // rebuild only when projects are added or removed, so a playing video is never interrupted
    box.dataset.ids = ids; lastKey = "";
    box.innerHTML = jobs.length ? jobs.map((j) => `<div class="jobwrap" data-id="${j.id}"><div class="job" data-id="${j.id}"></div><div class="job-detail"></div></div>`).join("")
      : `<div class="card"><h2>NO PROJECTS YET</h2><p class="muted" style="margin:0">Open <strong>New video</strong> and create your first one.</p></div>`;
  }
  for (const j of jobs) {
    const wrap = box.querySelector(`.jobwrap[data-id="${j.id}"]`); if (!wrap) continue;
    const card = $(".job", wrap), html = cardHTML(j);
    if (card.dataset.sig !== html) { card.innerHTML = html; card.dataset.sig = html; }
    card.classList.toggle("sel", j.id === selected);
    if (j.id !== selected) { const d = $(".job-detail", wrap); if (d.innerHTML) d.innerHTML = ""; }
  }
  const cur = jobs.find((j) => j.id === selected);
  if (cur) renderDetail(false, cur); else selected = null;
}
$("#jobs-list").addEventListener("click", (e) => {
  const card = e.target.closest(".job"); if (!card) return;
  selected = selected === card.dataset.id ? null : card.dataset.id; lastKey = ""; loadJobs();
});

let lastKey = "";
const PUBERR = {};
async function renderDetail(force, job) {
  const box = $(`.jobwrap[data-id="${selected}"] .job-detail`);
  if (!box) return;
  job = job || (await api(`/api/jobs/${selected}`).catch(() => null));
  if (!job) { selected = null; return; }
  const key = `${job.id}|${job.status}|${job.updated}|${JSON.stringify(job.result?.upload || "")}`;
  if (!force && key === lastKey) return;
  if (!force && box.contains(document.activeElement) && ["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  lastKey = key;
  box.innerHTML = detailHTML(job);
  bindDetail(job);
}

function detailHTML(j) {
  if (j.status === "failed") {
    return `<div class="card"><h2>CUT! THIS TAKE FAILED</h2><div class="err-box">${esc(j.error)}</div>
      <div class="row"><button class="primary" id="retry">Roll again</button><button class="ghost danger" id="del">Delete project</button></div></div>`;
  }
  if (!j.result || !j.result.video) {
    const idx = stageIndex(j);
    return `<div class="card glow"><div class="nowshow">
      <div class="leader"><i class="h"></i><i class="v"></i><b>${j.progress}</b></div>
      <div class="txt"><div class="eyebrow">On set</div><h3>${esc(j.stage || "Working")}</h3>
        <p>${idx < 0 ? "Waiting for the crew to be free." : "This page updates by itself. You can leave it and come back."}</p></div></div>
      ${pipeHTML(j)}${stripHTML(j.progress, true)}</div>`;
  }
  const r = j.result, base = `/files/${j.id}`, m = r.metadata, long = r.format === "long";
  const thumbs = (r.thumbnails || []).map((t) => `
    <div class="thumb ${t.file === r.selected_thumbnail ? "sel" : ""}" data-file="${esc(t.file)}">
      ${t.recommended ? '<span class="rec2">Best pick</span>' : ""}
      <img src="${base}/thumbs/${esc(t.file)}" alt="Poster: ${esc(t.headline)}">
      <div class="cap">${t.score != null ? `${esc(t.score)}/10 · ` : ""}${esc(t.reason || t.headline)}</div></div>`).join("");
  const segs = r.segments.map((s) => `<div>${s.movie ? "<strong>" + esc(s.movie) + "</strong><br>" : ""}${esc(s.narration)}<br><small>${esc(s.asset_source)}${s.asset_credit ? " by " + esc(s.asset_credit) : ""} · ${esc(s.visual_query)}</small></div>`).join("");
  const pub = r.published || {};
  const plats = [["youtube", "YouTube", CFG.youtube_connected], ["instagram", "Instagram", CFG.instagram && r.format === "short"], ["facebook", "Facebook", CFG.facebook]];
  const linkNote = (p, label) => pub[p] ? `<div class="note">${label}: published. <a href="${esc(pub[p].url)}" target="_blank" rel="noopener">${esc(pub[p].url || "open")}</a></div>` : "";
  const pickers = plats.map(([id, label, ok]) => `<label class="check"><input type="checkbox" data-plat="${id}" ${ok && !pub[id] && (CFG.defaults ? CFG.defaults[id] : true) ? "checked" : ""} ${ok ? "" : "disabled"}><span>${label}${pub[id] ? " (already published)" : !ok ? (id === "instagram" && r.format !== "short" ? " (Reels are vertical only)" : " (set up in Settings)") : ""}</span></label>`).join("");
  const errs = Object.entries(PUBERR[j.id] || {}).map(([p, e]) => `<div class="err-box">${esc(p)}: ${esc(e)}</div>`).join("");
  const up = `${linkNote("youtube", "YouTube")}${linkNote("instagram", "Instagram")}${linkNote("facebook", "Facebook")}${errs}
    <div class="stack">${pickers}</div>
    <div class="row"><select id="privacy" style="width:auto"><option value="private">YouTube: private</option><option value="unlisted">YouTube: unlisted</option><option value="public">YouTube: public</option></select>
      <button class="primary" id="publish">Publish to selected</button><span id="up-msg" class="msg"></span></div>`;
  return `
    ${r.silent_dryrun ? '<div class="note">No voice key was set, so this render has silent narration. Check the voice settings.</div>' : ""}
    <div class="detail ${long ? "long" : ""}">
      <div class="screen"><video controls src="${base}/${esc(r.video)}"></video></div>
      <div class="card">
        <h2>YOUTUBE</h2>
        <label>Title <input id="m-title" value="${esc(m.title)}"></label>
        <label>Description <textarea id="m-desc">${esc(m.description)}</textarea></label>
        <label>Tags (comma separated) <input id="m-tags" value="${esc(m.tags.join(", "))}"></label>
        <h2>INSTAGRAM</h2>
        <label>Caption <textarea id="m-igcap">${esc(m.instagram_caption || "")}</textarea></label>
        <h2>FACEBOOK</h2>
        <label>Title <input id="m-fbt" value="${esc(m.facebook_title || "")}"></label>
        <label>Description <textarea id="m-fbd">${esc(m.facebook_description || "")}</textarea></label>
        <div class="row"><button class="ghost" id="save-meta">Save changes</button><span id="meta-msg" class="msg"></span></div>
      </div>
    </div>
    <div class="card"><h2>WHAT WAS USED</h2>
      <p class="muted" style="margin:0">Mood: <strong style="color:var(--ink)">${esc(r.mood || "")}</strong> · Music: ${esc(r.music || "")} · Length: ${esc(r.duration)}s${r.quality ? " · Picture: " + esc(r.quality) : ""}${r.final_seconds ? " · " + esc(r.final_seconds) + "s of " + esc(r.time_limit) + "s allowed" : ""}${r.pov === "protagonist" ? " · Told by " + esc(r.protagonist || "the main character") : ""}${r.ai_requests != null ? " · AI requests used: " + esc(r.ai_requests) : ""}</p>
      ${(r.hook || []).length ? `<p class="muted" style="margin:0">Hook: the opening seconds use the strongest trailer scenes.</p>` : ""}
      ${(r.trailers || []).map((t) => `<p style="margin:0">Trailer for <strong>${esc(t.movie)}</strong>: <a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(t.video_title)}</a> <span class="muted">(${esc(t.channel)})${t.vertical ? " · vertical 9:16" : ""}${(t.extras || []).length ? " · plus " + t.extras.length + " official clip(s)" : ""}</span></p>`).join("")}
      ${(r.trends || []).length ? `<p class="muted" style="margin:.4rem 0 0">Popular on this topic right now (used only as ideas for the hook, never copied or used as footage):</p>` + r.trends.map((t) => `<p style="margin:0"><a href="${esc(t.url)}" target="_blank" rel="noopener">${esc(t.title)}</a> <span class="muted">(${Number(t.views).toLocaleString()} views)</span></p>`).join("") : ""}
      ${(r.warnings || []).map((w) => `<div class="note">${esc(w)}</div>`).join("")}</div>
    ${thumbs ? `<div class="card"><h2>POSTERS</h2><div class="thumbs">${thumbs}</div></div>` : ""}
    <div class="card"><h2>SCRIPT AND FOOTAGE</h2><div class="seglist">${segs}</div></div>
    <div class="card"><h2>PUBLISH</h2>${up}</div>
    <div class="row"><a class="ghost" style="text-decoration:none;color:inherit" href="${base}/${esc(r.video)}" download="${esc(m.title)}.mp4">Download MP4</a>
      <button class="ghost" id="retry">Re-run this job</button><button class="ghost danger" id="del">Delete project</button></div>`;
}

function bindDetail(j) {
  if ($("#privacy")) $("#privacy").value = CFG.yt_privacy || "private";
  $("#retry")?.addEventListener("click", async () => { await send(`/api/jobs/${j.id}/retry`, {}); lastKey = ""; loadJobs(); });
  $("#del")?.addEventListener("click", async () => {
    if (!confirm("Delete this project and its video files? Movies it used become available again.")) return;
    try { await api(`/api/jobs/${j.id}`, { method: "DELETE" }); selected = null; lastKey = ""; loadJobs(); loadUsed(); }
    catch (e) { alert(e.message); }
  });
  $$(".thumb").forEach((t) => {
    t.addEventListener("click", async () => {
      await send(`/api/jobs/${j.id}/metadata`, { selected_thumbnail: t.dataset.file }, "PATCH");
      $$(".thumb").forEach((x) => x.classList.toggle("sel", x === t));
    });
    if (!REDUCED) {
      t.addEventListener("mousemove", (e) => { const b = t.getBoundingClientRect(), x = (e.clientX - b.left) / b.width - 0.5, y = (e.clientY - b.top) / b.height - 0.5; t.style.transform = `rotateY(${x * 10}deg) rotateX(${-y * 10}deg) translateZ(6px)`; });
      t.addEventListener("mouseleave", () => (t.style.transform = ""));
    }
  });
  const saveMeta = async () => {
    const tags = $("#m-tags").value.split(",").map((s) => s.trim()).filter(Boolean);
    await send(`/api/jobs/${j.id}/metadata`, { title: $("#m-title").value, description: $("#m-desc").value, tags,
      instagram_caption: $("#m-igcap").value, facebook_title: $("#m-fbt").value, facebook_description: $("#m-fbd").value }, "PATCH");
  };
  $("#save-meta")?.addEventListener("click", async () => { await saveMeta(); $("#meta-msg").textContent = "Saved"; });
  $("#publish")?.addEventListener("click", async () => {
    const msg = $("#up-msg");
    const platforms = $$("[data-plat]").filter((c) => c.checked && !c.disabled).map((c) => c.dataset.plat);
    if (!platforms.length) { msg.className = "msg err"; msg.textContent = "Tick at least one platform."; return; }
    msg.className = "msg"; msg.innerHTML = '<span class="spin"></span> Publishing… this can take a few minutes.'; $("#publish").disabled = true;
    try {
      await saveMeta();
      const res = await send(`/api/jobs/${j.id}/publish`, { platforms, privacy: $("#privacy").value });
      PUBERR[j.id] = Object.fromEntries(Object.entries(res).filter(([, v]) => !v.ok).map(([p, v]) => [p, v.error]));
      lastKey = ""; loadJobs();
    } catch (e) { msg.className = "msg err"; msg.textContent = e.message; $("#publish").disabled = false; }
  });
}

/* ---------- movies already used ---------- */
async function loadUsed() {
  const items = await api("/api/used-movies").catch(() => []);
  $("#used-count").textContent = `(${items.length})`;
  $("#used-list").innerHTML = items.length ? items.map((m) => `
    <div class="libitem"><span>${esc(m.title)}${m.year ? " (" + esc(m.year) + ")" : ""}</span>
    <button class="ghost" data-used="${m.id}">Remove</button></div>`).join("") : `<p class="muted">Nothing yet. Movies are added automatically when a video is made.</p>`;
  $$("[data-used]").forEach((b) => b.addEventListener("click", async () => { await api(`/api/used-movies/${b.dataset.used}`, { method: "DELETE" }); loadUsed(); }));
}
$("#used-btn").addEventListener("click", async () => {
  const msg = $("#used-msg");
  try {
    const r = await send("/api/used-movies", { text: $("#used-add").value });
    msg.className = "msg ok"; msg.textContent = `Added ${r.added}${r.skipped ? ", skipped " + r.skipped + " duplicates" : ""}`; $("#used-add").value = ""; loadUsed();
  } catch (e) { msg.className = "msg err"; msg.textContent = e.message; }
});

/* ---------- footage library ---------- */
async function loadLibrary() {
  const box = $("#lib-list"); box.innerHTML = '<div class="skel"></div>';
  const items = await api("/api/library").catch(() => []);
  box.innerHTML = items.length ? items.map((a) => `
    <div class="libitem"><div><strong>${esc(a.name)}</strong><br><small class="muted">${esc(a.description)} · ${esc(a.license)}</small></div>
    <button class="ghost danger" data-del="${esc(a.name)}">Remove</button></div>`).join("")
    : `<p class="muted">Nothing here yet. Without library footage the editor uses trailers, stock clips or plain colour cards.</p>`;
  $$("[data-del]", box).forEach((b) => b.addEventListener("click", async () => { await api(`/api/library/${encodeURIComponent(b.dataset.del)}`, { method: "DELETE" }); loadLibrary(); }));
}
$("#lib-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = $("#l-file").files[0], msg = $("#lib-msg");
  if (!f) { msg.className = "msg err"; msg.textContent = "Choose a file first."; return; }
  const fd = new FormData(); fd.append("file", f); fd.append("description", $("#l-desc").value); fd.append("license", $("#l-lic").value);
  msg.className = "msg"; msg.innerHTML = '<span class="spin"></span> Uploading…';
  try { await api("/api/library", { method: "POST", body: fd }); msg.className = "msg ok"; msg.textContent = "Added"; e.target.reset(); loadLibrary(); }
  catch (err) { msg.className = "msg err"; msg.textContent = err.message; }
});

/* ---------- usage ---------- */
async function loadUsage() {
  const box = $("#usage-box"); box.innerHTML = '<div class="skel"></div><div class="skel"></div><div class="skel"></div>';
  let u; try { u = await api("/api/usage"); } catch (e) { box.innerHTML = `<div class="err-box">${esc(e.message)}</div>`; return; }
  const el = u.elevenlabs, n = (x) => Number(x).toLocaleString();
  const elText = el.error ? esc(el.error)
    : el.limit != null ? `${n(el.remaining)} of ${n(el.limit)} credits left${el.resets_unix ? " (resets " + new Date(el.resets_unix * 1000).toLocaleDateString() + ")" : ""}. Used by this app today: ${n(el.used_today)} characters`
    : `Used by this app today: ${n(el.used_today)} characters` + (u.voice_provider === "elevenlabs" ? "" : " (not your voice at the moment)");
  const est = (k, label) => { const e = u.estimate[k]; return `<strong style="font-family:var(--display);font-size:2.2rem;font-weight:400;color:var(--amber)">${e.videos}</strong> more ${label} today <span class="muted">(limited by ${esc(e.limited_by)})</span>`; };
  const g = u.gemini;
  box.innerHTML = `
    <div class="card glow"><h2>YOU CAN STILL MAKE ABOUT</h2>
      <p style="margin:0">${est("short", "40-second Shorts")}</p><p style="margin:0">${est("long", "3-4 minute videos")}</p>
      <small class="muted">A rough guide using the smallest remaining limit. Gemini is counted only if you set a daily limit in Settings.</small></div>
    <div class="card"><h2>AI REQUESTS</h2><p style="margin:0">Used today by this app: <strong>${n(g.used_today)}</strong>${g.limit ? " of " + n(g.limit) : ""}.</p>
      <p class="muted" style="margin:0">Average per video: <strong style="color:var(--ink)">${g.per_video_by_format.short}</strong> per Short, <strong style="color:var(--ink)">${g.per_video_by_format.long}</strong> per long video${(g.measured.short + g.measured.long) ? ` (measured from your last ${g.measured.short + g.measured.long} videos)` : " (a guess until you have made some)"}.</p>
      <small class="muted">Google has no API for remaining quota. See live usage at ai.dev/rate-limit.</small></div>
    <div class="card"><h2>DAILY PLAN</h2>
      <div class="grid2"><label>Shorts per day <input type="number" id="plan-s" min="0" value="${localStorage.getItem("plan-s") ?? 5}"></label>
      <label>Long videos per day <input type="number" id="plan-l" min="0" value="${localStorage.getItem("plan-l") ?? 0}"></label></div>
      <p id="plan-out" style="margin:0"></p></div>
    <div class="card"><h2>ELEVENLABS</h2><p style="margin:0">${elText}.</p>
      <small class="muted">A Short uses about ${n(el.chars_per_video.short)} characters, a long video about ${n(el.chars_per_video.long)}.</small></div>
    <div class="card"><h2>YOUTUBE UPLOADS</h2><p style="margin:0">${u.youtube.used_today} of about ${u.youtube.limit} uploads used today from this app.</p>
      <small class="muted">Exact quota: Google Cloud Console, YouTube Data API v3, Quotas.</small></div>`;
  ["#plan-s", "#plan-l"].forEach((id) => $(id).addEventListener("input", () => planUpdate(u)));
  planUpdate(u);
}
$("#usage-refresh").addEventListener("click", loadUsage);
function planUpdate(u) {
  const S = +$("#plan-s").value || 0, L = +$("#plan-l").value || 0, g = u.gemini;
  localStorage.setItem("plan-s", S); localStorage.setItem("plan-l", L);
  const need = Math.round(S * g.per_video_by_format.short + L * g.per_video_by_format.long);
  const up = S + L, lim = g.limit, ytl = u.youtube.limit;
  const ok = (!lim || need <= lim) && up <= ytl;
  $("#plan-out").innerHTML = `That plan needs about <strong>${need}</strong> AI requests and <strong>${up}</strong> uploads a day. ` +
    (lim ? `Your AI limit is ${lim}: ${need <= lim ? '<span style="color:var(--green)">fits</span>' : '<span style="color:var(--red)">too many, lower it or add another AI provider in Settings</span>'}. ` : "Set your daily AI limit in Settings to check it. ") +
    `Upload cap about ${ytl}: ${up <= ytl ? '<span style="color:var(--green)">fits</span>' : '<span style="color:var(--red)">over the cap</span>'}. ` +
    (S && L ? "Tip: make Shorts on some days and long videos on others." : "");
  void ok;
}

/* ---------- settings ---------- */
const FIELDS = {
  voice: [
    { key: "VOICE_PROVIDER", label: "Voice engine", type: "select", def: "edge", options: [["edge", "Free: Microsoft Edge voices"], ["elevenlabs", "ElevenLabs (best emotion)"], ["openai", "ChatGPT voices (OpenAI)"]] },
    { key: "EDGE_VOICE", label: "Free voice name", def: "en-US-AndrewNeural", help: "e.g. en-US-AriaNeural, en-GB-RyanNeural, en-IN-NeerjaNeural, hi-IN-MadhurNeural" },
    { key: "EDGE_VOICE_FEMALE", label: "Free voice for a female main character", def: "en-US-AriaNeural", help: "Used when a one-movie video is told by a female protagonist." },
    { key: "ELEVENLABS_API_KEY", label: "ElevenLabs API key", type: "secret" },
    { key: "ELEVENLABS_VOICE_ID", label: "ElevenLabs voice ID", def: "" },
    { key: "ELEVENLABS_MODEL", label: "ElevenLabs model", def: "eleven_v4" },
    { key: "ELEVENLABS_STABILITY", label: "ElevenLabs emotion (low = more emotional)", type: "range", min: 0, max: 1, step: 0.05, def: "0.5" },
    { key: "OPENAI_TTS_MODEL", label: "ChatGPT voice model", def: "gpt-4o-mini-tts", help: "Uses the OpenAI key from the ChatGPT card above." },
    { key: "OPENAI_TTS_VOICE", label: "ChatGPT voice", def: "alloy" },
    { key: "VOICE_FALLBACK", label: "Switch to the free voice if credits run out", type: "toggle", def: "1" },
  ],
  quality: [
    { key: "OUTPUT_RES_SHORT", label: "Shorts picture quality", type: "select", def: "4k", options: [["1080p", "1080p (fastest)"], ["1440p", "1440p"], ["4k", "4K look (best on YouTube)"]], help: "Clips are cut at 1080p; the finished video is upsized once at the end." },
    { key: "OUTPUT_RES_LONG", label: "Long video picture quality", type: "select", def: "1440p", options: [["1080p", "1080p (fastest)"], ["1440p", "1440p (recommended)"], ["4k", "4K look (slow without a graphics card)"]] },
    { key: "HW_ENCODE", label: "Use my graphics card to encode when possible", type: "toggle", def: "1", help: "Much faster 4K. Falls back to the CPU automatically." },
    { key: "TRAILER_MAX_HEIGHT", label: "Best trailer quality to download", type: "select", def: "2160", options: [["1080", "1080p (fastest)"], ["1440", "1440p"], ["2160", "4K when the trailer has it"]], help: "Lower-quality sources are upscaled to at least 1080p automatically." },
    { key: "CLIP_RES", label: "Cut clips at", type: "select", def: "1080p", options: [["1080p", "1080p (fast)"], ["match", "The final size (sharper with 4K trailers, slower)"]] },
    { key: "SHORT_SHOT_SECONDS", label: "Short: seconds per cut", type: "range", min: 1.2, max: 4, step: 0.1, def: "2.4", help: "Lower = faster cutting with more scenes." },
    { key: "LONG_SHOT_SECONDS", label: "Long video: seconds per cut", type: "range", min: 2, max: 8, step: 0.5, def: "4" },
    { key: "HOOK_SFX", label: "Bass hit on the very first frame", type: "toggle", def: "1" },
    { key: "HOOK_ENABLED", label: "Open with the strongest scenes (the hook)", type: "toggle", def: "1", help: "The first seconds use the most gripping trailer shots, cut fast." },
    { key: "HOOK_SECONDS", label: "Hook length in seconds", type: "range", min: 2, max: 8, step: 0.5, def: "4.5" },
    { key: "HOOK_STYLE", label: "What counts as a strong hook", type: "select", def: "auto", options: [["auto", "Auto: follows the video's mood"], ["balanced", "Balanced: any intense moment"], ["comedy", "Funny moments"], ["romance", "Romance, chemistry, kisses"], ["action", "Action, fights, chases"], ["shock", "Shocks, scares, big reveals"], ["emotional", "Emotional moments"]], help: "Auto picks the opening scenes to match the script mood (comedy gets funny scenes, mystery gets tense ones). Nudity and explicit scenes are always skipped." },
  ],
  footage: [
    { key: "PIXABAY_API_KEY", label: "Pixabay key (free stock clips)", type: "secret" },
    { key: "PEXELS_API_KEY", label: "Pexels key (free stock clips)", type: "secret" },
    { key: "TMDB_API_KEY", label: "TMDB key (better trailer lookup)", type: "secret" },
    { key: "OPENAI_IMAGE_MODEL", label: "AI poster model (needs OpenAI key)", def: "gpt-image-1" },
    { key: "TREND_RESEARCH", label: "Research what is already popular on the topic", type: "toggle", def: "1", help: "Reads titles and view counts of top videos so the hook uses angles that work. No AI request." },
    { key: "OFFICIAL_CLIPS_SHORTS", label: "Shorts: also add 1 official clip per movie", type: "toggle", def: "0", help: "More scenes to choose from, but slower and uses about 1 more AI request per movie." },
    { key: "OFFICIAL_CLIPS", label: "One-movie long videos: add the studio's official clips", type: "toggle", def: "1", help: "Uses official clips and featurettes from the studio or licensed channels, not only the trailer." },
    { key: "DESCRIBE_TRAILER_SCENES", label: "AI describes each trailer scene", type: "toggle", def: "1", help: "Better scene matching, but uses many AI requests. Turn off to save quota." },
    { key: "PREFER_VERTICAL_TRAILERS", label: "Shorts: look for an official vertical clip first", type: "toggle", def: "1" },
    { key: "SHORT_PAN", label: "Shorts: slow pan across zoomed footage", type: "toggle", def: "1" },
    { key: "SHORT_FILL", label: "Shorts: how much of the screen the footage fills", type: "range", min: 0.5, max: 1, step: 0.05, def: "0.8" },
    { key: "SHORT_THUMBNAILS", label: "Make posters (thumbnails) for Shorts too", type: "toggle", def: "0", help: "Off saves time and AI requests." },
  ],
  length: [
    { key: "SHORT_TARGET_WORDS", label: "Short: target words", type: "number", def: "94", help: "About 2.5 spoken words a second: 94 words is about 38-40 seconds." },
    { key: "SHORT_MAX_WORDS", label: "Short: hard maximum", type: "number", def: "104" },
    { key: "SHORT_SEGMENTS", label: "Short: number of parts", def: "5", help: "5 = hook, 3 movies, outro." },
    { key: "SINGLE_TARGET_WORDS", label: "One-movie Short: target words", type: "number", def: "50", help: "About 20 seconds." },
    { key: "SINGLE_MAX_WORDS", label: "One-movie Short: hard maximum", type: "number", def: "58" },
    { key: "SINGLE_SEGMENTS", label: "One-movie Short: number of parts", def: "3", help: "3 = hook, the film, outro." },
    { key: "SHORT_MAX_SECONDS", label: "Short (list): must end within (seconds)", type: "number", def: "30", help: "If the voice runs longer it is sped up, at most 1.2x." },
    { key: "SINGLE_MAX_SECONDS", label: "One-movie Short: must end within (seconds)", type: "number", def: "20" },
    { key: "LONG_MAX_SECONDS", label: "Long video: must end within (seconds)", type: "number", def: "180" },
    { key: "LONG_TARGET_WORDS", label: "Long video: target words", type: "number", def: "500", help: "The voice speaks about 2.5 words a second, so 500 words is about 3.3 minutes." },
    { key: "LONG_MAX_WORDS", label: "Long video: hard maximum", type: "number", def: "580" },
  ],
  publish: [
    { key: "PUBLISH_YOUTUBE", label: "Tick YouTube by default", type: "toggle", def: "1" },
    { key: "PUBLISH_INSTAGRAM", label: "Tick Instagram by default", type: "toggle", def: "1" },
    { key: "PUBLISH_FACEBOOK", label: "Tick Facebook by default", type: "toggle", def: "1" },
    { key: "YT_PRIVACY", label: "YouTube privacy by default", type: "select", def: "private", options: [["private", "Private"], ["unlisted", "Unlisted"], ["public", "Public"]] },
  ],
  social: [
    { key: "META_ACCESS_TOKEN", label: "Meta access token (Page token)", type: "secret" },
    { key: "FB_PAGE_ID", label: "Facebook Page ID", def: "" },
    { key: "IG_USER_ID", label: "Instagram account ID", def: "" },
    { key: "META_GRAPH_VERSION", label: "Meta API version", def: "v25.0", help: "If Meta says the version is too old, use the newest one from developers.facebook.com." },
  ],
  audio: [
    { key: "MUSIC_SOURCE", label: "Background music source", type: "select", def: "auto", options: [["auto", "Your tracks, else free real music, else generated"], ["library", "Only my tracks (else generated)"], ["generated", "Always generated"]], help: "Put your own mp3s in assets/music/<mood>/ (for example horror). Free tracks are downloaded once and kept there, named auto_..." },
    { key: "MUSIC_VOLUME", label: "Background music level", type: "range", min: 0.05, max: 0.4, step: 0.01, def: "0.15", help: "0.10 to 0.15 sits quietly under the voice." },
    { key: "VOICE_LUFS", label: "Voice loudness (LUFS)", type: "range", min: -20, max: -12, step: 1, def: "-15", help: "-14 is YouTube's level (loud). -16 is softer." },
  ],
  limits: [
    { key: "BUDGET_MODE", label: "Save AI requests (recommended)", type: "toggle", def: "1", help: "Larger batches, fewer retries, no extra poster-ranking request. Lets you make more videos a day on free plans." },
    { key: "RANK_THUMBNAILS", label: "Extra AI request to rank posters", type: "toggle", def: "0", help: "Off: the poster ideas already come with a click prediction." },
    { key: "GEMINI_DAILY_LIMIT", label: "Your Gemini daily request limit", type: "number", def: "0", help: "From ai.dev/rate-limit. 0 means unknown." },
    { key: "YOUTUBE_DAILY_UPLOADS", label: "YouTube uploads per day", type: "number", def: "6" },
    { key: "WORKER_THREADS", label: "Videos rendered at the same time", type: "number", def: "1", help: "Restart needed for this one." },
    { key: "GEMINI_TIMEOUT", label: "Seconds to wait for one AI answer", type: "number", def: "600" },
  ],
};
const SECTION_TITLES = { social: ["SOCIAL ACCOUNTS", "Instagram and Facebook one-click publishing"], quality: ["PICTURE AND HOOK", "How good it looks and how it opens"], voice: ["VOICE", "How your videos sound"], footage: ["FOOTAGE AND POSTERS", "Where scenes come from"], length: ["VIDEO LENGTH", "How long scripts are"], audio: ["AUDIO MIX", "Voice against background music"], limits: ["LIMITS", "Used for the Usage page"] };

let SET = null, state = { all: [], enabled: new Set(), open: new Set() }, dirty = {}, rulesDirty = false, rulesSingleDirty = false, rulesLongDirty = false;

async function loadSettings() {
  $("#settings-box").innerHTML = '<div class="skel"></div><div class="skel" style="margin-top:.7rem"></div><div class="skel" style="margin-top:.7rem"></div>';
  try { SET = await api("/api/settings"); } catch (e) { $("#settings-box").innerHTML = `<div class="err-box">${esc(e.message)}</div>`; return; }
  dirty = {}; rulesDirty = false; rulesSingleDirty = false; rulesLongDirty = false;
  const order = [...SET.order];
  state.enabled = new Set(order);
  state.open = new Set(order.slice(0, 1));
  state.all = [...order, ...SET.providers.map((p) => p.id).filter((id) => !order.includes(id))];
  renderSettings();
}

function fieldHTML(f) {
  const cur = SET.values[f.key] || "";
  const val = dirty[f.key] ?? (cur !== "" ? cur : f.def ?? "");
  if (f.type === "toggle") return `<label class="check"><input type="checkbox" data-key="${f.key}" data-kind="toggle" ${val === "1" || val === true ? "checked" : ""}><span><strong>${esc(f.label)}</strong>${f.help ? `<br><span class="field-help">${esc(f.help)}</span>` : ""}</span></label>`;
  if (f.type === "secret") { const has = SET.secrets[f.key]; return `<label>${esc(f.label)} ${has ? '<span class="tag ready">saved ' + esc(has) + "</span>" : ""}<input type="password" autocomplete="off" data-key="${f.key}" data-kind="secret" placeholder="${has ? "Type to replace" : "Paste your key"}"></label>`; }
  if (f.type === "select") return `<label>${esc(f.label)}<select data-key="${f.key}">${f.options.map(([v, t]) => `<option value="${v}" ${v === val ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
  if (f.type === "range") return `<label>${esc(f.label)}: <b data-out="${f.key}">${esc(val)}</b><input type="range" data-key="${f.key}" min="${f.min}" max="${f.max}" step="${f.step}" value="${esc(val)}">${f.help ? `<span class="field-help">${esc(f.help)}</span>` : ""}</label>`;
  return `<label>${esc(f.label)}<input data-key="${f.key}" ${f.type === "number" ? 'type="number"' : ""} value="${esc(val)}">${f.help ? `<span class="field-help">${esc(f.help)}</span>` : ""}</label>`;
}
function sectionHTML(id) {
  const [title, sub] = SECTION_TITLES[id];
  const extra = id === "voice" ? `<div class="row"><button class="ghost" id="try-voice" type="button">▶ Hear the current voice</button><span class="msg" id="voice-msg"></span><audio id="voice-audio" controls hidden></audio></div>`
    : id === "social" ? `<p class="field-help" style="margin:0">Needs a Meta developer app, a Facebook Page and an Instagram professional account linked to it. Step by step in the README. YouTube uses its own login (client_secret.json).</p><div class="row"><button class="ghost" id="try-social" type="button">Test connection</button><span class="msg" id="social-msg"></span></div><div id="social-detail" class="stack"></div>` : "";
  return `<div class="sec-title"><h2>${title}</h2><span>${sub}</span></div>
    <div class="card"><div class="grid2">${FIELDS[id].map(fieldHTML).join("")}</div>${extra}</div>`;
}

function uploadHTML() {
  const yt = `<div class="card" id="yt-card"><div class="row" style="justify-content:space-between"><h2>YOUTUBE</h2><span class="tag need" id="yt-chip">checking…</span></div>
    <p class="field-help" style="margin:0">1) In Google Cloud, create an OAuth client of type "Desktop app" and download its JSON (steps are in the README). 2) Choose that file here. 3) Press Connect and sign in with the channel's Google account in the window that opens on this PC.</p>
    <div class="row"><input type="file" id="yt-file" accept=".json" style="flex:1;min-width:200px"><button class="ghost" id="yt-upload" type="button">Upload client_secret.json</button></div>
    <div class="row"><button class="primary" id="yt-connect" type="button">Connect YouTube</button><button class="ghost danger" id="yt-disconnect" type="button">Disconnect</button><span class="msg" id="yt-msg"></span></div></div>`;
  const social = `<div class="card"><h2>FACEBOOK AND INSTAGRAM</h2><div class="grid2">${FIELDS.social.map(fieldHTML).join("")}</div>
    <p class="field-help" style="margin:0">Needs a Meta developer app, a Facebook Page and an Instagram professional account linked to it. Step by step in the README.</p>
    <div class="row"><button class="ghost" id="try-social" type="button">Test connection</button><span class="msg" id="social-msg"></span></div><div id="social-detail" class="stack"></div></div>`;
  const defs = `<div class="card"><h2>PUBLISH DEFAULTS</h2><div class="grid2">${FIELDS.publish.map(fieldHTML).join("")}</div></div>`;
  return `<div class="sec-title"><h2>UPLOAD ACCOUNTS</h2><span>YouTube, Instagram and Facebook: set up once, then publish with one click</span></div><div class="stack">${yt}${social}${defs}</div>`;
}

function renderSettings() {
  $("#settings-box").innerHTML = `
    <div class="sec-title"><h2>AI WRITERS</h2><span>Tried top to bottom until one answers. Turn on as many as you like.</span></div>
    <div class="stack" id="prov-list"></div>
    ${["quality", "voice", "footage", "length", "audio"].map(sectionHTML).join("")}${uploadHTML()}${["limits"].map(sectionHTML).join("")}
    <div class="sec-title"><h2>SCRIPT STYLE</h2><span>Your own rules for every script</span></div>
    <div class="card"><label>Several movies (lists)<textarea id="script-rules" style="min-height:9rem" placeholder="Your rules for lists of movies">${esc(SET.script_rules || "")}</textarea></label>
    <span class="field-help">Added to the writer's instructions. Saved to script_rules.txt.</span></div>
    <div class="card" style="margin-top:1rem"><label>One-movie Shorts<textarea id="script-rules-single" style="min-height:9rem" placeholder="Your rules for a single-movie Short">${esc(SET.script_rules_single || "")}</textarea></label>
    <span class="field-help">Used for Shorts about one movie. Saved to script_rules_single.txt.</span></div>
    <div class="card" style="margin-top:1rem"><label>Long videos<textarea id="script-rules-long" style="min-height:9rem" placeholder="Your rules for long videos">${esc(SET.script_rules_long || "")}</textarea></label>
    <span class="field-help">Used for long videos. Saved to script_rules_long.txt.</span></div>`;
  renderProviders();
  bindSettings();
}

function provHTML(p, i) {
  const on = state.enabled.has(p.id), has = SET.secrets[p.key_name];
  const isGem = p.kind === "gemini", isCustom = !!p.base_env;
  const model = dirty[p.model_name] ?? SET.values[p.model_name] ?? "";
  return `<div class="prov ${on ? "on" : ""} ${state.open.has(p.id) ? "open" : ""}" data-pid="${p.id}">
    <div class="badge2">${esc(p.label[0])}</div>
    <div class="head"><div><b>${esc(p.label)}</b> ${p.free ? '<span class="tag free">free tier</span>' : ""} <span class="tag ${p.ready ? "ready" : "need"}">${p.ready ? "ready" : "needs setup"}</span></div>
      <div class="ctl"><button class="ghost" data-act="toggle" type="button">${state.open.has(p.id) ? "Hide" : "Set up"}</button><button class="ghost" data-act="up" type="button" title="Higher priority" ${i === 0 ? "disabled" : ""}>↑</button><button class="ghost" data-act="down" type="button" title="Lower priority">↓</button>
        <label class="check" style="gap:.4rem;align-items:center"><input type="checkbox" data-act="enable" ${on ? "checked" : ""}><span>Use</span></label></div></div>
    <div class="body">
      <label>API key ${has ? '<span class="tag ready">saved ' + esc(has) + "</span>" : ""}<input type="password" autocomplete="off" data-key="${p.key_name}" data-kind="secret" placeholder="${has ? "Type to replace" : "Paste your key"}"></label>
      ${isCustom ? `<label>Base URL<input data-key="${p.base_env}" value="${esc(dirty[p.base_env] ?? SET.values[p.base_env] ?? "")}" placeholder="https://api.example.com/v1"></label>` : ""}
      <label>Model <span class="field-help">${p.kind === "gemini" ? "e.g. gemini-flash-latest" : "press Load models to see what your key can use"}</span>
        <div class="row" style="flex-wrap:nowrap"><input list="models-${p.id}" data-key="${p.model_name}" value="${esc(model)}" placeholder="model name"><datalist id="models-${p.id}">${(MODELS[p.id] || []).map((m) => `<option value="${esc(m)}"></option>`).join("")}</datalist><button class="ghost" data-act="models" type="button">Load models</button></div></label>
      ${isGem ? `<label>Backup Gemini models <span class="field-help">comma separated; used when the main one's free quota runs out</span><input data-key="GEMINI_FALLBACK_MODELS" value="${esc(dirty.GEMINI_FALLBACK_MODELS ?? SET.values.GEMINI_FALLBACK_MODELS ?? "")}"></label>` : ""}
      ${p.id === "openai" ? '<span class="field-help">This same key also powers ChatGPT voices and AI posters.</span>' : ""}
      <div class="row"><button class="ghost" data-act="test" type="button">Save and test</button><span class="msg" data-role="result"></span></div>
    </div></div>`;
}
function renderProviders() {
  const list = $("#prov-list");
  list.innerHTML = state.all.map((id, i) => provHTML(SET.providers.find((p) => p.id === id), i)).join("");
}

function collect() {
  const values = { ...dirty };
  values.LLM_PROVIDERS = state.all.filter((id) => state.enabled.has(id)).join(",");
  return values;
}
async function saveSettings(quiet) {
  const msg = $("#set-msg");
  try {
    await send("/api/settings", { values: collect(), script_rules: rulesDirty ? $("#script-rules").value : null, script_rules_single: rulesSingleDirty ? $("#script-rules-single").value : null, script_rules_long: rulesLongDirty ? $("#script-rules-long").value : null });
    const cfgp = loadConfig();
    const fresh = await api("/api/settings");
    SET = fresh; dirty = {}; rulesDirty = false; rulesSingleDirty = false; rulesLongDirty = false;
    if (!quiet) { msg.className = "msg ok"; msg.textContent = "Saved. New settings are active now."; }
    await cfgp;
    return true;
  } catch (e) { msg.className = "msg err"; msg.textContent = e.message; return false; }
}
$("#set-save").addEventListener("click", async () => {
  const btn = $("#set-save"); btn.disabled = true;
  const ok = await saveSettings(false);
  if (ok) renderSettings();
  btn.disabled = false;
});

let MODELS = {};
function resultLine(id, cls, text) {
  const n = $(`.prov[data-pid="${id}"] [data-role="result"]`);
  if (n) { n.className = "msg " + cls; n.textContent = text; }
}
function initSettingsListeners() {
  const box = $("#settings-box");
  box.addEventListener("input", (e) => {
    const t = e.target;
    if (t.id === "script-rules") { rulesDirty = true; return; }
    if (t.id === "script-rules-single") { rulesSingleDirty = true; return; }
    if (t.id === "script-rules-long") { rulesLongDirty = true; return; }
    const key = t.dataset.key; if (!key) return;
    const v = t.type === "checkbox" ? (t.checked ? "1" : "0") : t.value;
    if (t.dataset.kind === "secret" && v === "") { delete dirty[key]; return; }
    dirty[key] = v;
    const out = $(`[data-out="${key}"]`); if (out) out.textContent = v;
  });
  box.addEventListener("change", (e) => {
    const t = e.target;
    if (t.dataset.key && t.tagName === "SELECT") dirty[t.dataset.key] = t.value;
    if (t.dataset.act === "enable") {
      const card = t.closest(".prov"), id = card.dataset.pid;
      t.checked ? state.enabled.add(id) : state.enabled.delete(id);
      card.classList.toggle("on", t.checked);
    }
  });
  box.addEventListener("click", async (e) => {
    const head = e.target.closest(".prov .head");
    if (head && !e.target.closest(".ctl")) { const id = head.closest(".prov").dataset.pid; state.open.has(id) ? state.open.delete(id) : state.open.add(id); renderProviders(); return; }
    const btn = e.target.closest("button[data-act]"); if (!btn) return;
    const card = btn.closest(".prov"), id = card?.dataset.pid, act = btn.dataset.act;
    if (act === "toggle") { state.open.has(id) ? state.open.delete(id) : state.open.add(id); renderProviders(); return; }
    if (act === "up" || act === "down") {
      const i = state.all.indexOf(id), j = act === "up" ? i - 1 : i + 1;
      if (j < 0 || j >= state.all.length) return;
      [state.all[i], state.all[j]] = [state.all[j], state.all[i]];
      renderProviders(); return;
    }
    if (act !== "test" && act !== "models") return;
    state.open.add(id); resultLine(id, "", ""); $('[data-role="result"]', card).innerHTML = `<span class="spin"></span> ${act === "test" ? "Saving and testing…" : "Loading models…"}`;
    btn.disabled = true;
    if (!(await saveSettings(true))) { resultLine(id, "err", "Could not save your changes first."); btn.disabled = false; return; }
    let cls = "ok", text = "";
    try {
      if (act === "test") {
        const r = await send("/api/test/ai", { provider: id });
        cls = r.ok ? "ok" : "err"; text = r.ok ? `Works! Answered in ${r.ms} ms.` : (r.error || "No answer.");
      } else {
        const r = await api(`/api/models/${id}`);
        MODELS[id] = r.models; text = `${r.models.length} models found. Click the Model box and pick one.`;
      }
    } catch (err) { cls = "err"; text = err.message; }
    renderProviders(); resultLine(id, cls, text);
  });
}
function bindSettings() {
  const chip = $("#yt-chip");
  const showYT = (s) => {
    chip.className = "tag " + (s.connected ? "ready" : "need");
    chip.textContent = s.connected ? "connected" : s.connecting ? "waiting for sign-in" : s.has_secret ? "ready to connect" : "needs client_secret.json";
    const m = $("#yt-msg"); m.className = "msg" + (s.error ? " err" : ""); m.textContent = s.error || (s.connecting ? "A Google sign-in window opened on this PC. Finish it there." : "");
  };
  const pollYT = async () => { const s = await api("/api/youtube/status"); showYT(s); if (s.connecting) setTimeout(pollYT, 2000); else if (s.connected) loadConfig(); };
  pollYT().catch(() => {});
  $("#yt-upload")?.addEventListener("click", async () => {
    const f = $("#yt-file").files[0], m = $("#yt-msg");
    if (!f) { m.className = "msg err"; m.textContent = "Choose the downloaded JSON file first."; return; }
    const fd = new FormData(); fd.append("file", f);
    try { showYT(await api("/api/youtube/secret", { method: "POST", body: fd })); m.className = "msg ok"; m.textContent = "Saved. Now press Connect YouTube."; }
    catch (e) { m.className = "msg err"; m.textContent = e.message; }
  });
  $("#yt-connect")?.addEventListener("click", async () => {
    try { showYT(await send("/api/youtube/connect", {})); setTimeout(pollYT, 2000); }
    catch (e) { const m = $("#yt-msg"); m.className = "msg err"; m.textContent = e.message; }
  });
  $("#yt-disconnect")?.addEventListener("click", async () => { showYT(await send("/api/youtube/disconnect", {})); loadConfig(); });
  const ts = $("#try-social");
  ts?.addEventListener("click", async () => {
    const m = $("#social-msg"), d = $("#social-detail"); m.className = "msg"; m.innerHTML = '<span class="spin"></span> Saving and checking…'; ts.disabled = true;
    if (await saveSettings(true)) {
      try {
        const r = await send("/api/test/social", {});
        d.innerHTML = Object.entries(r).map(([k, v]) => `<div class="${v.ok ? "note" : "err-box"}">${esc(k)}: ${v.ok ? "OK " + esc(v.detail || "") : esc(v.error || v.detail || "failed")}</div>`).join("");
        m.textContent = "";
      } catch (e) { m.className = "msg err"; m.textContent = e.message; }
    }
    ts.disabled = false;
  });
  const tv = $("#try-voice");
  tv?.addEventListener("click", async () => {
    const m = $("#voice-msg"), a = $("#voice-audio"); m.className = "msg"; m.innerHTML = '<span class="spin"></span> Saving and generating…'; tv.disabled = true;
    if (await saveSettings(true)) {
      try {
        const r = await send("/api/test/voice", {});
        if (r.ok) { a.hidden = false; a.src = r.url; a.play().catch(() => {}); m.className = "msg ok"; m.textContent = `Voice works (${r.provider}).`; }
        else { m.className = "msg err"; m.textContent = r.error; }
      } catch (e) { m.className = "msg err"; m.textContent = e.message; }
    }
    tv.disabled = false;
  });
}

/* ---------- go ---------- */
initSettingsListeners();
loadConfig().then(loadStats).catch(() => {});
