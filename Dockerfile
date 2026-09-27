FROM python:3.13-slim

WORKDIR /app

COPY services/core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/core/main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
