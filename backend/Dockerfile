FROM python:3.12-slim

WORKDIR /app

# System deps (pandas/numpy wheels are prebuilt, but keep build tools just in case)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces expects the app on port 7860
ENV PORT=7860
EXPOSE 7860

CMD ["gunicorn", "app:app", "--timeout", "120", "--workers", "1", "--bind", "0.0.0.0:7860"]
