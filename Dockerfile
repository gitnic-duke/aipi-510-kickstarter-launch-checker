# Kickstarter Launch Checker: one image for both training and serving (task T8).
#   docker build -t kickstarter-api .
#   docker run --rm -p 8080:8080 kickstarter-api           # serve (default)
#   docker run --rm kickstarter-api train                  # train (from T11 on)
# The production model is added by Cloud Build (see cloudbuild.yaml and docs/deploy.md);
# a plain local build uses the placeholder model.
FROM python:3.11-slim

# Unbuffered output so logs reach Cloud Run immediately; no .pyc clutter.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# XGBoost needs the OpenMP runtime, which the slim image doesn't include.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so code changes don't invalidate this (slow) cached layer.
COPY requirements.txt .
# XGBoost pulls in NVIDIA's NCCL (~250 MB) for multi-GPU training. We only use
# CPUs and XGBoost loads NCCL only when needed, so drop it to shrink the image.
# (pip just warns and continues if it isn't installed on this platform.)
RUN pip install -r requirements.txt \
    && pip uninstall -y nvidia-nccl-cu12

COPY src/ src/
COPY scripts/ scripts/
COPY config.yaml docker-entrypoint.sh ./

# Model baked into the image at build time (task T15).
# Cloud Build first downloads the production model from GCS into
# model-artifact/ (see cloudbuild.yaml). Builds without it (CI, plain local
# builds) fall back to the placeholder. The [t] glob makes the folder optional:
# COPY still succeeds when model-artifact/ doesn't exist.
ARG MODEL_VERSION=placeholder-v0
COPY docker-entrypoint.sh model-artifac[t] /tmp/model-in/
RUN mkdir -p models \
    && if [ -f /tmp/model-in/model.joblib ]; then \
         if [ "$MODEL_VERSION" = "placeholder-v0" ]; then \
           echo "model-artifact/model.joblib found: pass --build-arg MODEL_VERSION=<version>" >&2; \
           exit 1; \
         fi; \
         mv /tmp/model-in/model.joblib models/model.joblib; \
       elif [ "$MODEL_VERSION" = "placeholder-v0" ]; then \
         python -m scripts.make_dummy_model --out models/model.joblib; \
       else \
         echo "MODEL_VERSION=$MODEL_VERSION but no model-artifact/model.joblib to bake in" >&2; \
         exit 1; \
       fi \
    && rm -rf /tmp/model-in
ENV MODEL_PATH=/app/models/model.joblib \
    MODEL_VERSION=${MODEL_VERSION}

# Run as a non-root user (least privilege).
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

# Cloud Run sends traffic to $PORT (8080 by default).
EXPOSE 8080
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["serve"]
