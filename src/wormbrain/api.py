"""Local-first, bounded, paper-only reference worker and same-origin UI."""
from __future__ import annotations
import os
import secrets
import threading
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict

from .core import SCENARIOS
from .replay import run_replay
from .live import monitor

app = FastAPI(title="WormBrain paper worker", docs_url=None, redoc_url=None, openapi_url=None)
if os.getenv("WORM_REMOTE_MODE") == "1" and not os.getenv("WORM_WORKER_TOKEN"):
    raise RuntimeError("Remote mode requires a private worker token")
origins = [x.strip() for x in os.getenv("WORM_ALLOWED_ORIGINS", "").split(",") if x.strip()]
if "*" in origins:
    raise RuntimeError("Wildcard browser access is not permitted")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["Authorization", "Content-Type"], allow_credentials=False)
executor = ThreadPoolExecutor(max_workers=1)
lock = threading.Lock()
jobs: dict = {}


def authorize(request: Request) -> None:
    configured = os.getenv("WORM_WORKER_TOKEN", "")
    provided = request.headers.get("authorization", "").removeprefix("Bearer ")
    if configured:
        if not secrets.compare_digest(provided, configured):
            raise HTTPException(401, "Worker authorization required")
    elif not request.client or request.client.host not in {"127.0.0.1", "::1", "testclient"}:
        raise HTTPException(403, "Remote workers require a server-side token")
    # CORS alone does not prevent cross-site writes to an unprotected local worker.
    origin = request.headers.get("origin")
    local = {"http://127.0.0.1:8000", "http://localhost:8000"}
    if origin and origin not in set(origins) | local:
        raise HTTPException(403, "Browser origin not allowed")


@app.get("/api/health")
def health():
    available = all(shutil.which(x) for x in ("java", "gcc", "g++", "make"))
    return dict(status="ok" if available else "degraded", runtime="c302-reference", backend="neuron", mode="paper", live_execution=False)


class JobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: str


def execute_job(identifier: str, name: str):
    try:
        report = run_replay(name)
        with lock:
            jobs[identifier] = dict(status="complete", report=report)
    except Exception:
        # Do not disclose exception messages, local paths, config, or dependency logs.
        with lock:
            jobs[identifier] = dict(status="failed", error="Reference simulation failed. Run the CLI model diagnostic locally.")


@app.post("/api/jobs", dependencies=[Depends(authorize)], status_code=202)
def create_job(body: JobRequest):
    if body.scenario not in SCENARIOS:
        raise HTTPException(422, "Choose a supported scenario")
    with lock:
        if monitor.active or any(x["status"] == "running" for x in jobs.values()):
            raise HTTPException(429, "One reference simulation is already running")
        while len(jobs) >= 8:
            jobs.pop(next(iter(jobs)))
        identifier = uuid4().hex
        jobs[identifier] = dict(status="running")
    executor.submit(execute_job, identifier, body.scenario)
    return dict(id=identifier, status="running")


@app.get("/api/jobs/{identifier}", dependencies=[Depends(authorize)])
def get_job(identifier: str):
    with lock:
        if identifier not in jobs:
            raise HTTPException(404, "Job not found or expired")
        return jobs[identifier]


@app.post("/api/live/start", dependencies=[Depends(authorize)], status_code=202)
def start_live():
    with lock:
        if monitor.active or any(x["status"] == "running" for x in jobs.values()):
            raise HTTPException(429, "The reference worker is already in use")
        monitor.start(seconds=3600)
    return dict(status="preparing-brain", session_seconds=3600)


@app.post("/api/live/stop", dependencies=[Depends(authorize)])
def stop_live():
    monitor.stop()
    return dict(status="stop-requested")


@app.get("/api/live", dependencies=[Depends(authorize)])
def live_status(history: bool = False):
    return monitor.snapshot(history=history)


web = Path(os.getenv("WORM_WEB_ROOT", str(Path(__file__).resolve().parents[2] / "web")))
if web.is_dir():
    app.mount("/", StaticFiles(directory=web, html=True), name="dashboard")
