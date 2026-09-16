"""
FastAPI wrapper around Stage 1 detection. Owner: Harshita (deployment,
harshita-deployment.md Part 3).

    GET  /api/health          -> {"ok": true, "commit": "<sha>"}
    POST /api/detect          -> {case_id} runs Stage 1 on a bundled case
    POST /api/detect/upload   -> multipart GeoTIFF, runs Stage 1 on it directly

Shells out to pipeline/detect/run.py rather than importing its internals, so this
can never quietly diverge from what a human running the documented command gets.
The acceptance gate (Part 4) is that /api/detect's output is byte-identical to the
committed cases/<id>/detections.geojson for all nine gallery cases.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from collections import defaultdict, deque

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

REPO = Path(__file__).resolve().parents[1]
CASES = REPO / "cases"
RUN_PY = REPO / "pipeline" / "detect" / "run.py"

GIT_SHA = os.environ.get("GIT_SHA", "unknown")

# P4: a 60s in-memory cache keyed by case id, so a judge mashing "re-run" doesn't
# queue nine jobs. Keyed only on the bundled-case path — an upload is never cached,
# it's a fresh scene every time.
CACHE_TTL_S = 60
_cache: dict[str, tuple[float, dict]] = {}

# P5 gates for the upload endpoint. Enforced here in the app because there is no
# reverse proxy in front of this container (see docs/updates/harshita.md — plain
# HTTP, CloudFront skipped over an AWS account-verification hold); the brief's
# "rejected at the reverse proxy, not in Python" note assumed one would exist.
MAX_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_RASTER_DIM_PX = 8000
TIFF_MAGIC_PREFIXES = (b"II*\x00", b"MM\x00*")  # little/big-endian TIFF byte order marks

# 5 requests/minute/IP (Part 5, gate 4) — "generous" per the brief, this only exists to
# stop a deliberately hostile client from queueing unbounded compute on Harshita's credits,
# not to throttle a single judge clicking the button.
RATE_LIMIT_PER_MIN = 5
RATE_LIMIT_WINDOW_S = 60
_upload_hits: dict[str, deque[float]] = defaultdict(deque)


def _check_rate_limit(client_ip: str) -> None:
    now = time.time()
    hits = _upload_hits[client_ip]
    while hits and now - hits[0] > RATE_LIMIT_WINDOW_S:
        hits.popleft()
    if len(hits) >= RATE_LIMIT_PER_MIN:
        raise HTTPException(429, "rate limit exceeded — 5 uploads per minute per IP")
    hits.append(now)

app = FastAPI(title="UDGAM detect API")

# No cookies/auth on this API, and the frontend's own origin varies (S3 website
# hosting, no fixed CloudFront domain), so a wildcard origin costs nothing here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True, "commit": GIT_SHA}


def _rule_flags_for(case_id: str) -> list[str]:
    """The classical path refuses to guess a rule threshold (D34) — reproduce the
    exact invocation documented in docs/updates/soumirya.md per provenance: satellite
    cases require --rule-contrast/--rule-elongation, benchmark cases must run with
    neither, matching the command that actually produced the committed bundle."""
    meta_path = CASES / case_id / "meta.json"
    provenance = "satellite"
    if meta_path.exists():
        provenance = (json.loads(meta_path.read_text()).get("provenance")) or "satellite"
    if provenance == "benchmark":
        return []
    return ["--rule-contrast", "-3.0", "--rule-elongation", "2.5"]


def _run_detect(case_dir: Path, extra_flags: list[str]) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "detections.geojson"
        cmd = [sys.executable, str(RUN_PY),
               "--case", case_dir.name, "--cases-root", str(case_dir.parent),
               "--out", str(out_path), *extra_flags]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError((proc.stderr or proc.stdout)[-4000:])
        return json.loads(out_path.read_text())


@app.post("/api/detect")
def detect(case_id: str = Form(...)):
    case_dir = CASES / case_id
    if not case_dir.is_dir():
        raise HTTPException(404, f"unknown case_id {case_id!r}")

    cached = _cache.get(case_id)
    if cached and time.time() - cached[0] < CACHE_TTL_S:
        return cached[1]

    try:
        result = _run_detect(case_dir, _rule_flags_for(case_id))
    except Exception as e:
        raise HTTPException(500, str(e)) from e

    _cache[case_id] = (time.time(), result)
    return result


@app.post("/api/detect/upload")
async def detect_upload(
    request: Request, file: UploadFile = File(...), provenance: str = Form("satellite")
):
    _check_rate_limit(request.client.host if request.client else "unknown")

    if provenance not in ("satellite", "benchmark"):
        raise HTTPException(400, "provenance must be 'satellite' or 'benchmark'")

    head = await file.read(4)
    if head[:4] not in TIFF_MAGIC_PREFIXES:
        raise HTTPException(400, "not a TIFF file (magic-byte check failed)")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        tif_path = tmp_dir / "sar_vv_vh.tif"
        size = len(head)
        with open(tif_path, "wb") as fh:
            fh.write(head)
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(413, "file exceeds the 200 MB limit")
                fh.write(chunk)

        import rasterio  # local import: keeps this endpoint's dependency visible here only

        try:
            with rasterio.open(tif_path) as src:
                if max(src.width, src.height) > MAX_RASTER_DIM_PX:
                    raise HTTPException(
                        400, f"raster too large ({src.width}x{src.height} px, "
                             f"max {MAX_RASTER_DIM_PX} px on a side)")
                bounds = {"west": src.bounds.left, "south": src.bounds.bottom,
                          "east": src.bounds.right, "north": src.bounds.top}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"not a readable GeoTIFF: {e}") from e

        (tmp_dir / "bounds.json").write_text(json.dumps(bounds))
        (tmp_dir / "meta.json").write_text(json.dumps({"provenance": provenance}))

        extra_flags = [] if provenance == "benchmark" else ["--rule-contrast", "-3.0",
                                                              "--rule-elongation", "2.5"]
        try:
            detections = _run_detect(tmp_dir, extra_flags)
        except Exception as e:
            raise HTTPException(500, str(e)) from e

    return {"detections": detections, "bounds": bounds}
