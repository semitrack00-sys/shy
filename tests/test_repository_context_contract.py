import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]
path = root / "services" / "agent-runtime" / "repository_context.py"


def load_module(name, file_path):
    spec = importlib.util.spec_from_file_location(name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = load_module("shy_repository_context", path)

ctx = module.build_repository_context(
    repository_identifier="C:/SHY",
    branch="codex/shy-v0.11-intelligence",
    commit="f3792a40348f87f1c866122911a5aa5a1f26f419",
    relevant_files=["services/core/main.py", "services/core/memory.py"],
    diagnostics=["tests/test_memory_relevance.py: PASS"],
    test_results=["35/35 evals pass"],
    diff_summary="".join(["x" for _ in range(5000)]),
)

assert ctx.repository_identifier == "C:/SHY"
assert ctx.branch == "codex/shy-v0.11-intelligence"
assert ctx.commit == "f3792a40348f87f1c866122911a5aa5a1f26f419"
assert len(ctx.relevant_files) == 2
assert len(ctx.diff_summary) <= 4000
print("repository context contract: PASS")

print("SHY Phase 6B repository context tests: PASS")
