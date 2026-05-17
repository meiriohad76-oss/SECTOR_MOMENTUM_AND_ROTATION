# Pushing this project to GitHub

Three ways, easiest first.

---

## Option A — GitHub Desktop (no command line)

1. **Install GitHub Desktop** from https://desktop.github.com/.
2. **Sign in** with your GitHub account (create one at github.com if you don't have it — free).
3. In GitHub Desktop, click **File → Add Local Repository...**
4. Browse to your project folder (e.g. `D:\smart money dashboard 17052026\`) and click "Add Repository."
5. If prompted, click **"create a repository"** — GitHub Desktop will initialize git for you.
6. Set the repo name to something like `sector-rotation-dashboard` (lowercase, hyphens, no spaces).
7. Leave the default ".gitignore" choice — we already shipped one.
8. Click **"Create Repository."**
9. Click the **"Publish repository"** button at the top.
10. Untick "Keep this code private" if you want it public; tick it to keep private. Click **Publish.**

Done. Your repo is live at `https://github.com/<your-username>/sector-rotation-dashboard`.

To push future changes: GitHub Desktop shows changed files at left → write a summary → **Commit to main** → **Push origin**.

---

## Option B — Command line (git CLI)

Install Git first: https://git-scm.com/downloads (use defaults during install).

Then:

```powershell
cd "D:\smart money dashboard 17052026"

# Initialize git in this folder
git init
git branch -M main

# Configure your identity (one time per machine)
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"

# Stage everything (the .gitignore will exclude .venv/ and __pycache__/)
git add .
git commit -m "Initial commit: sector rotation dashboard with 7-pillar methodology"
```

Now create the empty repo on GitHub:
1. Go to https://github.com/new.
2. Repository name: `sector-rotation-dashboard`.
3. **Do NOT initialize with README, .gitignore, or LICENSE** — you already have them locally.
4. Click "Create repository."

GitHub will show you commands. Use these (replace `<your-username>`):

```powershell
git remote add origin https://github.com/<your-username>/sector-rotation-dashboard.git
git push -u origin main
```

GitHub will ask you to sign in. Use a **Personal Access Token (PAT)** as the password:
- Go to https://github.com/settings/tokens/new
- Note: "git CLI"
- Expiration: 90 days (or your preference)
- Scope: tick "repo" (full control of private repos)
- Generate → copy the token → paste it as the password when git asks

To push future changes:
```powershell
git add .
git commit -m "what you changed"
git push
```

---

## Option C — Drag-and-drop via the GitHub website

Easiest if the project is small enough.

1. Go to https://github.com/new, create `sector-rotation-dashboard`, tick "Add a README" (so the repo is initialized).
2. Open the repo page, click **"Add file" → "Upload files."**
3. Drag the entire contents of `D:\smart money dashboard 17052026\` into the drop zone — **except** the `.venv` folder (skip it manually).
4. Write a commit message, click **"Commit changes."**

Limitation: GitHub web upload caps at 100 files per drag. If you hit the limit, upload `src/`, `docs/`, etc. as separate batches.

---

## What gets uploaded vs what stays local

The `.gitignore` we shipped excludes:
- `.venv/` — your Python environment (huge, machine-specific, recreate elsewhere with `pip install -r requirements.txt`)
- `__pycache__/`, `*.pyc` — Python bytecode caches
- `state.json` — the local state-machine snapshot (regenerates on first run)
- `*.log`, `.streamlit/secrets.toml` — local-only

Everything in `src/`, `docs/`, the launchers, README, and LICENSE will be committed.

---

## After your first push

- **Add a description** in the GitHub repo settings ("Sector rotation dashboard with 7-pillar methodology — Streamlit + yfinance").
- **Add topics**: `streamlit`, `finance`, `quant`, `sector-rotation`, `momentum`, `rrg`, `yfinance`.
- (Optional) **Add a screenshot** of the dashboard to the top of README — `![Dashboard](docs/screenshot.png)`.

That's it. Welcome to GitHub.
