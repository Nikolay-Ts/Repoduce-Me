# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12.10
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create a non-privileged user
ARG UID=10001
RUN adduser \
    --disabled-password \
    --gecos "" \
    --home "/home/appuser" \
    --shell "/bin/bash" \
    --uid "${UID}" \
    appuser

# Install dependencies for pyenv and Python builds
RUN apt-get update && apt-get install -y \
    git \
    gcc \
    g++ \
    make \
    libffi-dev \
    libssl-dev \
    python3-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    curl \
    wget \
    llvm \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    liblzma-dev \
    libgl1 libglib2.0-0 libxext6 libsm6 libxrender1 \
    && apt-get clean

# Ensure the appuser owns their home directory
RUN mkdir -p /home/appuser && chown -R appuser:appuser /home/appuser

# Set environment variables for pyenv
ENV PYENV_ROOT=/home/appuser/.pyenv
ENV PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"

# Switch to the non-privileged user
USER appuser

# Install pyenv for the non-privileged user
RUN git clone https://github.com/pyenv/pyenv.git $PYENV_ROOT && \
    git clone https://github.com/pyenv/pyenv-virtualenv.git $PYENV_ROOT/plugins/pyenv-virtualenv && \
    echo 'eval "$(pyenv init --path)"' >> /home/appuser/.bashrc && \
    echo 'eval "$(pyenv init -)"' >> /home/appuser/.bashrc && \
    echo 'eval "$(pyenv virtualenv-init -)"' >> /home/appuser/.bashrc

# Pre-install Python versions (optional, for faster runtime)
RUN pyenv install 2.7.18 && \
    pyenv install 3.5.10 && \
    pyenv install 3.6.15 && \
    pyenv install 3.8.20 && \
    pyenv install 3.9.22 && \
    pyenv install 3.10.17 && \
    pyenv install 3.11.12 && \
    pyenv install 3.12.10 && \
    pyenv install 3.13.2

# Switch back to root for privileged operations
USER root

# Install public dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=bind,source=requirements.txt,target=requirements.txt \
    python -m pip install -r requirements.txt

COPY ConstructorAdapter /tmp/ConstructorAdapter
RUN python -m pip install /tmp/ConstructorAdapter

# Ensure the non-privileged user has write permissions to the ImportedProjects directory
RUN mkdir -p /app/ImportedProjects && \
    chown -R appuser:appuser /app/ImportedProjects

# Switch to the non-privileged user to run the application.
USER appuser

# Python packages. jupyter-lab, etc.
ENV PATH="$PATH:/home/appuser/.local/bin"

# Run the application.
CMD ["python", "accra_lc_pipeline.py", "-i"]
