FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir flask requests gunicorn

COPY mcp_server.py .

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "mcp_server:app"]
