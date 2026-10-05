FROM python:3.13-slim

WORKDIR /app

COPY services/core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/core/ ./
COPY services/core/intelligence_types.py ./core/intelligence_types.py
COPY services/model-router/app/ ./model_router/
COPY services/permissions/ ./permissions/
COPY services/tools/ ./tools/
COPY services/agent-runtime/ ./agent_runtime/
COPY services/research/ ./research/

RUN touch ./model_router/__init__.py
RUN touch ./permissions/__init__.py
RUN touch ./tools/__init__.py
RUN touch ./agent_runtime/__init__.py
RUN touch ./research/__init__.py

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
