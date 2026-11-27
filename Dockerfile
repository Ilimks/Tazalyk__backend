FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --upgrade pip

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN useradd --system --uid 1001 --no-create-home django \
    && mkdir -p media \
    && chown -R django:django media
USER django

EXPOSE 8000

CMD ["gunicorn", "tazalyk.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "4", "--timeout", "300", "--access-logfile", "-"]
