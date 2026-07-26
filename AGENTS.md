# Repository Guidelines

## Project Structure & Module Organization
- `backend/` holds the FastAPI app (`api.py`, `security.py`, `redline.py`) plus shared resources in `prompts/`, `demo/`, `static/`, `user/`, and scratch data in `temp/`. Keep new orchestrators or utilities under `backend/` and reference prompt templates from `prompts/`.
- `BrowserExtension/` is a Next.js + TypeScript workspace; UI components live in `components/`, panels in `pages/` and `app/`, and Chrome-specific glue (manifest, scripts, build artifacts) lives beside them. Built artifacts land in `BrowserExtension/dist-extension/` and production bundles are mirrored under `releases/`.
- `test/` mirrors key backend resources (fixture users, stub temp files) and contains pytest suites such as `test_api.py`. Front-end demos that mock the API responses reside in `demo/`.

## Build, Test, and Development Commands
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt                    # install backend deps
uvicorn backend.api:app --reload --port 8000       # run FastAPI locally
pytest test                                        # execute backend unit tests
cd BrowserExtension && npm install                 # install UI deps
npm run dev                                        # Next.js dev server
BACKEND_URL=http://localhost:8000 npm run build-extension   # ship Chrome build
```
Use `npm run build` for a pure Next.js static build and `npm run lint` to run ESLint.

## Coding Style & Naming Conventions
- Python: 4-space indentation, module-level docstrings, and typed function signatures as shown in `backend/api.py`. Name modules and files in `snake_case`, classes or Pydantic models in `PascalCase`, and constants in `UPPER_SNAKE_CASE`.
- TypeScript/React: follow functional components, co-locate styles (Tailwind) with components, and rely on Next.js aliases already defined in `tsconfig.json`. Run `npm run lint` before submitting UI work.
- Keep prompt templates suffixed with `_GOLD.txt`, demo payloads named `*_demo.*`, and temp stubs under `test/temp_stub/` to make fixtures easy to recognize.

## Testing Guidelines
Backend coverage relies on pytest fixtures that stub Google auth and LLM responses (see `test/test_api.py`). Add new tests under `test/` with the `test_*.py` naming pattern and ensure each new endpoint has at least one demo-mode test plus a mocked real-mode path. Document any manual BrowserExtension verification (e.g., “loaded panel via `npm run dev` and confirmed resume diff renders”) in PRs.

## Commit & Pull Request Guidelines
Recent history (`git log`) shows short, imperative, lower-case messages (“added proxy for pythonanywhere…”). Follow that style, start with the affected area (`backend:`, `extension:`) when helpful, and keep subjects under ~72 characters. Pull requests should outline 1) the problem and solution, 2) environments tested (`pytest`, `npm run lint`, manual extension build), 3) screenshots or screen recordings for UI changes, and 4) linked issues or TODOs.

## Security & Configuration Tips
Never commit `.env`, user resumes, or generated `temp/` data. The backend autoloads credentials such as `GROQ_API_KEY`, `LANGSMITH_API_KEY`, `GOOGLE_WEB_CLIENT_ID`, `ALLOWED_EMAILS`, `ALLOWED_DOMAINS`, and `CHROME_EXTENSION_ID`; ensure these exist locally before running `uvicorn`. LangSmith tracing defaults on for development; set `LANGSMITH_TRACING_V2=false` in production until content and access guards are implemented. When building Chrome packages, double-check `BACKEND_URL` so demo builds do not leak private staging endpoints, and reset any test resumes placed in `user/` after validating features.
