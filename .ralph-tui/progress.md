# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

- **pytest pythonpath**: `pytest.ini` with `pythonpath = .` is required to import root-level modules (cache.py, config.py, etc.) from tests/. Without it, `from cache import Cache` fails with ModuleNotFoundError.

---

## 2026-04-07 - US-001
- Implemented full project scaffold from scratch
- Files created: sources/__init__.py, requirements.txt, package.json, tsconfig.json, config.example.json, config.json, .gitignore, src/app.ts
- Directories created: sources/, tests/, src/modules/, static/js/, static/css/, systemd/
- Python venv created at .venv/ with all pinned dependencies installed
- npm install completed with esbuild ^0.20.0 and typescript ^5.4.0
- TypeScript typecheck passes (tsc --noEmit)
- **Learnings:**
  - tsconfig.json needs `"moduleResolution": "bundler"` for esbuild compatibility with ESNext module target
  - src/app.ts must exist (even as a stub) for tsc to have something to check
  - config.json is gitignored and copied from config.example.json
---

## 2026-04-07 - US-002
- Implemented Pydantic response models in models.py
- Files changed: models.py (new)
- **Learnings:**
  - Use `.venv/bin/python3` to run Python in this project (venv at .venv/)
  - `list[Photo]` syntax works fine with Python 3.11+ and pydantic v2
---

## 2026-04-07 - US-003
- Implemented typed config loader using Python dataclasses
- Files changed: config.py (new), tests/conftest.py (new), tests/test_config.py (new)
- **Learnings:**
  - No mypy in requirements.txt; typecheck means syntax/import correctness only for now
  - camelCase JSON keys are mapped manually in load_config() — no external library needed
  - pytest conftest.py with tmp_path fixture works well for file-based config tests
---

## 2026-04-07 - US-004
- Implemented in-memory TTL cache using `time.monotonic()` for expiry
- Files changed: cache.py (new), tests/test_cache.py (new), pytest.ini (new)
- **Learnings:**
  - pytest.ini with `pythonpath = .` is needed so tests can import root-level modules
  - `time.monotonic()` is preferred over `time.time()` for TTL expiry (immune to clock adjustments)
  - TTL=0 entries expire immediately; a 10ms sleep reliably triggers expiry in tests
---

## 2026-04-07 - US-005
- Implemented FastAPI skeleton with mock /api/data endpoint
- Files created: main.py, static/index.html, tests/test_api.py
- Files changed: pytest.ini (added asyncio_mode = auto)
- **Learnings:**
  - `asyncio_mode = auto` in pytest.ini allows async test functions without `@pytest.mark.asyncio` decorator
  - `ASGITransport` from httpx is the correct way to test FastAPI apps without a running server; use `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`
  - FastAPI catch-all route `/{full_path:path}` must be defined AFTER specific routes (like /api/data) and static mounts to avoid shadowing them
  - `create_app(config_path)` factory pattern lets tests inject a temp config file, avoiding dependency on real config.json at test time
  - `StaticFiles(directory=...)` raises `RuntimeError` if the directory doesn't exist at mount time — directories must exist before app startup
---
