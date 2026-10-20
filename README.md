# Concept Check

A learner explains a backend scenario, investigates uncertain reasoning with a tutor, practises, revises, and applies the principle to an unfamiliar case. Reports preserve the evidence and help used instead of assigning a mastery percentage.

The catalogue contains seven concepts across requests/security, persistence, and data modelling: **60 authored scenarios, 19 diagrams and 8 cloze exercises**. Storage/persistence remains the featured demo. Cases are AI-authored and await human review; automated judgments are provisional.

## Quick Start

Use Python 3.12 and a Node version compatible with Vite 8.

### Backend
```powershell
cd backend
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --port 8000 --workers 1
```

Copy the example only in a new checkout; keep an existing local `.env`. Configure backend `OPENAI_API_KEY` and optional `FISH_AUDIO_API_KEY`. Set your own persistent `SECRET_KEY` to retain anonymous-browser identity across backend restarts. Staff review stays disabled until you configure a private `REVIEWER_API_KEY`; enter it through the staff dialog, never frontend configuration.

The local SQLite database is created and safely upgraded at startup. Prepared case versions are seeded without replacing historical answers or human case reviews. Back up existing data before any upgrade. `DATABASE_URL` supports another database, but changing it does not transfer existing records.

### Frontend
```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Open the development address shown by Vite. It proxies backend requests to port 8000. The backend exposes API documentation at `/docs` and authored learning guides at `/v1/resources/{concept-slug}`.

## Verification

```powershell
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

```powershell
cd frontend
npm.cmd run test:ui
npm.cmd run lint
npm.cmd run build
```

Backend tests disable real providers and use temporary records. An optional `python scripts/check_ai.py --live` from `backend` makes up to four billable requests with fictional inputs, without reading learner records.

## Learning and evidence

- Separate chat replies, prepared practice, original-answer revision, and independent unfamiliar-case submission.
- Typed answers and reviewed voice transcripts follow the same submission path.
- Prepared diagram/cloze selections are checked separately from conceptual reasoning.
- Reports compare stable skills, show support received, retain conversations, and link earlier sessions.
- Human reviewers can review/correct criteria and review/reject immutable case versions.
- Missing providers and malformed assessments remain explicit and inconclusive. Saved answers can be reassessed without creating another attempt.

## Operating limits

Run one backend worker: the current resumable-turn coordinator is designed for one process. Production configuration requires a strong persistent signing secret; use HTTPS and an appropriate deployment configuration. Public hosting, real microphone testing, human case review, and actual learner/stranger validation remain separate tasks. This repository does not claim proven learning effectiveness.

Local `.env`, databases, uploads, dependencies, build output, and scratch audit records are excluded from version control.

## Documentation

API documentation is hosted locally at `/docs` when the backend is running. Seeded concept resources and guides can be queried via `/v1/resources/{concept-slug}`.
