<p align="center">
  <img src="assets/readme-header.png" alt="Scrapper Tool — Multi-board job search API (FastAPI, Playwright)" width="100%" />
</p>

**Multi-board job search API** — a small [FastAPI](https://fastapi.tiangolo.com/) service that exposes HTTP endpoints to fetch job listings from several job boards. One shared headless Chromium instance ([Playwright](https://playwright.dev/python/) + stealth) starts with the app and is reused by all scrapers.

[![Python](https://img.shields.io/badge/python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Playwright](https://img.shields.io/badge/Playwright-1.59-2EAD33?style=flat&logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED?style=flat&logo=docker&logoColor=white)](docker-compose.yml)

| | |
|---|---|
| **Stack** | FastAPI · Uvicorn · Playwright (stealth) · optional Docker Compose |
| **Endpoints** | `/naukri` · `/linkedin` · `/cutshort` · `/hirist` · `/wellfound` · `GET /health` |

## Supported job boards

Scrapers are implemented for these job sites (each maps to an API route prefix):

| Job board | Route prefix |
| --- | --- |
| [Naukri](https://www.naukri.com/) | `/naukri` |
| [LinkedIn](https://www.linkedin.com/) | `/linkedin` |
| [Hirist](https://www.hirist.tech/) | `/hirist` |
| [Cutshort](https://cutshort.io/) | `/cutshort` |
| [Wellfound](https://wellfound.com/) | `/wellfound` |

---

## Disclaimer

This project is for **education and personal automation**. Third-party job sites have their own **terms of use**, rate limits, and technical protections. You are responsible for using this software **lawfully** and in line with each site's rules. The authors are not liable for misuse.

---

## Contents

- [Supported job boards](#supported-job-boards)
- [Architecture](#architecture)
- [Deployment (optional)](#deployment-optional)
- [Local run](#local-run)
- [Top contributors](#top-contributors)

---

## Architecture

```mermaid
flowchart TB
  subgraph clients["Clients"]
    HTTP[HTTP clients / curl]
  end

  subgraph runtime["Process: Uvicorn + FastAPI"]
    API["main.py — FastAPI app"]
    LIFESPAN["Lifespan: browser startup / shutdown"]
    HEALTH["GET /health"]
  end

  subgraph browser_layer["Browser layer"]
    BROWSER["browser.py"]
    PW["Playwright Stealth + Chromium"]
  end

  subgraph scrapers["Scraper routers (APIRouter)"]
    N["scraper_1 — /naukri"]
    L["scraper_2 — /linkedin"]
    C["scraper_3 — /cutshort"]
    H["scraper_4 — /hirist"]
    W["scraper_5 — /wellfound"]
  end

  subgraph external["External sites"]
    N_S["naukri.com"]
    L_S["linkedin.com"]
    C_S["cutshort.io"]
    H_S["hirist.com"]
    W_S["wellfound.com"]
  end

  HTTP --> API
  API --> LIFESPAN
  API --> HEALTH
  LIFESPAN --> BROWSER
  BROWSER --> PW
  API --> scrapers
  N & L & C & H & W --> BROWSER
  N --> N_S
  L --> L_S
  C --> C_S
  H --> H_S
  W --> W_S
```

**Request path:** an HTTP call hits `main.py`, which routes to the matching `APIRouter`. The router uses `get_browser()` to drive headless Chromium and returns parsed job data. `GET /health` reports whether the shared browser was initialized.

---

## Deployment (optional)

```mermaid
flowchart LR
  subgraph host["Host"]
    DC["docker compose"]
  end
  subgraph container["Container: scraper"]
    UV[Uvicorn :8000]
  end
  DC -->|build + run, port 8001:8000| container
  host -->|healthcheck GET /health| UV
```

`docker-compose.yml` maps host port **8001** to the app on **8000** inside the container and runs a healthcheck against `/health`. Playwright benefits from extra shared memory (`shm_size`).

---

## Local run

**1. Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

**2. Run the server**

```bash
# default port 8000
uvicorn main:app --reload

# custom port
PORT=9000 python main.py
```

**3. Hit an endpoint**

```bash
curl "http://localhost:8000/linkedin?query=python+developer&location=bangalore"
curl "http://localhost:8000/health"
```

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | Port Uvicorn listens on |

---

## Project structure

```
job-scraper/
├── main.py               # FastAPI app + lifespan
├── browser.py            # Shared Playwright browser instance
├── scrapers/
│   ├── scraper_1.py
│   ├── scraper_2.py
│   ├── scraper_3.py
│   ├── scraper_4.py
│   └── scraper_5.py
├── requirements.txt
└── docker-compose.yml
```

---

## Top contributors

Thanks to everyone who helps improve this project.

**Live data:** avatars and counts below are fetched from GitHub when you open this page ([contrib.rocks](https://contrib.rocks) + [Shields.io](https://shields.io/)). They update as new people contribute.

<p align="center">
  <a href="https://github.com/akxhat06/naukari-scrapper/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=akxhat06/naukari-scrapper" alt="Repository contributors (loaded from GitHub)" />
  </a>
</p>

<p align="center">
  <a href="https://github.com/akxhat06/naukari-scrapper/graphs/contributors" title="View all contributors on GitHub">
    <img src="https://img.shields.io/github/contributors/akxhat06/naukari-scrapper?style=flat-square&label=GitHub%20contributors" alt="Number of contributors on GitHub" />
  </a>
</p>

> **Be part of this project** — if you do not see contributors above yet (new repo, private fork, or image blocked), you can still help: **[open a pull request](https://github.com/akxhat06/naukari-scrapper/compare)** or **[start an issue](https://github.com/akxhat06/naukari-scrapper/issues)** with ideas, bugs, or docs. First-time contributors are welcome.

[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/akxhat06/naukari-scrapper/compare)