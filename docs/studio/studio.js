// Badge Studio: manage a GitHub Universe badge over Web Serial.
// Every command goes to the MicroPython REPL as one base64-encoded exec(),
// followed by a unique marker, so the answer of each command is read in full
// and a MicroPython error is reported instead of being mistaken for output.

"use strict";

const USB_FILTER = { usbVendorId: 0x2e8a, usbProductId: 0x1101 };
const INSTALL_ROOT = "/apps";
const STAGING_ROOT = "/.studio-staging";
const BUILT_IN_ROOT = "/system/apps";
const WRITE_CHUNK = 1536;
const SHOT_CHUNK = 3072;
const MAX_APP_BYTES = 600 * 1024;
const SKIP_APPS = new Set(["menu", "startup", "system", "mass_storage", "settings"]);
const SOURCES = [
  { id: "official", label: "Official badge apps (badger/home)", repo: "badger/home", branch: "main", base: "badge/apps" },
  { id: "akiyo", label: "Akiyo974/badger apps", repo: "Akiyo974/badger", branch: "main", base: "system/apps" },
];
const SETTINGS = [
  ["WIFI_SSID", "Wi-Fi network", "text", "2.4 GHz only"],
  ["WIFI_PASSWORD", "Wi-Fi password", "password", "Left empty, it stays as it is"],
  ["GITHUB_USERNAME", "GitHub username", "text", "Badge stats and the Last push line"],
  ["CONTACT_NAME", "Name", "text", "Contact card and NFC"],
  ["CONTACT_LINKEDIN", "LinkedIn", "text", "Username or full link"],
  ["CONTACT_WEBSITE", "Website", "text", "Contact card, NFC and QR"],
  ["CONTACT_TITLE", "Job title", "text", "NFC contact card"],
  ["CONTACT_COMPANY", "Company", "text", "NFC contact card"],
  ["NFC_CARD", "NFC tag content", "select:vcard,link", "Contact card, or the website link only"],
  ["RADAR_STATUS", "Radar status", "text", "Name + status: 25 bytes in total"],
  ["STEPS_GOAL", "Daily steps goal", "number", "Pedometer app"],
  ["WATCH_REMOTE", "Watch remote", "select:True,False", "Badger Remote over Bluetooth"],
];

// Helpers defined once on the badge after connecting
const HELPERS = `
import os, sys, gc, json, binascii
def _st_out(value):
    print("@@json " + json.dumps(value))
def _st_isdir(path):
    try:
        return os.stat(path)[0] & 0x4000 != 0
    except OSError:
        return False
def _st_ls(path):
    try:
        return [(e[0], e[1] == 0x4000) for e in os.ilistdir(path)]
    except OSError:
        return []
def _st_size(path):
    total = 0
    for name, folder in _st_ls(path):
        full = path + "/" + name
        total += _st_size(full) if folder else os.stat(full)[6]
    return total
def _st_rm(path):
    if _st_isdir(path):
        for name, folder in _st_ls(path):
            _st_rm(path + "/" + name)
        os.rmdir(path)
    else:
        try:
            os.remove(path)
        except OSError:
            pass
def _st_mkdirs(path):
    built = ""
    for part in path.strip("/").split("/"):
        built += "/" + part
        if not _st_isdir(built):
            os.mkdir(built)
def _st_write(path, b64, mode):
    f = open(path, mode)
    f.write(binascii.a2b_base64(b64))
    f.close()
def _st_check(path):
    crc = 0
    size = 0
    f = open(path, "rb")
    while True:
        data = f.read(2048)
        if not data:
            break
        size += len(data)
        crc = binascii.crc32(data, crc)
    f.close()
    return size, crc
def _st_read_b64(path):
    f = open(path, "rb")
    data = f.read()
    f.close()
    return binascii.b2a_base64(data).decode().strip()
def _st_secrets():
    here = os.getcwd()
    os.chdir("/rom")
    sys.modules.pop("secrets", None)
    import secrets
    os.chdir(here)
    return secrets
`;

// ---------- small utilities ----------

const $ = (selector) => document.querySelector(selector);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const encoder = new TextEncoder();

function toast(message, ms = 3200) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.remove("show"), ms);
}

function bytesToBase64(bytes) {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

function base64ToBytes(b64) {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    table[n] = c >>> 0;
  }
  return table;
})();

function crc32(bytes) {
  let crc = 0xffffffff;
  for (let i = 0; i < bytes.length; i++) crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function pyString(value) {
  return JSON.stringify(String(value));
}

function formatBytes(n) {
  if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " MB";
  if (n >= 1024) return Math.round(n / 1024) + " KB";
  return n + " B";
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function titleCase(slug) {
  return slug.split("_").map((w) => (w ? w[0].toUpperCase() + w.slice(1) : w)).join(" ");
}

// ---------- the serial link ----------

class Badge {
  constructor() {
    this.port = null;
    this.writer = null;
    this.buffer = "";
    this.queue = Promise.resolve();
    this.commandId = 0;
    this.waiter = null;
    this.busy = 0;
    this.onText = null;
    this.onState = null;
  }

  get connected() {
    return !!this.writer;
  }

  async connect(port) {
    this.port = port || (await navigator.serial.requestPort({ filters: [USB_FILTER] }));
    this.closing = false;
    await this.port.open({ baudRate: 115200, bufferSize: 1 << 20 });
    try {
      await this.port.setSignals({ dataTerminalReady: true });
    } catch (_) {}
    this.writer = this.port.writable.getWriter();
    this.reading = this.readLoop();
    await this.interrupt();
    await this.run(HELPERS);
    this.state("ok", "connected");
  }

  async disconnect() {
    await this.teardown();
    this.state("", "not connected");
  }

  // Ends the read loop, frees both stream locks and closes the port
  async teardown() {
    this.closing = true;
    try { await this.reader?.cancel(); } catch (_) {}
    try { await this.reading; } catch (_) {}
    try { this.writer?.releaseLock(); } catch (_) {}
    this.writer = null;
    try { await this.port?.close(); } catch (_) {}
  }

  state(kind, text) {
    this.onState && this.onState(kind, text);
  }

  async readLoop() {
    const decoder = new TextDecoder();
    try {
      while (this.port.readable) {
        this.reader = this.port.readable.getReader();
        try {
          while (true) {
            const { value, done } = await this.reader.read();
            if (done) break;
            const text = decoder.decode(value, { stream: true });
            // Only a waiting command needs the text; the console keeps its own copy
            if (this.waiter) this.buffer += text;
            if (!this.busy && this.onText) this.onText(text);
            this.check();
          }
        } finally {
          this.reader.releaseLock();
        }
      }
    } catch (error) {
      // The badge reboots after an app exits or on reset: the port goes away
    }
    try { this.writer?.releaseLock(); } catch (_) {}
    this.writer = null;
    if (this.waiter) this.waiter.reject(new Error("The badge disconnected."));
    if (this.closing) {
      this.closing = false;
      return;
    }
    this.state("err", "disconnected");
  }

  write(text) {
    return this.writer.write(encoder.encode(text));
  }

  async interrupt() {
    await this.write("\x03");
    await sleep(350);
    await this.write("\x03");
    await sleep(350);
    this.buffer = "";
  }

  check() {
    const w = this.waiter;
    if (!w) return;
    const text = this.buffer.slice(w.start);
    const marker = text.search(w.pattern);
    if (marker >= 0) {
      this.waiter = null;
      // Drop the echoed command line, keep what the code printed
      const echoEnd = text.indexOf("\n");
      w.resolve(text.slice(echoEnd >= 0 && echoEnd < marker ? echoEnd + 1 : 0, marker));
      this.buffer = this.buffer.slice(w.start + marker);
      return;
    }
    const failure = text.match(/Traceback \(most recent call last\):[\s\S]*?(?=\r?\n>>> $)/);
    if (failure) {
      this.waiter = null;
      w.reject(new Error(failure[0].trim()));
    }
  }

  // Runs code and resolves with what it printed. Commands never overlap.
  run(code, timeout = 30000) {
    const job = this.queue.then(() => this.runNow(code, timeout));
    this.queue = job.catch(() => {});
    return job;
  }

  runNow(code, timeout) {
    if (!this.connected) return Promise.reject(new Error("Badge not connected."));
    const id = ++this.commandId;
    const marker = `@@done-${id}@@`;
    const b64 = bytesToBase64(encoder.encode(code));
    this.busy++;
    return new Promise((resolve, reject) => {
      let settled = false;
      const done = (fn) => (value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (this.waiter && this.waiter.id === id) this.waiter = null;
        this.busy--;
        fn(value);
      };
      const timer = setTimeout(() => done(reject)(new Error("No answer from the badge.")), timeout);
      this.waiter = {
        id, start: this.buffer.length,
        pattern: new RegExp("^" + marker + "\\r?$", "m"),
        resolve: done(resolve), reject: done(reject),
      };
      this.write(`exec(__import__('binascii').a2b_base64('${b64}').decode(), globals()); print('${marker}')\r`)
        .catch(done(reject));
    });
  }

  // Runs code that prints "@@json <value>" lines; returns the last value
  async json(code, timeout) {
    const out = await this.run(code, timeout);
    const lines = out.split(/\r?\n/).filter((l) => l.startsWith("@@json "));
    if (!lines.length) throw new Error("Unexpected answer from the badge:\n" + out);
    return JSON.parse(lines[lines.length - 1].slice(7));
  }

  async reset() {
    // The page reconnects by itself once the badge is back
    this.expectReset = true;
    try { await this.write("\x03"); await sleep(200); await this.write("import machine; machine.reset()\r"); } catch (_) {}
  }
}

const badge = new Badge();

// ---------- connection and device tab ----------

let device = null;

badge.onState = (kind, text) => {
  const pill = $("#status");
  pill.className = "pill " + (kind || "");
  pill.textContent = text;
  const on = badge.connected;
  $("#connect").textContent = on ? "Disconnect" : "Connect badge";
  for (const id of ["#console-send", "#console-ctrlc", "#shot-now", "#shot-app", "#shot-app-go", "#settings-save", "#settings-reboot"]) {
    $(id).disabled = !on;
  }
  renderHome();
  renderDrive();
  if (kind === "err") {
    device = null;
    if (badge.toDrive) {
      // Switched to USB drive mode on purpose
      badge.toDrive = false;
      $("#hero").hidden = false;
      $("#device").hidden = true;
      document.querySelector('#tabs [data-tab="extensions"]').click();
    } else if (badge.expectReset) {
      badge.expectReset = false;
      reconnect();
    } else {
      $("#hero").hidden = false;
      $("#device").hidden = true;
      toast("The badge disconnected (it reboots after an app or a reset). Press Connect badge to reconnect.", 5000);
    }
  }
};

// After a reboot the badge comes back as the same, already allowed port
async function reconnect() {
  badge.state("busy", "rebooting…");
  try { await badge.port?.close(); } catch (_) {}
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) {
    await sleep(1500);
    const ports = (await navigator.serial.getPorts()).filter((p) => {
      const info = p.getInfo();
      return info.usbVendorId === USB_FILTER.usbVendorId && info.usbProductId === USB_FILTER.usbProductId;
    });
    if (ports.length !== 1) continue;
    try {
      await badge.connect(ports[0]);
      await loadDevice();
      await loadAll();
      return;
    } catch (_) {
      await badge.teardown();
    }
  }
  badge.state("err", "not connected");
  $("#hero").hidden = false;
  $("#device").hidden = true;
  toast("The badge did not come back. Press Connect badge.", 5000);
}

async function connect() {
  if (badge.connected) {
    await badge.disconnect();
    return;
  }
  try {
    badge.state("busy", "connecting…");
    const known = (await navigator.serial.getPorts()).filter((p) => {
      const info = p.getInfo();
      return info.usbVendorId === USB_FILTER.usbVendorId && info.usbProductId === USB_FILTER.usbProductId;
    });
    await badge.connect(known.length === 1 ? known[0] : undefined);
    await loadDevice();
    await loadAll();
  } catch (error) {
    await badge.teardown();
    badge.state("", "not connected");
    // NotFoundError: the chooser was closed without picking the badge
    toast(error.name === "NotFoundError" ? "No badge picked. Plug it in, then choose it in the list." : "Could not connect: " + error.message, 6000);
  }
}

async function loadAll() {
  // The commands queue up on the serial link: start with what is on screen
  await Promise.all([loadInstalled().then(() => Promise.all([renderStore(), loadShotApps()])), loadSettings()]);
  try {
    await loadHome();
  } catch (error) {
    toast("Could not read the home screen: " + error.message, 6000);
  }
}

async function loadDevice() {
  device = await badge.json(`
import machine
from badgeware import link as _l
_u = os.uname()
_r = os.statvfs("/")
_s = os.statvfs("/system")
_st_out({
    "name": _l.badge_name(bytes(machine.unique_id())[:_l.ID_LEN]),
    "machine": _u.machine, "release": _u.release,
    "battery": badge.battery_level(), "charging": badge.is_charging(),
    "root_free": _r[0] * _r[3], "root_size": _r[0] * _r[2],
    "system_free": _s[0] * _s[3], "system_size": _s[0] * _s[2],
    "ram_free": gc.mem_free(),
})`);
  $("#hero").hidden = true;
  $("#device").hidden = false;
  $("#device-name").textContent = device.name;
  $("#device-sub").textContent = device.machine + " · MicroPython " + device.release;
  const stats = [
    ["Battery", device.battery + "%" + (device.charging ? " · charging" : "")],
    ["Space for apps (/apps)", formatBytes(device.root_free) + " free of " + formatBytes(device.root_size)],
    ["Built-in apps (/system)", formatBytes(device.system_free) + " free of " + formatBytes(device.system_size)],
    ["Memory", formatBytes(device.ram_free) + " free"],
  ];
  $("#device-stats").innerHTML = stats
    .map(([label, value]) => `<div class="card stat"><div class="label">${label}</div><div class="value">${escapeHtml(value)}</div></div>`)
    .join("");
  $("#apps-space").textContent = formatBytes(device.root_free) + " free in /apps";
}

// ---------- apps: installed and store ----------

let installed = { builtin: [], apps: [], menu: false };
const catalogues = {};

async function loadInstalled() {
  installed = await badge.json(`
_apps = []
for _n, _d in _st_ls("${INSTALL_ROOT}"):
    if not _d:
        continue
    _p = "${INSTALL_ROOT}/" + _n
    _meta = {}
    try:
        _meta = json.load(open(_p + "/.studio.json"))
    except (OSError, ValueError):
        pass
    _icon = None
    try:
        _icon = _st_read_b64(_p + "/icon.png")
    except OSError:
        pass
    _apps.append({"slug": _n, "size": _st_size(_p), "meta": _meta, "icon": _icon})
try:
    _menu = "INSTALLED_ROOT" in open("${BUILT_IN_ROOT}/menu/app.py").read()
except OSError:
    _menu = False
_st_out({"builtin": [n for n, d in _st_ls("${BUILT_IN_ROOT}") if d], "apps": _apps, "menu": _menu})`, 60000);
  renderInstalled();
}

function renderInstalled() {
  const note = $("#apps-menu-note");
  note.hidden = installed.menu;
  note.innerHTML = "This badge's menu only shows <code>/system/apps</code>, so apps installed here are started with <b>Run on badge</b>. "
    + "To see them in the menu, deploy the menu of <a href='https://github.com/Akiyo974/badger'>Akiyo974/badger</a> once (USB drive mode).";
  const box = $("#apps-installed");
  if (!installed.apps.length) {
    box.innerHTML = `<p class="muted">Nothing installed yet. Pick an app in the store below.</p>`;
    return;
  }
  box.innerHTML = "";
  for (const app of installed.apps) {
    const card = document.createElement("div");
    card.className = "card app";
    const from = app.meta.repo ? `from ${escapeHtml(app.meta.repo)}` : "added by hand";
    card.innerHTML = `
      <div class="top">${app.icon ? `<img alt="" src="data:image/png;base64,${app.icon}">` : `<div class="noicon"></div>`}
        <div><div class="name">${escapeHtml(titleCase(app.slug))}<span class="tag installed">installed</span></div>
        <div class="meta">${formatBytes(app.size)} · ${from}</div></div></div>
      <div class="actions">
        <button class="small" data-act="run">Run on badge</button>
        ${app.meta.repo ? `<button class="small" data-act="reinstall">Reinstall</button>` : ""}
        <button class="small danger" data-act="remove">Uninstall</button>
      </div>`;
    card.querySelector('[data-act="run"]').onclick = () => runApp(INSTALL_ROOT + "/" + app.slug);
    card.querySelector('[data-act="remove"]').onclick = () => uninstall(app.slug);
    const again = card.querySelector('[data-act="reinstall"]');
    if (again) again.onclick = () => installFromMeta(app);
    box.appendChild(card);
  }
}

async function loadCatalogue(source) {
  if (catalogues[source.id]) return catalogues[source.id];
  const cacheKey = "studio-tree-" + source.id;
  let tree = null;
  try {
    const cached = JSON.parse(sessionStorage.getItem(cacheKey) || "null");
    if (cached && Date.now() - cached.at < 10 * 60 * 1000) tree = cached.tree;
  } catch (_) {}
  if (!tree) {
    const response = await fetch(`https://api.github.com/repos/${source.repo}/git/trees/${source.branch}?recursive=1`);
    if (!response.ok) throw new Error(`GitHub answered ${response.status} for ${source.repo}`);
    tree = (await response.json()).tree.filter((e) => e.type === "blob" && e.path.startsWith(source.base + "/"));
    try { sessionStorage.setItem(cacheKey, JSON.stringify({ at: Date.now(), tree })); } catch (_) {}
  }
  const apps = {};
  for (const entry of tree) {
    const [slug, ...rest] = entry.path.slice(source.base.length + 1).split("/");
    if (!rest.length || (!source.all && SKIP_APPS.has(slug))) continue;
    // Editor caches are not part of an app
    if (rest.some((part) => part.startsWith(".") || part === "__pycache__")) continue;
    (apps[slug] ||= { slug, files: [], size: 0 });
    apps[slug].files.push({ path: rest.join("/"), sha: entry.sha, size: entry.size || 0 });
    apps[slug].size += entry.size || 0;
  }
  const list = Object.values(apps).filter((app) => app.files.some((f) => f.path === "__init__.py"));
  for (const app of list) app.version = await appVersion(app.files);
  catalogues[source.id] = list.sort((a, b) => a.slug.localeCompare(b.slug));
  return catalogues[source.id];
}

async function appVersion(files) {
  const text = files.map((f) => f.path + ":" + f.sha).sort().join("\n");
  const digest = await crypto.subtle.digest("SHA-1", encoder.encode(text));
  return Array.from(new Uint8Array(digest)).slice(0, 6).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function rawUrl(source, path) {
  return `https://raw.githubusercontent.com/${source.repo}/${source.branch}/${source.base}/${path}`;
}

async function renderStore() {
  const box = $("#apps-store");
  const source = SOURCES.find((s) => s.id === $("#apps-source").value) || SOURCES[0];
  // Only the latest call draws: an older catalogue may arrive last
  const turn = (renderStore.turn = (renderStore.turn || 0) + 1);
  let list;
  try {
    list = await loadCatalogue(source);
  } catch (error) {
    if (turn !== renderStore.turn) return;
    box.innerHTML = `<div class="notice err">Could not load the catalogue: ${escapeHtml(error.message)}</div>`;
    return;
  }
  if (turn !== renderStore.turn) return;
  const query = $("#apps-search").value.trim().toLowerCase();
  const filter = $("#apps-filter").value;
  const builtin = new Set(installed.builtin);
  const mine = new Map(installed.apps.map((a) => [a.slug, a]));
  box.innerHTML = "";
  for (const app of list) {
    if (query && !app.slug.toLowerCase().includes(query)) continue;
    const here = mine.get(app.slug);
    const isBuiltIn = builtin.has(app.slug);
    const update = here && here.meta.version && here.meta.version !== app.version && here.meta.repo === source.repo;
    const tooBig = app.size > MAX_APP_BYTES;
    if ((filter === "available" && (here || isBuiltIn)) || (filter === "installed" && !here) || (filter === "updates" && !update)) continue;
    let tag = "";
    if (isBuiltIn) tag = `<span class="tag builtin">built in</span>`;
    else if (update) tag = `<span class="tag update">update</span>`;
    else if (here) tag = `<span class="tag installed">installed</span>`;
    const icon = app.files.some((f) => f.path === "icon.png") ? `<img alt="" loading="lazy" src="${rawUrl(source, app.slug + "/icon.png")}">` : `<div class="noicon"></div>`;
    const card = document.createElement("div");
    card.className = "card app";
    card.dataset.slug = app.slug;
    card.innerHTML = `
      <div class="top">${icon}<div><div class="name">${escapeHtml(titleCase(app.slug))}${tag}</div>
        <div class="meta">${formatBytes(app.size)} · ${app.files.length} files</div></div></div>
      <div class="desc">…</div>
      <div class="actions"></div>`;
    const actions = card.querySelector(".actions");
    if (isBuiltIn) {
      actions.innerHTML = `<span class="muted" style="font-size:13px">Already on the badge</span>`;
    } else if (tooBig) {
      actions.innerHTML = `<span class="muted" style="font-size:13px">Too big for /apps (${formatBytes(app.size)})</span>`;
    } else {
      const button = document.createElement("button");
      button.className = "small" + (here ? "" : " primary");
      button.textContent = update ? "Update" : here ? "Reinstall" : "Install";
      button.disabled = !badge.connected;
      button.onclick = () => install(source, app, card);
      actions.appendChild(button);
      if (here) {
        const remove = document.createElement("button");
        remove.className = "small danger";
        remove.textContent = "Uninstall";
        remove.onclick = () => uninstall(app.slug);
        actions.appendChild(remove);
      }
    }
    card.querySelector(".name").onclick = () => openDetail(source, app, card);
    box.appendChild(card);
    describe(source, app, card.querySelector(".desc"));
  }
  if (!box.children.length) box.innerHTML = `<p class="muted">${query ? `No app matches “${escapeHtml(query)}”.` : "No app in this list."}</p>`;
}

async function describe(source, app, el) {
  const readme = app.files.find((f) => f.path.toLowerCase() === "readme.md");
  if (!readme) { el.textContent = ""; return; }
  try {
    const key = "studio-readme-" + source.id + "-" + app.slug + "-" + readme.sha;
    let text = sessionStorage.getItem(key);
    if (text === null) {
      text = await (await fetch(rawUrl(source, app.slug + "/" + readme.path))).text();
      try { sessionStorage.setItem(key, text); } catch (_) {}
    }
    // First paragraph after the title
    const paragraph = text.split(/\n\s*\n/).map((p) => p.trim()).find((p) => p && !p.startsWith("#")) || "";
    el.textContent = paragraph.replace(/[*_`]/g, "").slice(0, 180);
  } catch (_) {
    el.textContent = "";
  }
}

// One install, uninstall or restore at a time: badge.run() orders single
// commands, not whole operations
let operation = false;

async function exclusive(work) {
  if (operation) {
    toast("Wait for the current operation to finish.");
    return;
  }
  operation = true;
  try {
    return await work();
  } finally {
    operation = false;
  }
}

const install = (...args) => exclusive(() => installNow(...args));
const uninstall = (...args) => exclusive(() => uninstallNow(...args));

async function installNow(source, app, card) {
  if (!badge.connected) return;
  const target = INSTALL_ROOT + "/" + app.slug;
  // The new version is written apart; the old one stays until it is complete
  const staging = STAGING_ROOT + "/" + app.slug;
  if (device && app.size + 16 * 1024 > device.root_free) {
    toast(`Not enough space: ${formatBytes(app.size)} needed, ${formatBytes(device.root_free)} free.`, 6000);
    return;
  }
  const bar = document.createElement("div");
  bar.className = "progress";
  bar.innerHTML = "<i></i>";
  card.appendChild(bar);
  const buttons = card.querySelectorAll("button");
  buttons.forEach((b) => (b.disabled = true));
  try {
    // Download first, so a network error never leaves half an app on the badge
    const files = [];
    for (const file of app.files) {
      const response = await fetch(rawUrl(source, app.slug + "/" + file.path));
      if (!response.ok) throw new Error(`Download failed for ${file.path} (${response.status})`);
      let bytes = new Uint8Array(await response.arrayBuffer());
      if (file.path.endsWith(".py")) {
        // Apps refer to their own folder as /system/apps/<slug>; here it is /apps/<slug>
        const text = new TextDecoder().decode(bytes).split(`${BUILT_IN_ROOT}/${app.slug}`).join(target);
        bytes = encoder.encode(text);
      }
      files.push({ path: file.path, bytes });
    }
    const total = files.reduce((n, f) => n + f.bytes.length, 0);
    let sent = 0;
    await badge.run(`_st_rm(${pyString(staging)})\n_st_mkdirs(${pyString(staging)})`);
    for (const file of files) {
      const path = staging + "/" + file.path;
      const folder = path.slice(0, path.lastIndexOf("/"));
      await badge.run(`_st_mkdirs(${pyString(folder)})\nopen(${pyString(path)}, "wb").close()`);
      for (let i = 0; i < file.bytes.length; i += WRITE_CHUNK) {
        const chunk = file.bytes.subarray(i, i + WRITE_CHUNK);
        await badge.run(`_st_write(${pyString(path)}, "${bytesToBase64(chunk)}", "ab")`);
        sent += chunk.length;
        bar.firstChild.style.width = Math.round((sent / total) * 100) + "%";
      }
      const [size, crc] = await badge.json(`_st_out(_st_check(${pyString(path)}))`);
      if (size !== file.bytes.length || crc >>> 0 !== crc32(file.bytes)) {
        throw new Error(`${file.path} was not written correctly (size ${size} / ${file.bytes.length})`);
      }
    }
    const meta = { repo: source.repo, branch: source.branch, base: source.base, source: source.id, version: app.version, installed: new Date().toISOString() };
    await badge.run(`f = open(${pyString(staging + "/.studio.json")}, "w"); f.write(${pyString(JSON.stringify(meta))}); f.close()`);
    await badge.run(`_st_mkdirs(${pyString(INSTALL_ROOT)})\n_st_rm(${pyString(target)})\nos.rename(${pyString(staging)}, ${pyString(target)})`);
    toast(`${titleCase(app.slug)} installed.`);
    $("#apps-reboot").hidden = !installed.menu;
  } catch (error) {
    const kept = installed.apps.some((a) => a.slug === app.slug) ? " The installed version was kept." : "";
    toast("Install failed: " + error.message + "." + kept, 7000);
    try { await badge.run(`_st_rm(${pyString(staging)})`); } catch (_) {}
  }
  await refreshApps();
}

async function installFromMeta(app) {
  const source = SOURCES.find((s) => s.repo === app.meta.repo) || { id: "custom-" + app.meta.repo, repo: app.meta.repo, branch: app.meta.branch || "main", base: app.meta.base };
  const list = await loadCatalogue(source);
  const entry = list.find((a) => a.slug === app.slug);
  if (!entry) { toast("This app is no longer in " + source.repo + ".", 5000); return; }
  const card = [...document.querySelectorAll("#apps-installed .card")].find((c) => c.textContent.includes(titleCase(app.slug))) || $("#apps-installed");
  await install(source, entry, card);
}

async function uninstallNow(slug) {
  if (!confirm(`Remove ${titleCase(slug)} from the badge?`)) return;
  try {
    await badge.run(`_st_rm(${pyString(INSTALL_ROOT + "/" + slug)})`);
    toast(`${titleCase(slug)} removed.`);
    $("#apps-reboot").hidden = !installed.menu;
  } catch (error) {
    toast("Could not remove it: " + error.message, 6000);
  }
  await refreshApps();
}

async function refreshApps() {
  try {
    await loadDevice();
    await loadInstalled();
  } catch (error) {
    toast(error.message, 5000);
  }
  await renderStore();
  await loadShotApps();
}

async function runApp(path) {
  // launch() takes over the badge until the app exits; then the badge reboots
  await badge.write(`launch(${pyString(path)})\r`);
  toast("Running on the badge. Press Home on the badge to leave the app; reconnect afterwards.", 6000);
}

// ---------- settings ----------

let settings = null;

async function loadSettings() {
  settings = await badge.json(`
_s = _st_secrets()
_locked = list(getattr(_s, "LOCKED", {}).keys())
_v = {}
for _k in ${JSON.stringify(SETTINGS.map((s) => s[0]))}:
    _x = getattr(_s, _k, None)
    _v[_k] = (bool(_x) if _k == "WIFI_PASSWORD" else _x)
_st_out({"values": _v, "locked": _locked, "can_save": hasattr(_s, "save")})`);
  const form = $("#settings-form");
  form.innerHTML = "";
  for (const [key, label, kind, hint] of SETTINGS) {
    const locked = settings.locked.includes(key);
    const value = settings.values[key];
    const row = document.createElement("div");
    row.className = "field" + (locked ? " locked" : "");
    let input;
    if (kind.startsWith("select:")) {
      input = document.createElement("select");
      for (const option of kind.slice(7).split(",")) {
        const el = document.createElement("option");
        el.value = el.textContent = option;
        input.appendChild(el);
      }
      input.value = value === null || value === undefined ? input.options[0].value : String(value === true ? "True" : value === false ? "False" : value);
    } else {
      input = document.createElement("input");
      input.type = kind;
      if (kind === "password") {
        input.placeholder = value ? "•••••••• (set)" : "not set";
        input.autocomplete = "new-password";
      } else {
        input.value = value === null || value === undefined ? "" : value;
      }
    }
    input.dataset.key = key;
    input.setAttribute("aria-label", label);
    input.dataset.initial = kind === "password" ? "" : input.value;
    input.disabled = locked;
    row.innerHTML = `<div><div>${locked ? "🔒 " : ""}${escapeHtml(label)}</div><div class="hint mono">${key}</div></div>`;
    const right = document.createElement("div");
    right.appendChild(input);
    const note = document.createElement("div");
    note.className = "hint";
    note.textContent = locked ? "Set in /system/secrets.py on the USB drive" : hint;
    right.appendChild(note);
    row.appendChild(right);
    form.appendChild(row);
  }
  $("#settings-state").textContent = settings.can_save ? "" : "This firmware cannot save settings from here.";
}

async function saveSettings(reboot) {
  const changes = {};
  for (const input of document.querySelectorAll("#settings-form [data-key]")) {
    if (input.disabled || input.value === input.dataset.initial) continue;
    const key = input.dataset.key;
    if (key === "WIFI_PASSWORD" && !input.value) continue;
    let value = input.value;
    if (key === "STEPS_GOAL") value = parseInt(value, 10) || 0;
    if (key === "WATCH_REMOTE") value = value === "True";
    changes[key] = value;
  }
  if (!Object.keys(changes).length) { toast("Nothing changed."); return; }
  try {
    await badge.run(`_st_secrets().save(json.loads(${pyString(JSON.stringify(changes))}))`);
    toast(`Saved: ${Object.keys(changes).join(", ")}.`);
    if (reboot) await badge.reset();
    else await loadSettings();
  } catch (error) {
    toast("Could not save: " + error.message, 6000);
  }
}

// ---------- screenshots ----------

async function loadShotApps() {
  const select = $("#shot-app");
  const names = [...installed.builtin.filter((n) => !SKIP_APPS.has(n) || n === "menu").map((n) => [n, BUILT_IN_ROOT + "/" + n]),
    ...installed.apps.map((a) => [a.slug, INSTALL_ROOT + "/" + a.slug])];
  select.innerHTML = names.map(([n, p]) => `<option value="${escapeHtml(p)}">${escapeHtml(titleCase(n))}</option>`).join("");
}

function runnerCode(path, ms) {
  // Same approach as tools/screenshot.ps1: run() and badge.update() are
  // replaced so the app stops after a few frames and its screen stays put
  return `
import time
os.chdir(${pyString(path)}); sys.path.insert(0, ${pyString(path)})
class StopCapture(Exception):
    pass
REAL_BADGE = badge
FRAMES = 0
DEADLINE = None
def frame_done():
    global DEADLINE, FRAMES
    if DEADLINE is None:
        DEADLINE = time.ticks_add(time.ticks_ms(), ${ms})
    FRAMES += 1
    return FRAMES >= 3 and time.ticks_diff(time.ticks_ms(), DEADLINE) >= 0
class CaptureBadge:
    def __getattr__(self, name):
        return getattr(REAL_BADGE, name)
    def __setattr__(self, name, value):
        setattr(REAL_BADGE, name, value)
    def update(self, *args):
        result = REAL_BADGE.update(*args)
        if frame_done():
            raise StopCapture()
        return result
def capture_run(f):
    while True:
        REAL_BADGE.update(); f(); display.update()
        if frame_done():
            raise StopCapture()
g = dict(globals()); g["run"] = capture_run; g["badge"] = CaptureBadge(); g["__name__"] = "capture"
badge.mode(LORES | VSYNC)
try:
    exec(open(${pyString(path + "/__init__.py")}).read(), g)
except StopCapture:
    pass
if FRAMES < 3:
    raise RuntimeError("the app stopped before drawing anything")
`;
}

async function capture(appPath) {
  const state = $("#shot-state");
  const progress = $("#shot-progress");
  const bar = progress.firstChild;
  progress.hidden = false;
  bar.style.width = "0";
  $("#shot-download").hidden = true;
  try {
    await badge.interrupt();
    await badge.run(HELPERS);
    if (appPath) {
      state.textContent = "Running the app…";
      const seconds = Math.max(1, Math.min(20, parseFloat($("#shot-seconds").value) || 3));
      await badge.run(runnerCode(appPath, Math.round(seconds * 1000)), (seconds + 60) * 1000);
    }
    state.textContent = "Reading the screen…";
    let dims = null;
    for (let attempt = 0; attempt < 3 && !dims; attempt++) {
      const d = await badge.json(`_st_out([screen.width, screen.height, screen.stride])`);
      if ((d[0] === 320 && d[1] === 240 && d[2] === 640) || (d[0] === 160 && d[1] === 120 && d[2] === 320)) dims = d;
    }
    if (!dims) throw new Error("Unexpected screen size.");
    const [width, height, stride] = dims;
    const total = height * stride;
    const count = Math.ceil(total / SHOT_CHUNK);
    await badge.run(`
_r = bytes(screen.raw)[:${total}]
gc.collect()
def _chunk(n):
    data = _r[n * ${SHOT_CHUNK}:(n + 1) * ${SHOT_CHUNK}]
    print("#%d:%08x:%s" % (n, binascii.crc32(b"%d:" % n + data), binascii.b2a_base64(data).decode().strip()))`);
    const chunks = new Map();
    const read = (text) => {
      for (const m of text.matchAll(/^#(\d+):([0-9a-f]{8}):([A-Za-z0-9+/=]+)\r?$/gm)) {
        const n = Number(m[1]);
        const expected = Math.min(SHOT_CHUNK, total - n * SHOT_CHUNK);
        let data;
        try { data = base64ToBytes(m[3]); } catch (_) { continue; }
        if (expected <= 0 || data.length !== expected) continue;
        const signed = new Uint8Array(data.length + String(n).length + 1);
        signed.set(encoder.encode(n + ":"), 0);
        signed.set(data, String(n).length + 1);
        if (crc32(signed) === parseInt(m[2], 16)) chunks.set(n, data);
      }
      bar.style.width = Math.round((chunks.size / count) * 100) + "%";
    };
    read(await badge.run(`for n in range(${count}): _chunk(n)`, 60000));
    for (let attempt = 0; attempt < 5 && chunks.size < count; attempt++) {
      for (let n = 0; n < count; n++) if (!chunks.has(n)) read(await badge.run(`_chunk(${n})`));
    }
    if (chunks.size < count) throw new Error("Some parts of the image could not be read.");
    const raw = new Uint8Array(total);
    for (const [n, data] of chunks) raw.set(data, n * SHOT_CHUNK);
    draw(raw, width, height, stride);
    state.textContent = `Captured ${width}×${height}.`;
  } catch (error) {
    state.textContent = "Capture failed: " + error.message;
  }
  progress.hidden = true;
  // Give the badge its menu back
  await badge.reset();
}

function draw(raw, width, height, stride) {
  const canvas = $("#shot-canvas");
  const scale = 640 / width;
  const small = new ImageData(width, height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const i = y * stride + x * 2;
      const v = raw[i] | (raw[i + 1] << 8);
      const o = (y * width + x) * 4;
      small.data[o] = ((v >> 11) & 0x1f) * 255 / 31;
      small.data[o + 1] = ((v >> 5) & 0x3f) * 255 / 63;
      small.data[o + 2] = (v & 0x1f) * 255 / 31;
      small.data[o + 3] = 255;
    }
  }
  const temp = document.createElement("canvas");
  temp.width = width;
  temp.height = height;
  temp.getContext("2d").putImageData(small, 0, 0);
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(temp, 0, 0, width * scale, height * scale);
  const link = $("#shot-download");
  link.href = canvas.toDataURL("image/png");
  link.download = "badge-" + new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-") + ".png";
  link.hidden = false;
}

// ---------- home screen layout ----------

const LAYOUT_FILE = "/state/menu_layout.json";
const SECTIONS = { custom: "Custom", order: "Apps", hidden: "Hidden" };
let home = null;

function pyTuple(source, name) {
  const match = source.match(new RegExp(name + "\\s*=\\s*\\(([\\s\\S]*?)\\)"));
  return match ? [...match[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];
}

async function loadHome() {
  const data = await badge.json(`
def _ok(p):
    for _n in ("__init__.py", "__init__.mpy"):
        try:
            os.stat(p + "/" + _n)
            return True
        except OSError:
            pass
    return False
def _ic(p):
    try:
        return _st_read_b64(p + "/icon.png")
    except OSError:
        return None
_b = [[n, _ic("${BUILT_IN_ROOT}/" + n)] for n, d in _st_ls("${BUILT_IN_ROOT}") if d and n != "menu" and _ok("${BUILT_IN_ROOT}/" + n)]
_bn = set(x[0] for x in _b)
_a = [[n, _ic("${INSTALL_ROOT}/" + n)] for n, d in _st_ls("${INSTALL_ROOT}") if d and n not in _bn and _ok("${INSTALL_ROOT}/" + n)]
_head = ""
_sup = False
try:
    _src = open("${BUILT_IN_ROOT}/menu/app.py").read()
    _sup = "LAYOUT_FILE" in _src
    _i = _src.find("APP_ORDER")
    _j = _src.find("BAND =")
    if 0 <= _i < _j:
        _head = _src[_i:_j]
    del _src
except OSError:
    pass
try:
    _lay = json.load(open("${LAYOUT_FILE}"))
except (OSError, ValueError):
    _lay = None
gc.collect()
_st_out({"builtin": _b, "added": _a, "head": _head, "supported": _sup, "layout": _lay})`, 60000);
  const appOrder = pyTuple(data.head, "APP_ORDER");
  const defaultCustom = pyTuple(data.head, "CUSTOM_APPS");
  const layout = data.layout && typeof data.layout === "object" ? data.layout : {};
  const apps = new Map();
  for (const [slug, icon] of data.builtin) apps.set(slug, { slug, icon, added: false });
  for (const [slug, icon] of data.added) apps.set(slug, { slug, icon, added: true });
  const customSlugs = ("custom" in layout ? layout.custom : defaultCustom) || [];
  const hidden = new Set(layout.hidden || []);
  const orderList = layout.order || [];
  // Same sort as the menu: the saved order first, then the menu's own order
  const rank = (slug) => (orderList.includes(slug) ? orderList.indexOf(slug) : orderList.length);
  const stock = (slug) => (appOrder.includes(slug) ? appOrder.indexOf(slug) : appOrder.length);
  const by = (...keys) => (a, b) => {
    for (const key of keys) {
      const x = key(a), y = key(b);
      if (x < y) return -1;
      if (x > y) return 1;
    }
    return 0;
  };
  const all = [...apps.values()];
  const visible = all.filter((a) => !hidden.has(a.slug));
  const inCustom = (a) => customSlugs.includes(a.slug);
  home = {
    supported: data.supported,
    saved: !!data.layout,
    lists: {
      custom: visible.filter(inCustom).sort(by((a) => rank(a.slug), (a) => customSlugs.indexOf(a.slug))),
      order: [
        ...visible.filter((a) => a.added && !inCustom(a)).sort(by((a) => rank(a.slug), (a) => a.slug)),
        ...visible.filter((a) => !a.added && !inCustom(a)).sort(by((a) => rank(a.slug), (a) => stock(a.slug), (a) => a.slug)),
      ],
      hidden: all.filter((a) => hidden.has(a.slug)).sort(by((a) => a.slug)),
    },
    dirty: false,
  };
  renderHome();
}

function renderHome() {
  if (!home) return;
  const note = $("#home-note");
  note.hidden = home.supported;
  note.innerHTML = "This badge's menu does not read a saved layout yet. Install the <b>Menu</b> extension (Extensions tab) first, then come back here.";
  for (const list of document.querySelectorAll("#home-columns .applist")) {
    const name = list.dataset.list;
    const apps = home.lists[name];
    list.innerHTML = "";
    apps.forEach((app, index) => {
      const item = document.createElement("li");
      item.draggable = true;
      item.dataset.slug = app.slug;
      item.innerHTML = `<span class="grip">⋮⋮</span>
        ${app.icon ? `<img alt="" width="20" height="20" style="image-rendering:pixelated" src="data:image/png;base64,${app.icon}">` : ""}
        <span class="label">${escapeHtml(titleCase(app.slug))}</span>
        <span class="src">${app.added ? "installed" : "built in"}</span>
        <button class="small" data-move="-1" title="Move up" ${index === 0 ? "disabled" : ""}>↑</button>
        <button class="small" data-move="1" title="Move down" ${index === apps.length - 1 ? "disabled" : ""}>↓</button>
        <select class="small" aria-label="Section of ${escapeHtml(titleCase(app.slug))}">
          ${Object.entries(SECTIONS).map(([list, title]) => `<option value="${list}" ${list === name ? "selected" : ""}>${title}</option>`).join("")}
        </select>`;
      item.querySelector("select").onchange = (e) => moveApp(app.slug, e.target.value, Infinity);
      item.querySelectorAll("[data-move]").forEach((button) => {
        button.onclick = () => moveApp(app.slug, name, index + Number(button.dataset.move));
      });
      item.ondragstart = (e) => {
        e.dataTransfer.setData("text/plain", app.slug);
        e.dataTransfer.effectAllowed = "move";
        item.classList.add("dragging");
      };
      item.ondragend = () => item.classList.remove("dragging");
      list.appendChild(item);
    });
    if (!apps.length) list.innerHTML = `<p class="muted" style="margin:8px">Drop apps here</p>`;
  }
  $("#home-save").disabled = !badge.connected || !home.dirty || !home.supported;
  $("#home-reset").disabled = !badge.connected || !home.saved || !home.supported;
  $("#home-state").textContent = home.dirty ? "Not saved yet." : home.saved ? "Your saved layout." : "Default layout.";
}

function moveApp(slug, to, index) {
  let app = null;
  for (const list of Object.values(home.lists)) {
    const at = list.findIndex((a) => a.slug === slug);
    if (at >= 0) app = list.splice(at, 1)[0];
  }
  if (!app) return;
  const target = home.lists[to];
  target.splice(Math.max(0, Math.min(index, target.length)), 0, app);
  // The menu always shows the installed apps before the stock ones
  if (to === "order") home.lists.order = [...target.filter((a) => a.added), ...target.filter((a) => !a.added)];
  home.dirty = true;
  renderHome();
}

function wireHomeDrop() {
  for (const list of document.querySelectorAll("#home-columns .applist")) {
    list.ondragover = (e) => {
      e.preventDefault();
      list.classList.add("over");
    };
    list.ondragleave = () => list.classList.remove("over");
    list.ondrop = (e) => {
      e.preventDefault();
      list.classList.remove("over");
      const slug = e.dataTransfer.getData("text/plain");
      // Drop above the item under the pointer, or at the end
      const items = [...list.querySelectorAll("li")].filter((li) => li.dataset.slug !== slug);
      let index = items.findIndex((li) => e.clientY < li.getBoundingClientRect().top + li.offsetHeight / 2);
      if (index < 0) index = items.length;
      if (slug && home) moveApp(slug, list.dataset.list, index);
    };
  }
}

async function saveHome(reset) {
  if (!home) return;
  const layout = {
    custom: home.lists.custom.map((a) => a.slug),
    order: home.lists.order.map((a) => a.slug),
    hidden: home.lists.hidden.map((a) => a.slug),
  };
  try {
    if (reset) {
      if (!confirm("Go back to the default home screen?")) return;
      await badge.run(`_st_rm(${pyString(LAYOUT_FILE)})`);
    } else {
      await badge.run(`_st_mkdirs("/state")\nf = open(${pyString(LAYOUT_FILE)}, "w"); f.write(${pyString(JSON.stringify(layout))}); f.close()`);
    }
    toast(reset ? "Default layout back. The badge restarts." : "Home screen saved. The badge restarts.");
    await badge.reset();
  } catch (error) {
    toast("Could not save the layout: " + error.message, 6000);
  }
}

// ---------- extensions: other versions of the built-in apps ----------
// /system is read-only from the badge. In USB drive mode the computer can
// write to it: the page then works on the drive's apps folder, through the
// File System Access API, and keeps a copy of every app it replaces.

const EXT_SOURCE = { id: "akiyo-system", repo: "Akiyo974/badger", branch: "main", base: "system/apps", all: true };
const BACKUPS = ".studio-backups";
let drive = null;
let extensions = null;

// The picked folder is kept in IndexedDB, so it is only picked once
function idb(action, value) {
  return new Promise((resolve, reject) => {
    const open = indexedDB.open("badge-studio", 1);
    open.onupgradeneeded = () => open.result.createObjectStore("handles");
    open.onerror = () => reject(open.error);
    open.onsuccess = () => {
      const store = open.result.transaction("handles", action === "get" ? "readonly" : "readwrite").objectStore("handles");
      const request = action === "get" ? store.get("apps") : store.put(value, "apps");
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    };
  });
}

// The id git gives a file, as listed by the GitHub trees API
async function gitBlobSha(bytes) {
  const head = encoder.encode(`blob ${bytes.length}\0`);
  const all = new Uint8Array(head.length + bytes.length);
  all.set(head, 0);
  all.set(bytes, head.length);
  const digest = await crypto.subtle.digest("SHA-1", all);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function folder(root, path, create) {
  let dir = root;
  for (const part of path.split("/").filter(Boolean)) dir = await dir.getDirectoryHandle(part, { create });
  return dir;
}

async function readFolder(dir, prefix = "", out = new Map()) {
  for await (const [name, handle] of dir.entries()) {
    if (handle.kind === "directory") {
      if (name !== "__pycache__") await readFolder(handle, prefix + name + "/", out);
    } else {
      out.set(prefix + name, handle);
    }
  }
  return out;
}

async function writeOnDrive(root, path, bytes) {
  const parts = path.split("/");
  const name = parts.pop();
  const dir = await folder(root, parts.join("/"), true);
  const writable = await (await dir.getFileHandle(name, { create: true })).createWritable();
  await writable.write(bytes);
  await writable.close();
  const back = new Uint8Array(await (await (await dir.getFileHandle(name)).getFile()).arrayBuffer());
  if (back.length !== bytes.length || crc32(back) !== crc32(bytes)) throw new Error(path + " was not written correctly");
}

async function copyFolder(from, to, skip = () => false) {
  for (const [path, handle] of await readFolder(from)) {
    if (skip(path)) continue;
    await writeOnDrive(to, path, new Uint8Array(await (await handle.getFile()).arrayBuffer()));
  }
}

async function hasEntry(dir, name, kind) {
  try {
    if (kind === "directory") await dir.getDirectoryHandle(name);
    else await dir.getFileHandle(name);
    return true;
  } catch (_) {
    return false;
  }
}

async function useDrive(handle) {
  if ((await handle.queryPermission({ mode: "readwrite" })) !== "granted"
      && (await handle.requestPermission({ mode: "readwrite" })) !== "granted") {
    throw new Error("Write access to the drive was not allowed.");
  }
  if (!(await hasEntry(handle, "menu", "directory"))) {
    throw new Error(`“${handle.name}” is not the badge's apps folder: open the BADGER drive and pick its apps folder.`);
  }
  // Fails when the drive is not plugged in any more
  await readFolder(await handle.getDirectoryHandle("menu"));
  drive = handle;
  try { await idb("put", handle); } catch (_) {}
  renderDrive();
  await loadBackups();
  await compareExtensions();
}

async function pickDrive() {
  if (badge.connected) {
    if (!confirm("The badge restarts as a USB drive named BADGER, then you pick its apps folder here. Continue?")) return;
    badge.toDrive = true;
    await badge.write("\x03");
    await sleep(200);
    await badge.write("import powman; powman.reset_into_msc()\r");
    $("#ext-state").textContent = "Wait for the BADGER drive to show up, then press Pick the apps folder.";
    return;
  }
  try {
    const saved = await idb("get").catch(() => null);
    if (saved) {
      try { await useDrive(saved); return; } catch (_) {}
    }
    await useDrive(await window.showDirectoryPicker({ id: "badger-apps", mode: "readwrite" }));
  } catch (error) {
    if (error.name !== "AbortError") toast(error.message, 7000);
  }
}

function renderDrive() {
  const supported = "showDirectoryPicker" in window;
  const button = $("#ext-drive");
  button.disabled = !supported || (!!drive && !badge.connected);
  button.textContent = badge.connected ? "Switch to USB drive mode" : drive ? "Drive ready" : "Pick the apps folder";
  $("#ext-check").disabled = !badge.connected && !drive;
  $("#ext-finish").hidden = !drive || badge.connected;
  const note = $("#ext-note");
  note.hidden = false;
  if (!supported) {
    note.className = "notice warn";
    note.textContent = "This browser cannot write to a drive. Use Chrome or Edge on a computer.";
  } else if (drive && !badge.connected) {
    note.className = "notice";
    note.innerHTML = "Working on the badge's drive (<b>BADGER/apps</b>). When you are done, press <b>Restart the badge</b>.";
  } else {
    note.hidden = true;
  }
}

// Compares every app of the repo with the one on the badge, file by file
async function compareExtensions() {
  const box = $("#ext-list");
  box.innerHTML = `<p class="muted">Comparing…</p>`;
  let list;
  try {
    list = await loadCatalogue(EXT_SOURCE);
  } catch (error) {
    box.innerHTML = `<div class="notice err">Could not load ${EXT_SOURCE.repo}: ${escapeHtml(error.message)}</div>`;
    return;
  }
  const local = new Map();
  try {
    if (drive) {
      for (const app of list) {
        if (!(await hasEntry(drive, app.slug, "directory"))) continue;
        for (const [path, handle] of await readFolder(await drive.getDirectoryHandle(app.slug))) {
          local.set(app.slug + "/" + path, await gitBlobSha(new Uint8Array(await (await handle.getFile()).arrayBuffer())));
        }
      }
    } else {
      const paths = list.flatMap((app) => app.files.map((f) => app.slug + "/" + f.path));
      const hashes = await badge.json(`
try:
    import hashlib
    _sha = hashlib.sha1
except (ImportError, AttributeError):
    _sha = None
def _blob(path):
    try:
        size = os.stat(path)[6]
    except OSError:
        return None
    if not _sha:
        return [size, None]
    h = _sha(("blob %d\\0" % size).encode())
    f = open(path, "rb")
    while True:
        data = f.read(2048)
        if not data:
            break
        h.update(data)
    f.close()
    return [size, binascii.hexlify(h.digest()).decode()]
_r = {}
for _p in json.loads(${pyString(JSON.stringify(paths))}):
    _x = _blob("${BUILT_IN_ROOT}/" + _p)
    if _x:
        _r[_p] = _x
_st_out(_r)`, 180000);
      // Without hashlib.sha1 on the badge, only the sizes can be compared
      for (const [path, [size, sha]] of Object.entries(hashes)) local.set(path, sha || "size:" + size);
    }
  } catch (error) {
    box.innerHTML = `<div class="notice err">Could not read the badge: ${escapeHtml(error.message)}</div>`;
    return;
  }
  extensions = list.map((app) => {
    let missing = 0, changed = 0;
    for (const file of app.files) {
      const here = local.get(app.slug + "/" + file.path);
      if (here === undefined) missing++;
      else if (here.startsWith("size:") ? Number(here.slice(5)) !== file.size : here !== file.sha) changed++;
    }
    const onBadge = [...local.keys()].some((p) => p.startsWith(app.slug + "/"));
    return { ...app, status: !onBadge ? "new" : missing || changed ? "differs" : "same", missing, changed };
  });
  renderExtensions();
}

function renderExtensions() {
  const box = $("#ext-list");
  box.innerHTML = "";
  const shown = extensions.filter((app) => app.status !== "same");
  const same = extensions.length - shown.length;
  for (const app of shown) {
    const card = document.createElement("div");
    card.className = "card app";
    const count = app.changed + app.missing;
    const what = app.status === "new"
      ? `<span class="state-missing">not on this badge</span>`
      : `<span class="state-diff">${[app.changed && app.changed + " changed", app.missing && app.missing + " new"].filter(Boolean).join(", ")} file${count > 1 ? "s" : ""}</span>`;
    const icon = app.files.some((f) => f.path === "icon.png") ? `<img alt="" loading="lazy" src="${rawUrl(EXT_SOURCE, app.slug + "/icon.png")}">` : `<div class="noicon"></div>`;
    card.innerHTML = `
      <div class="top">${icon}<div><div class="name">${escapeHtml(titleCase(app.slug))}<span class="tag ${app.status === "new" ? "update" : "builtin"}">${app.status === "new" ? "new" : "extension"}</span></div>
        <div class="meta">${formatBytes(app.size)} · ${what}</div></div></div>
      <div class="desc">…</div>
      <div class="actions"></div>`;
    const button = document.createElement("button");
    button.className = "small primary";
    button.textContent = app.status === "new" ? "Add to the badge" : "Install this version";
    button.disabled = !drive;
    button.title = drive ? "" : "Switch the badge to USB drive mode first";
    button.onclick = () => installExtension(app, card);
    card.querySelector(".actions").appendChild(button);
    card.querySelector(".name").onclick = () => openDetail(EXT_SOURCE, app, card);
    box.appendChild(card);
    describe(EXT_SOURCE, app, card.querySelector(".desc"));
  }
  if (!shown.length) box.innerHTML = `<p class="muted">Every app of ${EXT_SOURCE.repo} is already on this badge, in the same version.</p>`;
  $("#ext-state").textContent = same ? `${same} app${same > 1 ? "s" : ""} already identical.` : "";
}

function stamp() {
  return new Date().toISOString().slice(0, 19).replace(/[-:]/g, "").replace("T", "-");
}

// Copies the app as it is now into the backups folder
async function backup(slug, note) {
  if (!(await hasEntry(drive, slug, "directory"))) return null;
  const name = `${slug}-${stamp()}`;
  const target = await folder(drive, `${BACKUPS}/${name}`, true);
  await copyFolder(await drive.getDirectoryHandle(slug), target);
  await writeOnDrive(target, ".studio-backup.json", encoder.encode(JSON.stringify({ slug, note, at: new Date().toISOString() })));
  return name;
}

const installExtension = (...args) => exclusive(() => installExtensionNow(...args));
const restoreBackup = (...args) => exclusive(() => restoreBackupNow(...args));

async function installExtensionNow(app, card) {
  if (!drive) return;
  const bar = document.createElement("div");
  bar.className = "progress";
  bar.innerHTML = "<i></i>";
  card.appendChild(bar);
  card.querySelectorAll("button").forEach((b) => (b.disabled = true));
  try {
    // Download first, so a network error never leaves half an app on the badge
    const files = [];
    for (const file of app.files) {
      const response = await fetch(rawUrl(EXT_SOURCE, app.slug + "/" + file.path));
      if (!response.ok) throw new Error(`Download failed for ${file.path} (${response.status})`);
      files.push({ path: file.path, bytes: new Uint8Array(await response.arrayBuffer()) });
    }
    const saved = await backup(app.slug, "before " + EXT_SOURCE.repo + " " + app.version);
    await drive.removeEntry(app.slug, { recursive: true }).catch(() => {});
    const target = await drive.getDirectoryHandle(app.slug, { create: true });
    let done = 0;
    for (const file of files) {
      await writeOnDrive(target, file.path, file.bytes);
      bar.firstChild.style.width = Math.round((++done / files.length) * 100) + "%";
    }
    toast(`${titleCase(app.slug)} written${saved ? ", the old version is backed up" : ""}. Restart the badge when you are done.`, 6000);
  } catch (error) {
    toast("Install failed: " + error.message + ". Any replaced version is in Backups.", 8000);
  }
  await loadBackups();
  await compareExtensions();
}

async function loadBackups() {
  const box = $("#ext-backups");
  if (!drive) return;
  const backups = [];
  if (await hasEntry(drive, BACKUPS, "directory")) {
    for await (const [name, handle] of (await drive.getDirectoryHandle(BACKUPS)).entries()) {
      if (handle.kind !== "directory") continue;
      // The manifest is written last: without it the copy did not finish
      let meta = { slug: name.replace(/-\d{8}-\d{6}$/, ""), complete: false };
      try { meta = { ...meta, ...JSON.parse(await (await (await handle.getFileHandle(".studio-backup.json")).getFile()).text()), complete: true }; } catch (_) {}
      backups.push({ name, meta });
    }
  }
  backups.sort((a, b) => b.name.localeCompare(a.name));
  box.innerHTML = backups.length ? "" : `<p class="muted">No backup yet. One is made every time an app is replaced.</p>`;
  for (const item of backups) {
    const card = document.createElement("div");
    card.className = "card app";
    const when = item.meta.at ? new Date(item.meta.at).toLocaleString() : item.name;
    card.innerHTML = `
      <div class="top"><div class="noicon"></div><div><div class="name">${escapeHtml(titleCase(item.meta.slug))}</div>
        <div class="meta">${escapeHtml(when)}${item.meta.note ? " · " + escapeHtml(item.meta.note) : ""}</div></div></div>
      <div class="actions">${item.meta.complete ? `<button class="small" data-act="restore">Restore</button>` : `<span class="muted" style="font-size:13px">Incomplete copy</span>`}<button class="small danger" data-act="delete">Delete</button></div>`;
    const restore = card.querySelector('[data-act="restore"]');
    if (restore) restore.onclick = () => restoreBackup(item);
    card.querySelector('[data-act="delete"]').onclick = async () => {
      if (!confirm(`Delete this backup of ${titleCase(item.meta.slug)}?`)) return;
      await (await drive.getDirectoryHandle(BACKUPS)).removeEntry(item.name, { recursive: true });
      await loadBackups();
    };
    box.appendChild(card);
  }
}

async function restoreBackupNow(item) {
  const slug = item.meta.slug;
  if (!confirm(`Put back this version of ${titleCase(slug)}? The current one is backed up first.`)) return;
  try {
    await backup(slug, "before restoring " + item.name);
    await drive.removeEntry(slug, { recursive: true }).catch(() => {});
    const from = await (await drive.getDirectoryHandle(BACKUPS)).getDirectoryHandle(item.name);
    await copyFolder(from, await drive.getDirectoryHandle(slug, { create: true }), (path) => path === ".studio-backup.json");
    toast(`${titleCase(slug)} restored. Restart the badge when you are done.`, 6000);
  } catch (error) {
    toast("Restore failed: " + error.message, 8000);
  }
  await loadBackups();
  await compareExtensions();
}

// In USB drive mode the serial port is still there: reset the badge through it
async function finishDrive() {
  const ports = (await navigator.serial.getPorts()).filter((p) => {
    const info = p.getInfo();
    return info.usbVendorId === USB_FILTER.usbVendorId && info.usbProductId === USB_FILTER.usbProductId;
  });
  if (ports.length !== 1) {
    toast("Eject the BADGER drive, then press the badge's reset button.", 7000);
    return;
  }
  try {
    await ports[0].open({ baudRate: 115200 });
    const writer = ports[0].writable.getWriter();
    await writer.write(encoder.encode("\x03"));
    await sleep(300);
    await writer.write(encoder.encode("\x03import machine; machine.reset()\r"));
    await sleep(300);
    writer.releaseLock();
    await ports[0].close().catch(() => {});
    drive = null;
    extensions = null;
    badge.port = ports[0];
    toast("The badge restarts with the new apps.", 5000);
    renderDrive();
    badge.expectReset = false;
    reconnect();
  } catch (error) {
    toast("Could not restart it: " + error.message + ". Press the badge's reset button.", 7000);
  }
}

// ---------- app details ----------

// Just enough Markdown for the apps' READMEs
function markdown(text) {
  const inline = (line) => escapeHtml(line)
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
  const out = [];
  let list = false, code = false, para = [];
  const endParagraph = () => {
    if (para.length) out.push("<p>" + para.map(inline).join(" ") + "</p>");
    para = [];
  };
  const endList = () => {
    if (list) out.push("</ul>");
    list = false;
  };
  for (const line of text.split(/\r?\n/)) {
    if (line.startsWith("```")) {
      endParagraph();
      endList();
      out.push(code ? "</code></pre>" : "<pre><code>");
      code = !code;
      continue;
    }
    if (code) { out.push(escapeHtml(line) + "\n"); continue; }
    const heading = line.match(/^#{1,6}\s+(.*)/);
    const item = line.match(/^\s*[-*]\s+(.*)/);
    if (heading) {
      endParagraph(); endList();
      out.push(`<h3>${inline(heading[1])}</h3>`);
    } else if (item) {
      endParagraph();
      if (!list) { out.push("<ul>"); list = true; }
      out.push(`<li>${inline(item[1])}</li>`);
    } else if (line.trim().startsWith("|")) {
      endParagraph(); endList();
      if (!/^\|[\s|:-]+\|$/.test(line.trim())) {
        const cells = line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
        out.push(`<div class="mono muted" style="font-size:12px">${inline(cells.join(" · "))}</div>`);
      }
    } else if (!line.trim()) {
      endParagraph(); endList();
    } else {
      endList();
      para.push(line.trim());
    }
  }
  if (code) out.push("</code></pre>");
  endParagraph();
  endList();
  return out.join("");
}

async function openDetail(source, app, card) {
  const dialog = $("#detail");
  const hasIcon = app.files.some((f) => f.path === "icon.png");
  $("#detail-icon").hidden = !hasIcon;
  if (hasIcon) $("#detail-icon").src = rawUrl(source, app.slug + "/icon.png");
  $("#detail-name").textContent = titleCase(app.slug);
  const link = `https://github.com/${source.repo}/tree/${source.branch}/${source.base}/${app.slug}`;
  $("#detail-meta").innerHTML = `${formatBytes(app.size)} · ${app.files.length} files · <a href="${link}" target="_blank" rel="noopener">${escapeHtml(source.repo)}</a>`;
  $("#detail-files").innerHTML = app.files.map((f) => `<li>${escapeHtml(f.path)} · ${formatBytes(f.size)}</li>`).join("");
  // The same buttons as on the card
  const actions = $("#detail-actions");
  actions.innerHTML = "";
  for (const button of card ? card.querySelectorAll(".actions button") : []) {
    const copy = document.createElement("button");
    copy.className = button.className;
    copy.textContent = button.textContent;
    copy.disabled = button.disabled;
    copy.onclick = () => { dialog.close(); button.click(); };
    actions.appendChild(copy);
  }
  const readme = app.files.find((f) => f.path.toLowerCase() === "readme.md");
  const box = $("#detail-readme");
  box.innerHTML = readme ? `<p class="muted">Loading…</p>` : `<p class="muted">No README for this app.</p>`;
  dialog.showModal();
  if (!readme) return;
  try {
    const response = await fetch(rawUrl(source, app.slug + "/" + readme.path));
    if (!response.ok) throw new Error(response.status);
    box.innerHTML = markdown(await response.text());
  } catch (_) {
    box.innerHTML = `<p class="muted">Could not load the README.</p>`;
  }
}

// ---------- console ----------

const consoleOut = $("#console-out");
badge.onText = (text) => {
  consoleOut.textContent += text.replace(/\r/g, "");
  if (consoleOut.textContent.length > 60000) consoleOut.textContent = consoleOut.textContent.slice(-40000);
  consoleOut.scrollTop = consoleOut.scrollHeight;
};

async function sendConsole() {
  const input = $("#console-line");
  if (!badge.connected) return;
  await badge.write(input.value + "\r");
  input.value = "";
}

// ---------- wiring ----------

function wire() {
  if (!("serial" in navigator)) {
    $("#unsupported").hidden = false;
    $("#connect").disabled = true;
  }
  for (const button of document.querySelectorAll("#tabs button")) {
    button.onclick = () => {
      document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b === button));
      document.querySelectorAll("main section").forEach((s) => s.classList.toggle("active", s.id === "tab-" + button.dataset.tab));
    };
  }
  $("#connect").onclick = connect;
  $("#reboot").onclick = () => badge.reset();
  $("#disk-mode").onclick = async () => {
    await badge.write("\x03");
    await sleep(200);
    await badge.write("import powman; powman.reset_into_msc()\r");
    toast("The badge restarts as a USB drive named BADGER.", 5000);
  };
  $("#apps-source").innerHTML = SOURCES.map((s) => `<option value="${s.id}">${escapeHtml(s.label)}</option>`).join("");
  $("#apps-source").onchange = renderStore;
  $("#apps-search").oninput = renderStore;
  $("#apps-filter").onchange = renderStore;
  $("#apps-refresh").onclick = () => {
    for (const s of SOURCES) { delete catalogues[s.id]; try { sessionStorage.removeItem("studio-tree-" + s.id); } catch (_) {} }
    badge.connected ? refreshApps() : renderStore();
  };
  $("#apps-reboot-now").onclick = () => badge.reset();
  $("#settings-save").onclick = () => saveSettings(false);
  $("#settings-reboot").onclick = () => saveSettings(true);
  $("#shot-now").onclick = () => capture(null);
  $("#shot-app-go").onclick = () => capture($("#shot-app").value);
  $("#home-save").onclick = () => saveHome(false);
  $("#home-reset").onclick = () => saveHome(true);
  wireHomeDrop();
  $("#ext-check").onclick = compareExtensions;
  $("#ext-drive").onclick = pickDrive;
  $("#ext-finish").onclick = finishDrive;
  $("#detail-close").onclick = () => $("#detail").close();
  $("#detail").onclick = (e) => { if (e.target === $("#detail")) $("#detail").close(); };
  renderDrive();
  $("#console-send").onclick = sendConsole;
  $("#console-line").onkeydown = (e) => { if (e.key === "Enter") sendConsole(); };
  $("#console-ctrlc").onclick = () => badge.write("\x03");
  $("#console-clear").onclick = () => (consoleOut.textContent = "");
  renderStore().then(openFromLink);
}

// The landing page links to studio/#app=<source>/<slug>
async function openFromLink() {
  const match = location.hash.match(/^#app=([\w-]+)\/([\w-]+)$/);
  if (!match) return;
  const source = SOURCES.find((s) => s.id === match[1]);
  if (!source) return;
  document.querySelector('#tabs [data-tab="apps"]').click();
  if ($("#apps-source").value !== source.id) {
    $("#apps-source").value = source.id;
    await renderStore();
  }
  const app = (await loadCatalogue(source)).find((a) => a.slug === match[2]);
  const card = document.querySelector(`#apps-store .card[data-slug="${match[2]}"]`);
  if (app) openDetail(source, app, card);
}

wire();
