FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py .

ENV PORT=8000
ENV UVICORN_HOST=0.0.0.0
ENV MCP_HOST=0.0.0.0
EXPOSE 8000

CMD ["python", "-c", "from server import mcp; import uvicorn; uvicorn.run(mcp.sse_app(), host='0.0.0.0', port=8000)"]
