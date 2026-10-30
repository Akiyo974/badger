// Guides page: renders the Markdown guides of this folder, the same files
// GitHub shows. #radar opens radar.md; #index:some-heading scrolls to a heading.

"use strict";

const GUIDES = [
  ["index", "Start here"],
  ["badge", "Badge"],
  ["contacts", "Contacts"],
  ["radar", "Radar"],
  ["duck_maze", "Duck Maze"],
  ["pedometer", "Pedometer"],
  ["mona_pet", "Mona Pet"],
  ["menu", "Menu"],
  ["badger_remote", "Badger Remote"],
  ["bluetooth", "Bluetooth from a computer"],
];

const $ = (selector) => document.querySelector(selector);

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// The id GitHub gives a heading, so README.md#a-heading links work here too
function slug(text) {
  return text.toLowerCase().replace(/<[^>]+>/g, "").replace(/[^\w\- ]/g, "").trim().replace(/ /g, "-");
}

// A link of a guide, for this page: other guides become #routes
function href(target) {
  const guide = target.match(/^([\w-]+)\.md(?:#(.*))?$/);
  if (guide) {
    const name = guide[1] === "README" ? "index" : guide[1];
    return "#" + name + (guide[2] ? ":" + guide[2] : "");
  }
  return target;
}

function inline(text) {
  const codes = [];
  let html = escapeHtml(text).replace(/`([^`]+)`/g, (_, code) => `\u0000${codes.push(code) - 1}\u0000`);
  html = html
    .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_, alt, src) => `<img src="${src}" alt="${alt}" loading="lazy">`)
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, target) => {
      const url = href(target.replace(/&amp;/g, "&"));
      const outside = /^https?:/.test(url);
      return `<a href="${escapeHtml(url)}"${outside ? ' target="_blank" rel="noopener"' : ""}>${label}</a>`;
    })
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, "$1<i>$2</i>");
  return html.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[i]}</code>`);
}

function cells(line) {
  return line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
}

// The Markdown the guides use: headings, paragraphs, lists, tables, code, images
function markdown(text) {
  const lines = text.split(/\r?\n/);
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (line.trim().startsWith("```")) {
      const code = [];
      for (i++; i < lines.length && !lines[i].trim().startsWith("```"); i++) code.push(lines[i].replace(/^ {3}/, ""));
      out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
      i++;
      continue;
    }
    const heading = line.match(/^(#{1,3})\s+(.*)/);
    if (heading) {
      const level = heading[1].length;
      const content = inline(heading[2]);
      out.push(`<h${level} id="${slug(heading[2])}">${content}</h${level}>`);
      i++;
      continue;
    }
    if (line.trim().startsWith("|")) {
      const rows = [];
      for (; i < lines.length && lines[i].trim().startsWith("|"); i++) rows.push(lines[i]);
      const body = rows.filter((r) => !/^\|[\s|:-]+\|$/.test(r.trim()));
      const [head, ...rest] = body;
      out.push(`<div class="table"><table><thead><tr>${cells(head).map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>`
        + rest.map((r) => `<tr>${cells(r).map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`).join("")
        + "</tbody></table></div>");
      continue;
    }
    const item = line.match(/^(\s*)([-*]|\d+\.)\s+(.*)/);
    if (item) {
      const ordered = /\d/.test(item[2]);
      const items = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)([-*]|\d+\.)\s+(.*)/);
        if (m) { items.push([m[3]]); i++; continue; }
        // An indented line or a code block belongs to the item above
        if (items.length && /^\s{2,}\S/.test(lines[i])) {
          const block = [];
          while (i < lines.length && (/^\s{2,}/.test(lines[i]) || !lines[i].trim()) && !/^(\s*)([-*]|\d+\.)\s/.test(lines[i])) {
            block.push(lines[i]);
            i++;
          }
          while (block.length && !block[block.length - 1].trim()) block.pop();
          items[items.length - 1].push(markdown(block.map((l) => l.replace(/^\s{3}/, "")).join("\n")));
          continue;
        }
        // A blank line goes on with the list when an item or an indented block follows
        if (!lines[i].trim() && /^(\s*([-*]|\d+\.)\s|\s{2,}\S)/.test(lines[i + 1] || "")) { i++; continue; }
        break;
      }
      const tag = ordered ? "ol" : "ul";
      out.push(`<${tag}>${items.map(([first, ...more]) => `<li>${inline(first)}${more.join("")}</li>`).join("")}</${tag}>`);
      continue;
    }
    if (!line.trim()) { i++; continue; }
    const para = [];
    for (; i < lines.length && lines[i].trim() && !/^(#{1,3}\s|\||```|\s*([-*]|\d+\.)\s)/.test(lines[i]); i++) para.push(lines[i].trim());
    // An image alone in its paragraph stands as a figure
    out.push(para.length === 1 && /^!\[/.test(para[0]) ? inline(para[0]) : `<p>${inline(para.join(" "))}</p>`);
  }
  return out.join("\n");
}

const cache = {};

async function show() {
  const [name, anchor] = decodeURIComponent(location.hash.slice(1)).split(":");
  const index = Math.max(0, GUIDES.findIndex(([id]) => id === (name || "index")));
  const [id, title] = GUIDES[index];
  for (const link of document.querySelectorAll("#nav a")) link.classList.toggle("on", link.dataset.id === id);
  const article = $("#guide");
  // Only the guide asked last shows: a slower one may arrive after it
  const asked = location.hash;
  try {
    cache[id] ||= fetch(`${id === "index" ? "README" : id}.md`).then((r) => {
      if (!r.ok) throw new Error(`the guide answered ${r.status}`);
      return r.text();
    });
    const text = await cache[id];
    if (location.hash !== asked) return;
    const previous = GUIDES[index - 1], next = GUIDES[index + 1];
    article.innerHTML = markdown(text)
      + `<div class="pager"><span>${previous ? `<a href="#${previous[0]}">← ${escapeHtml(previous[1])}</a>` : ""}</span>`
      + `<span>${next ? `<a href="#${next[0]}">${escapeHtml(next[1])} →</a>` : ""}</span></div>`;
    document.title = id === "index" ? "Badge Guides" : `${title} guide`;
  } catch (error) {
    cache[id] = null;
    if (location.hash !== asked) return;
    article.innerHTML = `<p class="muted">This guide could not be loaded (${escapeHtml(error.message)}). It is also on <a href="https://github.com/Akiyo974/badger/tree/main/docs/guides">GitHub</a>.</p>`;
  }
  const target = anchor && document.getElementById(anchor);
  if (target) target.scrollIntoView();
  else window.scrollTo(0, 0);
}

for (const [id, title] of GUIDES) {
  const link = document.createElement("a");
  link.href = "#" + id;
  link.dataset.id = id;
  link.textContent = title;
  $("#nav").appendChild(link);
}
window.addEventListener("hashchange", show);
show();
