---
title: KESCO AT&C Analysis API
emoji: ⚡
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# KESCO AT&C Analysis API

Backend API for the KESCO AT&C loss analysis tool.
Flask + pandas, deployed as a Docker Space.

## Endpoints
- `GET /` — service info
- `GET /health` — health check
- `POST /analyze` — upload consumer + energy CSVs, returns analysis JSON
- `POST /download-report` — generate xlsx/pdf/csv report

The frontend (on Vercel) calls these endpoints. CORS is enabled.
