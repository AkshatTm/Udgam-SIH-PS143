# UDGAM detect API container. Owner: Harshita (deployment, harshita-deployment.md Part 3).
#
# Build locally where pipeline/detect/models/ and cases/ are actually populated — building
# from a bare clone silently ships a container with the small committed models but none of
# the gitignored ones, which is fine for the 9 gallery cases (see docs/updates/harshita.md:
# none of them exercise the classifier.pkl / unet.pt path) but would matter for anything else.
#
#   docker build -t udgam-api --build-arg GIT_SHA=$(git rev-parse --short HEAD) .
#   docker run --rm -p 8000:8000 udgam-api

FROM python:3.13-slim AS build
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-detect.txt ./
COPY api/requirements.txt ./api/requirements.txt

# CPU-only torch, installed on its own line. --extra-index-url must be scoped to just this
# one install, not applied to the whole requirements.txt — see requirements-detect.txt's own
# docstring: an --extra-index-url on the full file lets pip silently prefer a same-named
# package from the PyTorch index over PyPI, for every package in the file, not just torch.
RUN pip install --no-cache-dir --prefix=/install \
      --extra-index-url https://download.pytorch.org/whl/cpu \
      -r requirements-detect.txt
# rasterio ships GDAL inside its own manylinux wheel — no system GDAL package needed here.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r api/requirements.txt

FROM python:3.13-slim
WORKDIR /app
# Runtime-only shared libs the slim base doesn't ship, needed by wheels that only dlopen
# them (so the image builds and /api/health passes clean — only an actual pipeline run
# throws). rasterio/GDAL needs libexpat for XML parsing; opencv-python (non-headless, it's
# what requirements-detect.txt pins) needs the X11/GL/GLib stack for its Qt plugin even
# though nothing here ever opens a GUI window. Caught by hitting /api/detect for real.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libexpat1 libgl1 libglib2.0-0 libxcb1 && rm -rf /var/lib/apt/lists/*
COPY --from=build /install /usr/local
COPY pipeline/ ./pipeline/
COPY scripts/  ./scripts/
COPY cases/    ./cases/
COPY api/      ./api/

ARG GIT_SHA=unknown
ENV GIT_SHA=${GIT_SHA}
ENV PYTHONUNBUFFERED=1 OMP_NUM_THREADS=2
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
