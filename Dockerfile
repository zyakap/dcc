FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIPENV_VENV_IN_PROJECT=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    pkg-config \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pipenv

COPY . .

RUN set -e; \
    if [ -f "Pipfile" ]; then \
        pipenv install --skip-lock 2>/dev/null || true; \
    fi; \
    pipenv install django djangorestframework pillow psycopg2-binary mysqlclient 2>/dev/null || true

RUN mkdir -p /app/media /app/staticfiles /app/static_files /app/logs /app/uploads

EXPOSE 8002

CMD pipenv run python manage.py runserver 0.0.0.0:8002 --noreload
