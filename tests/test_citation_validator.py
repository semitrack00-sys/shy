import importlib.util
from pathlib import Path


root = Path(__file__).resolve().parents[1]
module_path = root / "services" / "research" / "citation_validator.py"


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


module = load_module("shy_citation_validator", module_path)

validate_citation_references = module.validate_citation_references

sources = [
    {
        "number": 1,
        "url": "https://example.com/one",
    },
    {
        "number": 2,
        "url": "https://example.com/two",
    },
]

valid = validate_citation_references(
    "Result with [1] and [2].",
    sources,
)
assert valid.is_valid is True
assert valid.valid_references == (1, 2)
assert valid.issues == ()
print("valid citations: PASS")

invalid = validate_citation_references(
    "Result with [9].",
    sources,
)
assert invalid.is_valid is False
assert any(item.defect == "CITATION_INVALID" for item in invalid.issues)
print("nonexistent citation detection: PASS")

malformed = validate_citation_references(
    "Result with [abc].",
    sources,
)
assert malformed.is_valid is False
assert any(item.defect == "CITATION_INVALID" for item in malformed.issues)
print("malformed citation detection: PASS")

mismatch = validate_citation_references(
    "Result with [1].",
    [
        {
            "number": 1,
            "url": "javascript:alert(1)",
        }
    ],
)
assert mismatch.is_valid is False
assert any(item.defect == "CITATION_MISMATCH" for item in mismatch.issues)
print("citation/source mismatch detection: PASS")

duplicate = validate_citation_references(
    "Result with [1], [1], and [2].",
    sources,
)
assert duplicate.is_valid is True
assert duplicate.valid_references == (1, 2)
print("duplicate citations handled safely: PASS")

print("SHY Phase 3 citation validator tests: PASS")
