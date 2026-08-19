FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies first (better layer caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Reference implementation source and canonical schemas.
COPY axis_core ./axis_core
COPY schemas ./schemas
COPY attestation-example.json attestation-example-deny.json ./

EXPOSE 8000

CMD ["uvicorn", "axis_core.main:app", "--host", "0.0.0.0", "--port", "8000"]
