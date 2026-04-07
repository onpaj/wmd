# Ralph Progress Log

This file tracks progress across iterations. Agents update this file
after each iteration and it's included in prompts for context.

## Codebase Patterns (Study These First)

*Add reusable patterns discovered during development here.*

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
