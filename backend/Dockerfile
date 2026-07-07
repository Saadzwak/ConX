FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances système :
#   - build-essential / curl : base
#   - libgl1 / libgomp1 : runtime IfcOpenShell C++ (test J9 OK avec ces deux libs)
#   - libpango-1.0-0 + libpangoft2-1.0-0 + libcairo2 + libffi-dev + shared-mime-info :
#     runtime WeasyPrint (rendu PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libgomp1 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libcairo2 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000

# CMD PROD (pas de --reload : watchers inotify + redémarrages intempestifs +
# mono-worker en prod). Le hot-reload dev est fourni par docker-compose.yml
# (bind mount ./backend:/app + `command: ... --reload`). Cf. AUDIT M13.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
