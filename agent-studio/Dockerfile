FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

RUN apt-get update \
  && apt-get upgrade -y --no-install-recommends \
  && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-eng \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY agent_studio ./agent_studio
COPY knowledge ./knowledge
COPY migrations ./migrations

EXPOSE 8010

CMD ["uv", "run", "--no-sync", "uvicorn", "agent_studio.main:app", "--host", "0.0.0.0", "--port", "8010"]
