FROM python:3.13-slim

WORKDIR /app

COPY services/core/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/core/main.py .
COPY services/core/memory.py .
COPY services/core/intelligence_types.py ./core/intelligence_types.py
COPY services/model-router/app/ ./model_router/

COPY services/permissions/policy.py ./permissions/policy.py
COPY services/permissions/approvals.py ./permissions/approvals.py
COPY services/tools/gateway.py ./tools/gateway.py

COPY services/agent-runtime/planner.py ./agent_runtime/planner.py
COPY services/agent-runtime/runtime.py ./agent_runtime/runtime.py
COPY services/agent-runtime/intelligence_router.py ./agent_runtime/intelligence_router.py
COPY services/agent-runtime/verifier.py ./agent_runtime/verifier.py
COPY services/agent-runtime/loop_state.py ./agent_runtime/loop_state.py

COPY services/research/web_search.py ./research/web_search.py
COPY services/research/tavily.py ./research/tavily.py
COPY services/research/query_planner.py ./research/query_planner.py
COPY services/research/evidence_compare.py ./research/evidence_compare.py
COPY services/research/research_engine.py ./research/research_engine.py
COPY services/research/citation_validator.py ./research/citation_validator.py

RUN touch ./model_router/__init__.py
RUN touch ./permissions/__init__.py
RUN touch ./tools/__init__.py
RUN touch ./agent_runtime/__init__.py
RUN touch ./research/__init__.py

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
