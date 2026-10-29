// Landing page: every app of the Badge Studio store, read live from GitHub.
// Same sources and the same tree cache as docs/studio/studio.js.

"use strict";

const SOURCES = [
  { id: "official", label: "Official", repo: "badger/home", branch: "main", base: "badge/apps" },
  { id: "akiyo", label: "Akiyo974", repo: "Akiyo974/badger", branch: "main", base: "system/apps" },
];
const SKIP_APPS = new Set(["menu", "startup", "system", "mass_storage", "settings"]);
const MODDED = new Set(["badge", "contacts", "mona_pet"]);
// Screenshots taken on the badge (docs/screenshots)
const SHOTS = {
  badge: "badge.png", contacts: "contacts.png", radar: "radar.png", duck_maze: "duck-maze.png",
  pedometer: "pedometer.png", mona_pet: "mona_pet.png", snake: "snake.png", pong: "pong.png",
  merge_conflict: "merge_conflict.png", flappy_mona: "flappy_mona.png", mona_paint: "mona_paint.png",
  rogue: "rogue.png", brattal: "brattal.png", life: "life.png", iss: "iss.png",
};

const $ = (selector) => document.querySelector(selector);
const encoder = new TextEncoder();

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function titleCase(slug) {
  return slug.split("_").map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w)).join(" ");
}

function rawUrl(source, path) {
  return `https://raw.githubusercontent.com/${source.repo}/${source.branch}/${source.base}/${path}`;
}

async function tree(source) {
  const key = "studio-tree-" + source.id;
  try {
    const cached = JSON.parse(sessionStorage.getItem(key) || "null");
    if (cached && Date.now() - cached.at < 10 * 60 * 1000) return cached.tree;
  } catch (_) {}
  const response = await fetch(`https://api.github.com/repos/${source.repo}/git/trees/${source.branch}?recursive=1`);
  if (!response.ok) throw new Error(`GitHub answered ${response.status}`);
  const entries = (await response.json()).tree.filter((e) => e.type === "blob" && e.path.startsWith(source.base + "/"));
  try { sessionStorage.setItem(key, JSON.stringify({ at: Date.now(), tree: entries })); } catch (_) {}
  return entries;
}

// The apps of one source: the folders with an __init__.py
async function catalogue(source) {
  const apps = {};
  for (const entry of await tree(source)) {
    const [slug, ...rest] = entry.path.slice(source.base.length + 1).split("/");
    if (!rest.length || SKIP_APPS.has(slug)) continue;
    if (rest.some((part) => part.startsWith(".") || part === "__pycache__")) continue;
    (apps[slug] ||= { slug, files: [] }).files.push({ path: rest.join("/"), sha: entry.sha });
  }
  const list = Object.values(apps).filter((app) => app.files.some((f) => f.path === "__init__.py"));
  for (const app of list) {
    app.icon = app.files.some((f) => f.path === "icon.png") ? rawUrl(source, app.slug + "/icon.png") : null;
    app.readme = app.files.find((f) => f.path.toLowerCase() === "readme.md");
  }
  return list;
}

async function describe(source, app, el) {
  if (!app.readme) return;
  try {
    const key = "studio-readme-" + source.id + "-" + app.slug + "-" + app.readme.sha;
    let text = sessionStorage.getItem(key);
    if (text === null) {
      text = await (await fetch(rawUrl(source, app.slug + "/" + app.readme.path))).text();
      try { sessionStorage.setItem(key, text); } catch (_) {}
    }
    const paragraph = text.split(/\n\s*\n/).map((p) => p.trim()).find((p) => p && !p.startsWith("#") && !p.startsWith("!") && !p.startsWith("<") && !p.startsWith("|")) || "";
    el.textContent = paragraph.replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/[*_`]/g, "").slice(0, 150);
  } catch (_) {}
}

let apps = [];

async function load() {
  const box = $("#market");
  try {
    const [official, mine] = await Promise.all(SOURCES.map(catalogue));
    const byOfficial = new Map(official.map((a) => [a.slug, a]));
    const byMine = new Map(mine.map((a) => [a.slug, a]));
    const slugs = [...new Set([...byOfficial.keys(), ...byMine.keys()])];
    apps = slugs.map((slug) => {
      const o = byOfficial.get(slug), m = byMine.get(slug);
      // An app of this repo that the official one does not have was made here.
      // system/ also holds the stock apps as shipped: only MODDED were changed
      const kind = !o ? "new" : MODDED.has(slug) ? "modded" : "official";
      const app = (kind !== "official" && m) || o || m;
      return { slug, kind, app, source: app === m ? SOURCES[1] : SOURCES[0] };
    });
    // The apps made or changed here first, then the ones with a screenshot
    const rank = (a) => (a.kind === "official" ? 2 : 0) + (SHOTS[a.slug] ? 0 : 1);
    apps.sort((a, b) => rank(a) - rank(b) || a.slug.localeCompare(b.slug));
    $("#market-count").textContent = apps.length;
    render();
  } catch (error) {
    box.innerHTML = `<p class="muted">The store could not be loaded (${escapeHtml(error.message)}). It is in <a href="studio/">Badge Studio</a>.</p>`;
  }
}

function render() {
  const box = $("#market");
  const filter = document.querySelector("#market-filter .on")?.dataset.filter || "all";
  const query = $("#market-search").value.trim().toLowerCase();
  box.innerHTML = "";
  for (const item of apps) {
    if (filter === "here" && item.kind === "official") continue;
    if (filter === "official" && item.kind === "new") continue;
    if (query && !item.slug.replace(/_/g, " ").toLowerCase().includes(query)) continue;
    const card = document.createElement("a");
    card.className = "app";
    card.href = `studio/#app=${item.source.id}/${encodeURIComponent(item.slug)}`;
    const shot = SHOTS[item.slug];
    const picture = shot
      ? `<img class="shot" loading="lazy" src="screenshots/${shot}" alt="">`
      : `<div class="shot tile">${item.app.icon ? `<img loading="lazy" src="${item.app.icon}" alt="">` : `<span>${escapeHtml(titleCase(item.slug)[0])}</span>`}</div>`;
    const tag = { official: "", modded: `<span class="tag mod">modded here</span>`, new: `<span class="tag new">made here</span>` }[item.kind];
    card.innerHTML = `${picture}<div class="body"><div class="name">${escapeHtml(titleCase(item.slug))}${tag}</div><div class="desc"></div><div class="go">Install →</div></div>`;
    box.appendChild(card);
    describe(item.source, item.app, card.querySelector(".desc"));
  }
  if (!box.children.length) box.innerHTML = `<p class="muted">No app matches.</p>`;
}

for (const button of document.querySelectorAll("#market-filter button")) {
  button.onclick = () => {
    document.querySelectorAll("#market-filter button").forEach((b) => b.classList.toggle("on", b === button));
    render();
  };
}
$("#market-search").oninput = render;
load();
