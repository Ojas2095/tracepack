# TracePack

**TracePack** is an offline-first evidence-to-case-pack utility for the OmniRush Frontier Buildathon — Agents & Automation track. Give it a folder of evidence files and it produces a polished, locally searchable HTML review room, a Markdown brief, a chronological timeline, and a SHA-256 integrity manifest.

The project is deliberately small and reproducible: Python 3.13.6 plus the standard library, no runtime network calls, and no third-party packages to download.

## What it does

TracePack walks an evidence folder recursively and, for every regular file:

- records a stable relative path, category, size, modified time, and SHA-256 digest;
- reads a bounded UTF-8 preview for text-like files and safely labels binary evidence;
- extracts ISO-like timestamps from filenames and text lines into a chronological timeline;
- renders `case_pack.html` with local search, category filters, responsive styling, and expandable previews;
- writes `summary.md`, `timeline.md`, `manifest.json`, `manifest.sha256`, `styles.css`, and `app.js`.

Everything in the generated output folder is self-contained. Open the HTML file directly in a browser; it does not need a server or an internet connection.

## Requirements

- Python **3.13.6**, pinned in `.python-version`.
- `make` for the documented one-command test target (or run the command inside the target directly).
- Docker is optional for container builds.

There are no runtime dependencies. `requirements.txt` and `requirements.lock` are intentionally empty of packages so a clean offline checkout remains reproducible.

## Setup

From the project root:

```sh
python --version
python -m venv .venv
# macOS/Linux
. .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The install step has no network work to do. TracePack is run from the repository root, so no package installation is required.

## Run TracePack

Build a case pack from any evidence folder:

```sh
python -m tracepack build path/to/evidence \
  --output path/to/case-pack \
  --title "Quarterly access review"
```

If the output folder already contains files, add `--force` to replace it. Then open `path/to/case-pack/case_pack.html` locally.

The CLI also supports:

```sh
python -m tracepack --help
python -m tracepack --version
```

## Demo

The repository includes a compact, realistic fixture set with notes, logs, CSV data, and an SVG diagram:

```sh
python -m tracepack build demo/evidence \
  --output demo/output \
  --title "Morning reconciliation review" \
  --force
```

Open `demo/output/case_pack.html`. Try the `/` keyboard shortcut, search for `retry`, and switch between the evidence categories. The generated `manifest.sha256` can be checked with a local SHA-256 tool if desired.

## Test

The single documented test command uses only `unittest` from the Python standard library:

```sh
make test
```

Equivalent command when `make` is unavailable:

```sh
python -m unittest discover -s tests -v
```

The tests cover recursive discovery and ordering, binary/text handling, SHA-256 values, timestamp extraction, timeline fallbacks, HTML escaping/search hooks, manifest integrity, and CLI overwrite behavior.

## Docker

Build and run the dependency-free image:

```sh
docker build -t tracepack .
docker run --rm tracepack
```

To build a pack from a mounted local folder, mount it at a container path and override the default command:

```sh
docker run --rm \
  -v "$(pwd)/demo:/work/demo" \
  tracepack \
  python -m tracepack build /work/demo/evidence --output /work/demo/output --title "Container demo" --force
```

## Deploy / handoff

TracePack's deployment artifact is the generated case-pack folder. Copy or archive that folder to the intended review location, then open `case_pack.html`. For a quick local preview of the same static folder, run `python -m http.server` from inside the output folder; the page still makes no network requests.

## Design notes and limitations

- Text previews are capped at 512 KiB per source file to keep a case pack responsive. Hashes always cover the complete source file.
- Binary files are indexed by metadata and digest but are not embedded in the HTML.
- Timeline extraction recognizes `YYYY-MM-DD`, ISO timestamps, and common UTC/offset forms. Files without a content timestamp use their filesystem modification time.
- Generated timestamps reflect the local run time, while file ordering and manifest entries are stable by relative path.
- No secrets, credentials, telemetry, or network services are used.
