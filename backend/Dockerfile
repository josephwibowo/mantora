# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Copy frontend files
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN npm install -g pnpm && pnpm install

COPY frontend/ ./
RUN pnpm build

# Stage 2: Backend with built frontend
FROM python:3.13-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY backend/pyproject.toml backend/uv.lock ./

# Install dependencies
RUN uv sync --frozen

# Copy source code
COPY backend/src ./src
COPY backend/tests ./tests
COPY backend/scripts ./scripts

# Set PYTHONPATH to include src
ENV PYTHONPATH=/app/src

# Copy built frontend from stage 1
COPY --from=frontend-builder /frontend/dist ../frontend/dist

# Make scripts executable
RUN chmod +x scripts/*.py

# Expose backend port
EXPOSE 8000

# Run backend with uvicorn
CMD ["uv", "run", "uvicorn", "mantora.app:app", "--host", "0.0.0.0", "--port", "8000"]

