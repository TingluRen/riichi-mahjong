# Riichi Mahjong

A software engineering project by **Tinglu Ren**.

A browser-based Japanese Mahjong game built with Python, FastAPI, and JavaScript. Play against three heuristic AI opponents, with automated scoring and persistent browser sessions.


## Play

- [Play online](https://tinglus-riichi-mahjong-game.onrender.com)
- [Download for Windows](https://github.com/TingluRen/riichi-mahjong/releases/latest/download/RiichiMahjong.exe)


### Web version

[Play Riichi Mahjong online](https://tinglus-riichi-mahjong-game.onrender.com)

Note: The demo uses free hosting. The first visit after inactivity may take about a minute to load.


### Windows version

Download and double-click `RiichiMahjong.exe`.
Python installation is not required.

Keep the launcher window open while playing.
Press Ctrl+C in that window to quit.
The Windows version runs locally and uses separate saves from the online demo.


## Features

- Three AI opponents that evaluate discards and support Chi, Pon, Kan, and Riichi.
- Hand validation, yaku evaluation, Han/Fu scoring, and match settlement.
- Riichi, Furiten, Dora/Ura Dora, red fives, and Kan handling.
- Animated turns, optional automatic wins, and automatic discards after Riichi.
- Independent browser games stored in SQLite, with a 30-day inactivity expiry.
- Separate public and local-development entry points.

## Run locally

Use Python 3.12 (the version used for verification). From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn web_server:app --host 127.0.0.1 --port 8000
```

On macOS/Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`.
Open http://127.0.0.1:8000. No API keys or external AI services are required.
If port 8000 is occupied, stop the previous server or select another port.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -v
```

The suite covers game rules, scoring, AI calls, persistence, browser isolation, and turn playback. Dependencies in these files are the versions used during the publication review; transitive dependencies are not fully locked.

## Structure

| Component | Responsibility |
| --- | --- |
| `web_server.py` | Public FastAPI entry point; browser sessions and request checks |
| `server.py` | Game API, public player views, and local development routes |
| `main.py` | Game state and turn orchestration |
| `ai.py`, `ai_calls.py` | Heuristic discard and call decisions |
| `hand_evaluator.py`, `yaku.py`, `scoring.py` | Hand evaluation and scoring |
| `visitor_store.py`, `game_store.py` | SQLite visitor sessions and save validation |
| `static/index.html` | Browser UI, styling, and animations |
| `test_*.py` | Automated regression tests |

## Hosting

Deploy a Python web service using `web_server:app`, with the repository root as the working directory. Install `requirements.txt`, then start:

```sh
uvicorn web_server:app --host 0.0.0.0 --port "$PORT"
```

The hosting provider must supply `PORT`; use a numeric port for a local shell. Configure `/health` as the health check. Use HTTPS. The public entry point excludes debug API routes; do not deploy `server:app` publicly.

Set `MAHJONG_VISITOR_DB` to a writable path on a persistent disk. Default: `data/visitors.sqlite3`. Use one instance and one worker for this demo. Ephemeral storage can lose games after restart/redeployment; multiple replicas require a shared persistence design. See `ONLINE_SETUP.txt` for session behavior and manual verification.

## Scope and limitations

- Single human versus three heuristic opponents; no online human multiplayer or machine-learning model.
- Desktop-first interface; small screens need further usability work.
- Browser-cookie sessions, without account login or cross-device synchronization. Clearing cookies loses access to that session.
- SQLite transactions serialize game requests; this demo has not been load-tested for large concurrent traffic.
- Automated tests do not establish complete compatibility with every Riichi ruleset.