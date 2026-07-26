## AI Recruiting Agent

The AI Recruiting Agent is an AI agent that maximizes your chances of landing an interview! 

Note, The code is a work-in-progress. It is not intended for use by anyone other than myself and my beta testers. I'm using this project to get hands-on experience with (a) creating and supporting an AI powered product, especially on the AI pipeline such as evals, and (b) building using the latest AI design and development tools. I wrote most of the back-end manually and vibe-coded the front-end.

### Product features
The AI Recruiting Agent interacts with user through a Chrome extension to:
* Assess how the user's resume lines up against a job (description). 
* Provide a item-by-item assessment of how their experience and skills line up against a job's "must haves" and tactics to improve that alignment
* Interview them for potential additional relevant experience and skills that may not be on their resume, but might be relevant to the job 
* Recommends a redlined resume that frames the user's career narrative, experience and skills to best align with the job description, as well as phrasing tweaks to increase their ATS (Applicant Tracking System) performance
* [Future] "Agentically" auto-complete the job application forms on their behalf!
* [Future] Identifies relevant 1st and 2nd degree contacts for networking into the job

Behind the scenes, the AI Recruiting Agent uses a custom AI-pipeline incorporating the developer's years of career coaching and recruiting experience together with latest LLM models.

### Installation instructions
To install the latest version of the compiled chrome extension:
1. Download the entire "dist-extension" directory from /releases
2. Open Chrome and go to chrome://extensions/
3. Turn on "Developer mode" (top right)
4. Click "Load unpacked" and select the "dist-extension" directory
5. The extension should now appear in your list of extensions (top right of the browser window)

Or you can use the web version (beta) of the extension at https://airecruitingagent.pythonanywhere.com 


### Compiling the browser extension

Run the following command from the /BrowserExtension directory to build the browser extension: 
- To use the production backend: npm run build-extension. 
- To use a local backend: BACKEND_URL=http://localhost:8000 npm run build-extension


### Repo details
Note:
1. /backend: The FastAPI backend (plus various utils, e.g., authentication) that serves as the main orchestrator of the AI pipeline 
2. /BrowserExtension: A Chrome extension that provides the user interface and interacts with the backend. This was initially built using v0.dev, but has since been heavily modified.
3. /demo: stubbed API responses used by the front-end during demo mode
4. /evals: A collection of evaluation scripts to assess the performance of the AI models (future)
5. /prompts: A collection of prompt templates used by the AI models
6. /tests: A collection of unit tests for the backend


### Deploying on PythonAnywhere

1. Firstly, create a FastAPI ASGI app
   - pa website create --domain airecruitingagent.pythonanywhere.com \
  --command '/home/airecruitingagent/.virtualenvs/airecruitingagent-venv/bin/uvicorn --app-dir /home/airecruitingagent/airecruitingagent --uds ${DOMAIN_SOCKET} backend.api:app'
2. After each code update:
   - cd ~/airecruitingagent
   - git pull origin main
   - pa website reload --domain airecruitingagent.pythonanywhere.com


### Syncing with v0.dev (deprecated; section for historical reference only) 

The chrome extension was originally vibe-coded using v0.dev, but has since been heavily modified. The v0.dev branch is no longer kept current. However, I've kept instructions here on how to keep the two repos in sync for legacy purposes.

- Sync changes from main/BrowserExtension/ → v0-dev branch
  1. git checkout main 
  2. git pull
  3. git add BrowserExtension 
  4. git commit -m "Update BrowserExtension"
  5. git subtree push --prefix=BrowserExtension origin v0-dev
- Sync changes from v0-dev branch → main/BrowserExtension/
  1. git checkout main
  2. git pull
  3. git subtree pull --prefix=BrowserExtension origin v0-dev --squash -m “v0.dev pull”
  4. git push


