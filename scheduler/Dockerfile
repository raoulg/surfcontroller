# Build stage
FROM python:3.11-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# Copy source code (respecting .dockerignore)
COPY . .

# Build the package
RUN uv build --wheel

# Final stage
FROM python:3.12-slim

# Install system dependencies (cron)
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the built wheel from the builder stage
COPY --from=builder /app/dist /app/dist

# Install the package from the wheel
RUN pip install /app/dist/*.whl flask

# Copy scheduler files
COPY scheduler/app.py /app/
COPY scheduler/pause_job.py /app/
COPY scheduler/templates /app/templates
COPY scheduler/crontab /etc/cron.d/pause-job

# Give execution rights on the cron job
RUN chmod 0644 /etc/cron.d/pause-job

# Apply cron job
RUN crontab /etc/cron.d/pause-job

# Create log file
RUN touch /var/log/cron.log

# Environment variables for config
ENV SURF_CONTROLLER_CONFIG_DIR=/config

# Run command: Start cron and Flask app
RUN echo '#!/bin/bash\ncron && python app.py' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
