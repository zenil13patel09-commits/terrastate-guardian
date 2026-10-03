# TerraState Guardian

Self-hosted Terraform state monitoring and drift detection for multi-environment infrastructure

TerraState Guardian is a self-hosted web application that monitors and validates Terraform state files across multiple environments and projects. Cloud engineers use it to detect state drift, track infrastructure changes over time, and receive alerts when state files show unexpected modifications or inconsistencies. The tool parses uploaded or locally stored Terraform state JSON files, compares them against baseline snapshots, and provides a visual dashboard showing resource counts, change history, and drift detection across development, staging, and production environments.

## Features

- Upload and parse Terraform state files in JSON format
- Automatic baseline snapshot creation for each environment and project
- State drift detection comparing current state against baseline snapshots
- Visual dashboard displaying resource counts by type across all environments
- Change history timeline showing state modifications over time
- Multi-environment support with separate tracking for dev, staging, and production
- Resource inventory view listing all managed infrastructure resources
- Alert system flagging unexpected resource additions or deletions
- State file comparison tool showing detailed diffs between versions
- Project grouping to organize state files by application or team
- Export functionality for drift reports and change summaries
- Session-based authentication to protect infrastructure visibility

## Tech stack

Python, FastAPI, SQLite, Flask, Terraform, HTML, CSS

## How to run locally
### Prerequisites

- Node.js 18 or newer
- Python 3.10 or newer
### Environment variables


Copy `.env.example` to `.env` in the project root before starting the app.

**Windows**

```bash
copy .env.example .env
```

**macOS / Linux**

```bash
cp .env.example .env
```

Fill in any empty values:

- `DATABASE_URL` — example: `sqlite:///./app.db`
- `SECRET_KEY` — example: `change-me`
- `DEBUG` — example: `true`
Start the **backend** and the **frontend** in **two separate terminals**. Start the backend first. Do **not** run `npm run build` just to try the app — that is a production build step.

### 1. Backend (terminal 1)

```bash
cd .
python -m venv .venv
```

**Windows (PowerShell or Command Prompt)**

```bash
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
flask --app main run --debug --host 127.0.0.1 --port 8000
```

**macOS / Linux**

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app main run --debug --host 127.0.0.1 --port 8000
```

Backend API: http://127.0.0.1:8000  
API docs: http://127.0.0.1:8000/docs

Leave this terminal running.

### 2. Frontend (terminal 2)

```bash
cd .
npm install
npm run dev
```

Frontend app: http://localhost:5173

Open the frontend URL in your browser. Keep **both** terminals running while you use the app.

### Optional production build

Only after the app already runs with `npm run dev`:

```bash
cd .
npm run build
```

## Project structure

```
.
├── src/
│   ├── App.jsx
│   ├── index.css
│   └── main.jsx
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── login.html
│   └── upload.html
├── tests/
│   └── test_api.py
├── .env.example
├── .gitignore
├── app.py
├── auth.py
├── database.py
├── drift_detector.py
├── index.html
├── main.py
├── models.py
├── package-lock.json
├── package.json
├── requirements.txt
├── routers.py
├── schemas.py
├── seed.py
├── state_parser.py
└── vite.config.js
```

---

Generated with [Alviora AI](https://alvioraai.com).
