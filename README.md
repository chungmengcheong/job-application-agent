## AI Recruiting Agent

The AI Recruiting Agent is an AI agent that maximizes your chances of landing an interview! 

Note, The code is a work-in-progress. It is not intended for use by anyone other than myself and my beta testers. I'm using this project to get hands-on experience with (a) creating and supporting an AI powered product, especially on the AI pipeline such as evals, and (b) building using the latest AI design and development tools. I wrote most of the back-end manually and vibe-coded the front-end.

### Product features
The AI Recruiting Agent is a web application that:
* Assess how the user's resume lines up against a job (description). 
* Provide a item-by-item assessment of how their experience and skills line up against a job's "must haves" and tactics to improve that alignment
* Interview them for potential additional relevant experience and skills that may not be on their resume, but might be relevant to the job 
* Recommends a redlined resume that frames the user's career narrative, experience and skills to best align with the job description, as well as phrasing tweaks to increase their ATS (Applicant Tracking System) performance
* [Future] Auto-complete the job application forms on their behalf!
* [Future] Identifies relevant 1st and 2nd degree contacts for networking into the job

Behind the scenes, the AI Recruiting Agent uses a custom AI-pipeline incorporating the developer's years of career coaching and recruiting experience together with latest LLM models.

### Using the application

The supported product is the web application at
https://airecruitingagent.pythonanywhere.com. Chrome extension development and
releases are frozen during the web-first refactor, so the extension is not a
supported installation or release target today. A future extension may return
as a thin client for browser-native capabilities after the web workflow is
proven.


### Repo details
Note:
1. /backend: The FastAPI backend (plus various utils, e.g., authentication) that serves as the main orchestrator of the AI pipeline 
2. /web: The supported web client - plain HTML/CSS/JS, no build step, served by the same FastAPI app at `/app`
3. /BrowserExtension: The frozen Next.js web app plus the frozen Chrome-extension implementation; not built or deployed. Kept until the separate Cleanup backlog item retires it (see `docs/frontend.md`).
4. /demo: fixed synthetic inputs and canned API responses used by the permanent public demo
5. /evals: A collection of evaluation scripts to assess the performance of the AI models (future)
6. /prompts: A collection of prompt templates used by the AI models
7. /tests: A collection of unit tests for the backend, plus `tests/test_web_smoke.py`, a dev-only browser smoke test of `/web`


### Deploying on PythonAnywhere

0. Set `ENVIRONMENT=production` in the deployed `.env` file. This disables
   FastAPI debug mode, which otherwise exposes tracebacks and internal
   exception detail in HTTP responses. It defaults to `development` (debug
   enabled) when unset, so local runs are unaffected.
1. Firstly, create a FastAPI ASGI app
   - pa website create --domain airecruitingagent.pythonanywhere.com \
  --command '/home/airecruitingagent/.virtualenvs/airecruitingagent-venv/bin/uvicorn --app-dir /home/airecruitingagent/airecruitingagent --uds ${DOMAIN_SOCKET} backend.api:app'
2. After each code update:
   - cd ~/airecruitingagent
   - git pull origin main
   - pa website reload --domain airecruitingagent.pythonanywhere.com

### Deploying locally

The backend serves the web client itself - one process, no separate frontend
dev server, build, or watch step:

```
source .venv/bin/activate   # if you're using the repo's venv
uvicorn backend.api:app --reload --port 8000
```

Then browse to http://127.0.0.1:8000/app/. Editing any file under `web/`
takes effect on the next refresh. Your `.env` already has `LLM_API_KEY`,
`GOOGLE_WEB_CLIENT_ID`, `ALLOWED_EMAILS`, etc. set, so this should just work.

### Testing the web client

```
node --test web/tests/*.test.mjs                 # pure-logic unit tests
pip install -r requirements-dev.txt               # dev-only, not a runtime dependency
playwright install chromium                        # once
pytest tests/test_web_smoke.py                     # production-like browser smoke test
``` 