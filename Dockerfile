FROM python@sha256:7ce4b6dfe35e55397b7cda544f8a13f191b7ae28dc5aad71fe664dbc9bc2623f AS base
RUN useradd -m -u 1001 botuser
WORKDIR /app
COPY --chown=botuser:botuser pyproject.toml .
COPY --chown=botuser:botuser src/ src/
RUN pip install --no-cache-dir . && pip install --no-cache-dir --upgrade pip
USER 1001:1001
ARG PORT
CMD ["python", "-m", "src.bot"]
