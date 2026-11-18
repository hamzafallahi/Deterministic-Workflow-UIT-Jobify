# Use a Python image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install dependencies using lockfile
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-editable --extra full --no-default-groups

# Add project source code and install
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --extra full --no-default-groups

# Final stage
FROM python:3.12-slim-bookworm

# Install system dependencies required for LaTeX rendering (Tectonic/Fonts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    fontconfig \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Setup a non-root user
RUN groupadd --system --gid 999 rendercv \
 && useradd --system --gid 999 --uid 999 --create-home rendercv

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder --chown=rendercv:rendercv /app/.venv /app/.venv

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Use the non-root user to run our application
USER rendercv

# Set the entrypoint to the rendercv CLI[cite: 5]
ENTRYPOINT ["rendercv"]

# Default command shows help[cite: 5]
CMD ["--help"]