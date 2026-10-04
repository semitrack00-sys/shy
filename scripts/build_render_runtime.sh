#!/usr/bin/env bash
set -eu

rm -rf runtime
mkdir -p runtime/core runtime/model_router runtime/permissions runtime/tools runtime/agent_runtime runtime/research

cp services/core/main.py runtime/main.py
cp services/core/memory.py runtime/memory.py
cp services/core/task_persistence.py runtime/task_persistence.py
cp services/core/intelligence_types.py runtime/core/intelligence_types.py

cp -R services/model-router/app/. runtime/model_router/
cp -R services/permissions/. runtime/permissions/
cp -R services/tools/. runtime/tools/
cp -R services/agent-runtime/. runtime/agent_runtime/
cp -R services/research/. runtime/research/

touch runtime/core/__init__.py
touch runtime/model_router/__init__.py
touch runtime/permissions/__init__.py
touch runtime/tools/__init__.py
touch runtime/agent_runtime/__init__.py
touch runtime/research/__init__.py
