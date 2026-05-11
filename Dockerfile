FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# Для разработки:
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# Для продакшена (раскомментировать позже):
# CMD ["gunicorn", "tazalyk.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]