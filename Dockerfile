# syntax=docker/dockerfile:1
FROM node:20-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VENV_PATH=/opt/venv \
    PORT=7860

# Python + venv (avoid PEP 668 system install issues)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-venv ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m venv $VENV_PATH
ENV PATH="$VENV_PATH/bin:$PATH"

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node deps
WORKDIR /app/project
COPY project/package*.json ./
RUN npm install

# App source
COPY project .

EXPOSE 7860

CMD ["npm", "start"]