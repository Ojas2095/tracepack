"""Dependency-free renderers for TracePack's human-facing artifacts."""

from __future__ import annotations

from datetime import datetime
from html import escape
import json
from typing import Sequence

from .core import EvidenceFile, TimelineEvent


def _human_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    return f"{value / (1024 * 1024):.1f} MB"


def _display_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _markdown_cell(value: str) -> str:
    return _markdown_safe(value).replace("|", "\\|").replace("\n", " ")


def _markdown_safe(value: str) -> str:
    """Keep evidence-derived Markdown text inert when rendered by a viewer."""

    return escape(value, quote=False).replace("`", "\\`").replace("\\", "\\\\")


def _event_json(event: TimelineEvent) -> str:
    return json.dumps(
        {"at": event.at.isoformat(), "source": event.source, "label": event.label, "detail": event.detail},
        ensure_ascii=False,
    )


def render_timeline(timeline: Sequence[TimelineEvent]) -> str:
    lines = ["# TracePack timeline", "", "Chronological events extracted from evidence content, with file metadata fallbacks.", ""]
    if not timeline:
        lines.append("No evidence files were found.")
        return "\n".join(lines) + "\n"
    for event in timeline:
        lines.extend(
            [
                f"## {_display_time(event.at)} — {event.label}",
                f"**Source:** `{_markdown_cell(event.source)}`  ",
                _markdown_safe(event.detail),
                "",
            ]
        )
    return "\n".join(lines)


def render_markdown_summary(
    title: str,
    evidence: Sequence[EvidenceFile],
    timeline: Sequence[TimelineEvent],
    manifest_hash: str,
    generated_at: datetime,
) -> str:
    categories: dict[str, int] = {}
    total_bytes = 0
    for item in evidence:
        categories[item.category] = categories.get(item.category, 0) + 1
        total_bytes += item.size
    category_text = ", ".join(f"{name} ({count})" for name, count in sorted(categories.items())) or "None"
    lines = [
        f"# {_markdown_safe(title)}",
        "",
        "> Offline-generated evidence brief by TracePack.",
        "",
        f"Generated: `{generated_at.strftime('%Y-%m-%d %H:%M UTC')}`  ",
        f"Integrity: `{manifest_hash}` (SHA-256 of `manifest.json`)",
        "",
        "## At a glance",
        "",
        f"- **{len(evidence)}** evidence files totaling **{_human_bytes(total_bytes)}**",
        f"- **{len(timeline)}** timeline events",
        f"- Categories: {category_text}",
        "",
        "## Evidence inventory",
        "",
        "| File | Type | Size | SHA-256 |",
        "| --- | --- | ---: | --- |",
    ]
    for item in evidence:
        lines.append(
            f"| `{_markdown_cell(item.relative_path)}` | {_markdown_cell(item.category)} | "
            f"{_human_bytes(item.size)} | `{item.sha256}` |"
        )
    if not evidence:
        lines.append("| *(none)* | — | — | — |")
    lines.extend(["", "## Timeline snapshot", ""])
    for event in timeline[:12]:
        lines.append(f"- **{_display_time(event.at)}** · `{_markdown_cell(event.source)}` — {_markdown_safe(event.detail)}")
    if len(timeline) > 12:
        lines.append(f"- _…and {len(timeline) - 12} more events in `timeline.md`._")
    lines.extend(["", "## How to use this pack", "", "Open `case_pack.html` locally for full-text search and category filters. Everything in this folder is self-contained and works without a network connection.", ""])
    return "\n".join(lines)


def render_html(
    title: str,
    evidence: Sequence[EvidenceFile],
    timeline: Sequence[TimelineEvent],
    manifest_hash: str,
    generated_at: datetime,
) -> str:
    total_bytes = sum(item.size for item in evidence)
    categories = sorted({item.category for item in evidence})
    category_options = "".join(
        f'<button class="filter-chip" type="button" aria-pressed="false" data-filter="{escape(category, quote=True)}">{escape(category)}</button>'
        for category in categories
    )
    timeline_markup = "".join(
        f"""
        <li class="timeline-item">
          <time datetime="{escape(event.at.isoformat(), quote=True)}">{escape(_display_time(event.at))}</time>
          <div><strong>{escape(event.label)}</strong><span class="timeline-source">{escape(event.source)}</span>
          <p>{escape(event.detail)}</p></div>
        </li>"""
        for event in timeline[:40]
    )
    cards: list[str] = []
    for item in evidence:
        content = item.content if item.is_text else "Binary or non-text evidence. Download the complete source below."
        if item.content_truncated:
            content += "\n\n[TracePack preview truncated at 512 KB; the SHA-256 covers the complete source file.]"
        search_text = f"{item.relative_path} {item.category} {item.extension} {item.content}".lower()
        cards.append(
            f"""
            <article class="evidence-card" data-category="{escape(item.category, quote=True)}" data-search="{escape(search_text[:20000], quote=True)}">
              <div class="card-topline"><span class="badge">{escape(item.category)}</span><span class="file-size">{_human_bytes(item.size)}</span></div>
              <h3>{escape(item.relative_path)}</h3>
              <p class="file-meta">{escape(item.extension)} · modified {escape(_display_time(item.modified_at))}</p>
              <details><summary>View evidence preview</summary><pre>{escape(content)}</pre></details>
              <p class="source-link"><a href="evidence/{escape(item.relative_path, quote=True)}" download>Open complete source ↗</a></p>
              <div class="hash-row" title="SHA-256">SHA-256 <code>{escape(item.sha256)}</code></div>
            </article>"""
        )
    cards_markup = "".join(cards) or '<div class="empty-state">No evidence files found in this folder.</div>'
    serialized_events = escape(json.dumps([_event_json(event) for event in timeline[:40]]), quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#102a43">
  <title>{escape(title)} · TracePack</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="hero">
    <div class="shell hero-inner">
      <div class="eyebrow"><span class="pulse"></span> TRACEPACK / OFFLINE CASE PACK</div>
      <h1>{escape(title)}</h1>
      <p class="lede">A searchable evidence room built for calm review, clear chronology, and verifiable handoffs.</p>
      <div class="hero-meta"><span>Generated {escape(_display_time(generated_at))}</span><span class="dot">•</span><span>SHA-256 verified manifest</span></div>
    </div>
  </header>
  <main class="shell">
    <section class="stats" aria-label="Case statistics">
      <div class="stat-card"><span class="stat-label">Evidence files</span><strong>{len(evidence)}</strong><span class="stat-foot">indexed locally</span></div>
      <div class="stat-card"><span class="stat-label">Evidence volume</span><strong>{escape(_human_bytes(total_bytes))}</strong><span class="stat-foot">source bytes</span></div>
      <div class="stat-card"><span class="stat-label">Timeline events</span><strong>{len(timeline)}</strong><span class="stat-foot">chronological signals</span></div>
      <div class="stat-card accent"><span class="stat-label">Manifest</span><strong>{escape(manifest_hash[:12])}</strong><span class="stat-foot">SHA-256 prefix</span></div>
    </section>
    <section class="workspace">
       <div class="section-heading"><div><span class="section-kicker">01 / FIND YOUR SIGNAL</span><h2>Evidence index</h2></div><span id="result-count" class="result-count" aria-live="polite">{len(evidence)} shown</span></div>
       <div class="toolbar">
         <label class="search-box"><span aria-hidden="true">⌕</span><span class="sr-only">Search evidence</span><input id="search" type="search" placeholder="Search files, notes, hashes…" autocomplete="off"><kbd>/</kbd></label>
         <div class="filter-row" role="group" aria-label="Filter evidence"><button class="filter-chip active" type="button" aria-pressed="true" data-filter="all">All</button>{category_options}</div>
       </div>
       <div id="evidence-grid" class="evidence-grid">{cards_markup}<p id="empty-results" class="empty-state" hidden>No matching evidence. Clear the search or choose All.</p></div>
    </section>
    <section class="timeline-section">
      <div class="section-heading"><div><span class="section-kicker">02 / FOLLOW THE THREAD</span><h2>Chronology</h2></div><a class="text-link" href="timeline.md">Open Markdown timeline ↗</a></div>
      <ol class="timeline">{timeline_markup or '<li class="empty-state">No timeline signals found.</li>'}</ol>
    </section>
    <footer class="pack-footer"><div><strong>TracePack</strong><span>Offline by default. Review with confidence.</span></div><div><a href="summary.md">Summary</a><a href="manifest.json">Manifest</a><a href="manifest.sha256">Checksum</a></div></footer>
  </main>
  <script id="timeline-data" type="application/json">{serialized_events}</script>
  <script src="app.js"></script>
</body>
</html>
"""


def styles_css() -> str:
    return r""":root {
  --ink: #102a43;
  --muted: #627d98;
  --line: #d9e2ec;
  --paper: #f6f8fb;
  --card: #ffffff;
  --teal: #0d9488;
  --teal-soft: #ccfbf1;
  --amber: #f59e0b;
  --shadow: 0 18px 40px rgba(16, 42, 67, .08);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin: 0; color: var(--ink); background: var(--paper); font: 15px/1.6 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
a { color: inherit; }
.shell { width: min(1160px, calc(100% - 40px)); margin: 0 auto; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.hero { color: #f5fbff; background: radial-gradient(circle at 85% 10%, rgba(45, 212, 191, .28), transparent 33%), linear-gradient(135deg, #102a43 0%, #163e5c 55%, #0f766e 130%); padding: 64px 0 74px; }
.hero-inner { max-width: 900px; }
.eyebrow, .section-kicker, .stat-label { letter-spacing: .13em; text-transform: uppercase; font-size: 11px; font-weight: 800; }
.eyebrow { color: #99f6e4; display: flex; align-items: center; gap: 9px; }
.pulse { width: 8px; height: 8px; border-radius: 50%; background: #5eead4; box-shadow: 0 0 0 5px rgba(94, 234, 212, .12); }
h1 { max-width: 780px; margin: 16px 0 12px; font-size: clamp(36px, 6vw, 66px); letter-spacing: -.045em; line-height: 1.02; }
.lede { max-width: 620px; margin: 0; color: #d9f0f0; font-size: 19px; line-height: 1.55; }
.hero-meta { display: flex; flex-wrap: wrap; gap: 11px; margin-top: 28px; color: #b7d5df; font-size: 13px; }
.dot { color: #5eead4; }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: -31px; position: relative; }
.stat-card { background: var(--card); border: 1px solid rgba(217, 226, 236, .9); border-radius: 12px; padding: 18px 20px; box-shadow: var(--shadow); }
.stat-card.accent { background: #ecfdf5; border-color: #a7f3d0; }
.stat-label { display: block; color: var(--muted); font-size: 10px; }
.stat-card strong { display: block; margin: 4px 0 1px; font-size: 27px; letter-spacing: -.04em; }
.stat-foot { color: var(--muted); font-size: 12px; }
.workspace, .timeline-section { padding: 72px 0 0; }
.section-heading { display: flex; align-items: end; justify-content: space-between; gap: 20px; margin-bottom: 22px; }
.section-kicker { color: var(--teal); }
h2 { margin: 5px 0 0; font-size: 29px; letter-spacing: -.035em; }
.result-count, .text-link { color: var(--muted); font-size: 13px; }
.text-link { text-decoration: none; border-bottom: 1px solid #b7c8d8; padding-bottom: 2px; }
.toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 14px; align-items: center; margin-bottom: 22px; }
.search-box { display: flex; align-items: center; gap: 10px; flex: 1 1 300px; max-width: 540px; padding: 10px 13px; color: var(--muted); background: white; border: 1px solid var(--line); border-radius: 9px; }
.search-box:focus-within { border-color: var(--teal); box-shadow: 0 0 0 3px rgba(13, 148, 136, .1); }
.search-box input { min-width: 0; flex: 1; border: 0; outline: 0; color: var(--ink); background: transparent; font: inherit; }
kbd { padding: 1px 6px; color: var(--muted); background: #edf2f7; border: 1px solid var(--line); border-radius: 4px; font-size: 11px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 7px; }
.filter-chip { cursor: pointer; color: var(--muted); background: transparent; border: 1px solid var(--line); border-radius: 999px; padding: 7px 12px; font: 700 12px inherit; }
.filter-chip:hover, .filter-chip.active { color: #0f766e; border-color: #5eead4; background: var(--teal-soft); }
.filter-chip:focus-visible, a:focus-visible, summary:focus-visible, input:focus-visible { outline: 3px solid #f59e0b; outline-offset: 2px; }
.evidence-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 17px; }
.evidence-card { min-width: 0; overflow: hidden; display: flex; flex-direction: column; background: var(--card); border: 1px solid var(--line); border-radius: 12px; box-shadow: 0 5px 20px rgba(16, 42, 67, .035); }
.evidence-card:hover { border-color: #9fb3c8; box-shadow: var(--shadow); }
.card-topline { display: flex; justify-content: space-between; align-items: center; padding: 17px 18px 0; }
.badge { color: #0f766e; background: var(--teal-soft); border-radius: 5px; padding: 3px 8px; font-size: 10px; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.file-size { color: var(--muted); font-size: 12px; }
.evidence-card h3 { overflow-wrap: anywhere; margin: 12px 18px 2px; font: 700 17px/1.3 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.file-meta { margin: 0 18px 14px; color: var(--muted); font-size: 12px; }
details { border-top: 1px solid #edf2f7; }
summary { cursor: pointer; padding: 11px 18px; color: #334e68; font-weight: 700; font-size: 13px; }
summary:hover { color: var(--teal); }
pre { overflow: auto; max-height: 280px; margin: 0; padding: 14px 18px 17px; color: #334e68; background: #f8fafc; border-top: 1px solid #edf2f7; white-space: pre-wrap; overflow-wrap: anywhere; font: 12px/1.65 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.hash-row { overflow-wrap: anywhere; margin-top: auto; padding: 12px 18px 15px; color: var(--muted); border-top: 1px solid #edf2f7; font-size: 10px; letter-spacing: .04em; }
.hash-row code { color: #486581; font-size: 10px; }
.source-link { margin: 0; padding: 10px 18px; border-top: 1px solid #edf2f7; color: #0f766e; font-size: 12px; font-weight: 700; }
.source-link a { text-decoration: none; }
.timeline { position: relative; list-style: none; margin: 0; padding: 3px 0 0 28px; }
.timeline::before { content: ""; position: absolute; left: 6px; top: 5px; bottom: 5px; width: 2px; background: #b7e4dd; }
.timeline-item { position: relative; display: grid; grid-template-columns: 165px 1fr; gap: 25px; padding: 0 0 28px; }
.timeline-item::before { content: ""; position: absolute; left: -28px; top: 6px; width: 10px; height: 10px; border: 3px solid var(--paper); border-radius: 50%; background: var(--teal); box-shadow: 0 0 0 1px #5eead4; }
.timeline-item time { color: var(--muted); font: 700 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace; }
.timeline-item strong { display: block; font-size: 15px; }
.timeline-source { display: block; margin-top: 2px; color: var(--teal); font: 12px ui-monospace, SFMono-Regular, Menlo, monospace; overflow-wrap: anywhere; }
.timeline-item p { margin: 7px 0 0; color: #486581; font-size: 14px; }
.empty-state { grid-column: 1 / -1; padding: 34px; color: var(--muted); text-align: center; background: white; border: 1px dashed #b7c8d8; border-radius: 10px; }
.pack-footer { display: flex; justify-content: space-between; gap: 20px; margin: 58px 0 30px; padding-top: 20px; color: var(--muted); border-top: 1px solid var(--line); font-size: 12px; }
.pack-footer strong { display: block; color: var(--ink); }
.pack-footer a { margin-left: 18px; text-decoration: none; }
.pack-footer a:hover { color: var(--teal); }
@media (max-width: 760px) { .shell { width: min(100% - 28px, 620px); } .hero { padding: 45px 0 62px; } .stats { grid-template-columns: repeat(2, 1fr); } .evidence-grid { grid-template-columns: 1fr; } .timeline-item { display: block; } .timeline-item time { display: block; margin-bottom: 5px; } .pack-footer { display: block; } .pack-footer > div:last-child { margin-top: 14px; } .pack-footer a { margin: 0 18px 0 0; } }
@media (max-width: 420px) { .stats { grid-template-columns: 1fr; } .section-heading { align-items: start; flex-direction: column; gap: 5px; } }
"""


def app_js() -> str:
    return r"""(() => {
  const search = document.querySelector('#search');
  const cards = [...document.querySelectorAll('.evidence-card')];
  const chips = [...document.querySelectorAll('.filter-chip')];
  const resultCount = document.querySelector('#result-count');
  const emptyResults = document.querySelector('#empty-results');
  let activeFilter = 'all';

  function applyFilters() {
    const query = (search.value || '').trim().toLowerCase();
    let visible = 0;
    cards.forEach((card) => {
      const categoryMatch = activeFilter === 'all' || card.dataset.category === activeFilter;
      const searchMatch = !query || `${card.dataset.search} ${card.textContent}`.toLowerCase().includes(query);
      const show = categoryMatch && searchMatch;
      card.hidden = !show;
      if (show) visible += 1;
    });
    resultCount.textContent = `${visible} shown`;
    emptyResults.hidden = visible !== 0;
  }

  search.addEventListener('input', applyFilters);
  chips.forEach((chip) => chip.addEventListener('click', () => {
    activeFilter = chip.dataset.filter;
    chips.forEach((item) => {
      const selected = item === chip;
      item.classList.toggle('active', selected);
      item.setAttribute('aria-pressed', String(selected));
    });
    applyFilters();
  }));
  document.addEventListener('keydown', (event) => {
    if (event.key === '/' && document.activeElement !== search) {
      event.preventDefault();
      search.focus();
    }
  });
})();
"""
