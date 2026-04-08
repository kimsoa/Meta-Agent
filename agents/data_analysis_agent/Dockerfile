FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8100
ENV OLLAMA_URL=http://host.docker.internal:11434
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8100"]
