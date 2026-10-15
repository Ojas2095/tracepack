# TracePack build provenance

TracePack was started and implemented in the OmniRush Frontier Buildathon workspace for the **Agents & Automation** track. This document contains no credentials, private prompts, tokens, or account data; it records only the public build artifact and reproducible checks.

## Public artifact

- Repository: <https://github.com/Ojas2095/tracepack>
- Live demo: <https://ojas2095.github.io/tracepack/>
- Buildathon track: Agents & Automation

## Reproduce from a clean checkout

```sh
python --version
python -m unittest discover -s tests -v
python -m tracepack build demo/evidence --output demo/output --title "TracePack demo" --force
python -m tracepack verify demo/output
```

The application uses only the Python 3.13.6 standard library. The output includes the original evidence under `evidence/`, a searchable HTML review room, Markdown artifacts, and a manifest whose copied source hashes can be verified without network access.

## Verification evidence

- GitHub Actions runs the test suite and publishes the static demo.
- The published demo is generated from the committed `demo/evidence/` fixtures.
- The local test suite covers safe path boundaries, transactional replacement, malformed timestamps, copied evidence, tamper detection, HTML escaping, accessibility hooks, and the main CLI behavior.
