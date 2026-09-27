FROM python:3.13-slim

WORKDIR /app

COPY services/core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/core/main.py .
COPY services/core/memory.py .
COPY services/model-router/app/router.py ./model_router/router.py

COPY services/permissions/policy.py ./permissions/policy.py
COPY services/permissions/approvals.py ./permissions/approvals.py
COPY services/tools/gateway.py ./tools/gateway.py

RUN touch ./model_router/__init__.py
RUN touch ./permissions/__init__.py
RUN touch ./tools/__init__.py

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
