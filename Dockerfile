FROM python:3.13-slim

WORKDIR /app

COPY services/core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/core/main.py .
COPY services/core/memory.py .
COPY services/core/task_persistence.py .
COPY services/core/intelligence_types.py ./core/intelligence_types.py
COPY services/model-router/app/ ./model_router/
COPY services/permissions/ ./permissions/
COPY services/tools/ ./tools/
COPY services/agent-runtime/ ./agent_runtime/
COPY services/research/ ./research/

RUN touch ./core/__init__.py \
    ./model_router/__init__.py \
    ./permissions/__init__.py \
    ./tools/__init__.py \
    ./agent_runtime/__init__.py \
    ./research/__init__.py

EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
