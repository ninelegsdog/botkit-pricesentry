FROM python:3.13-slim AS base
RUN useradd -m -u 1001 botuser
WORKDIR /app
COPY --chown=botuser:botuser pyproject.toml .
COPY --chown=botuser:botuser src/ src/
RUN pip install --no-cache-dir . && pip install --no-cache-dir --upgrade pip
USER 1001:1001
ARG PORT
CMD ["python", "-m", "src.bot"]
