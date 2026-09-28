import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]
module_path = root / "services" / "research" / "web_search.py"

spec = importlib.util.spec_from_file_location(
    "shy_web_search",
    module_path,
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

SearchResult = module.SearchResult
WebSearchProvider = module.WebSearchProvider
WebSearchService = module.WebSearchService


class FakeProvider(WebSearchProvider):
    name = "test-provider"

    def search(self, query, max_results=5):
        return [
            SearchResult(
                title="  SHY   Test Source  ",
                url=" https://example.com/source ",
                snippet="Structured\nresearch\tevidence.",
                source=" example.com ",
            ),
            SearchResult(
                title="Unsafe URL",
                url="javascript:alert(1)",
                snippet="This result must be removed.",
                source="invalid",
            ),
        ]


service = WebSearchService(FakeProvider())

result = service.search(
    "SHY research test",
    max_results=5,
)

assert result["provider"] == "test-provider"
assert result["query"] == "SHY research test"
assert result["result_count"] == 1
assert len(result["results"]) == 1
assert result["results"][0]["title"] == "SHY Test Source"
assert result["results"][0]["url"] == "https://example.com/source"
assert result["results"][0]["source"] == "example.com"
assert result["results"][0]["snippet"] == "Structured research evidence."

try:
    service.search("")
    raise AssertionError("Empty query was not rejected.")
except ValueError:
    pass

try:
    service.search("test", max_results=11)
    raise AssertionError("Oversized result request was not rejected.")
except ValueError:
    pass

print("structured results: PASS")
print("field normalization: PASS")
print("unsafe URL filtering: PASS")
print("empty query rejection: PASS")
print("result limit enforcement: PASS")
print("SHY Web Research foundation tests: PASS")
