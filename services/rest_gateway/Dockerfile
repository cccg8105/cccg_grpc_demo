FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generated/ generated/
COPY proto/ proto/
COPY services/ services/

ENV PYTHONPATH=/app

CMD ["python", "-m", "services.rest_gateway.main"]
