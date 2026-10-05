import unittest
from intelligence_helpers import rejects
from intelligence import retrieval as r


def passage(identifier="p1", value="solar energy kit", scope="a"):
    return {"id": identifier, "source_id": "doc", "text": value, "scope": scope}


class RetrievalTests(unittest.TestCase):
    def test_051_lossless_chunk_offsets_and_overlap(self):
        value = "abc def " * 100
        chunks = r.chunk_text({"source_id": "doc", "text": value, "chunk_chars": 50, "overlap": 10})["chunks"]
        self.assertEqual(chunks[-1]["end"], len(value))
        for chunk in chunks:
            self.assertEqual(chunk["text"], value[chunk["start"]:chunk["end"]])
        self.assertEqual(chunks[1]["start"], 40)
        rejects(r.chunk_text, {"source_id": "doc", "text": value, "chunk_chars": 50, "overlap": 50})

    def test_052_bm25_filters_scopes_and_ranks_relevant_text(self):
        result = r.rank_passages({"scope": "a", "query": "solar kit", "passages": [passage(), passage("p2", "truck freight"), passage("secret", "solar kit", "b")]})
        self.assertEqual([x["id"] for x in result["passages"]], ["p1"])
        self.assertEqual(result["eligible_count"], 2)
        rejects(r.rank_passages, {"scope": "a", "query": "?", "passages": []})

    def test_053_rrf_promotes_shared_results(self):
        result = r.fuse_rankings({"rankings": [["x", "shared"], ["shared", "y"]]})
        self.assertEqual(result["ranking"][0]["id"], "shared")
        rejects(r.fuse_rankings, {"rankings": [["x", "x"]]})

    def test_054_context_accounts_for_labels_without_partial_evidence(self):
        result = r.pack_context({"scope": "a", "passages": [passage(), passage("p2")], "max_chars": 25})
        self.assertLessEqual(result["chars"], 25)
        self.assertEqual(result["citation_ids"], ["p1"])
        self.assertEqual(result["chars"], len(result["context"]))

    def test_055_exact_quote_validation_and_missing_source(self):
        result = r.validate_citations({"scope": "a", "passages": [passage()], "citations": [{"id": "p1", "quote": "energy"}, {"id": "fake", "quote": "energy"}]})
        self.assertFalse(result["all_valid"])
        self.assertTrue(result["citations"][0]["valid"])
        self.assertFalse(result["citations"][1]["valid"])

    def test_056_structured_conflicts_preserve_source_ids(self):
        result = r.detect_conflicts({"claims": [{"subject": "price", "predicate": "USD", "value": v, "source_id": f"s{i}"} for i, v in enumerate([5, 6])]})
        self.assertFalse(result["conflict_free"])
        self.assertEqual(result["conflicts"][0]["source_ids"], ["s0", "s1"])

    def test_057_freshness_rejects_future_and_naive_dates(self):
        result = r.freshness({"now": "2026-10-05T00:00:00Z", "ttl_seconds": 60, "sources": [{"id": "s", "observed_at": "2026-10-05T00:01:00Z"}]})
        self.assertFalse(result["all_fresh"])
        self.assertTrue(result["sources"][0]["future_timestamp"])
        rejects(r.freshness, {"now": "2026-10-05", "ttl_seconds": 60, "sources": []})

    def test_058_memory_supersedes_verified_same_scope_records(self):
        records = [{"id": str(i), "subject": "project", "scope": "a", "value": v, "verified": True, "observed_at": f"2026-10-0{i+1}T00:00:00Z"} for i, v in enumerate(["Dukens", "SHY"])]
        result = r.consolidate_memory({"scope": "a", "records": records})
        self.assertEqual(result["active_records"][0]["value"], "SHY")
        self.assertEqual(result["superseded_ids"], ["0"])
        records[0]["observed_at"] = records[1]["observed_at"]
        self.assertEqual(r.consolidate_memory({"scope": "a", "records": records})["conflicting_subjects"], ["project"])

    def test_059_redacts_credentials_and_pii(self):
        result = r.redact_text({"text": "api_key=supersecret contact a@example.com 123-45-6789"})
        self.assertNotIn("supersecret", result["text"])
        self.assertNotIn("a@example.com", result["text"])
        self.assertEqual(set(result["redaction_counts"]), {"credential", "email", "ssn"})

    def test_060_answerability_abstains_on_irrelevant_evidence(self):
        p = {"scope": "a", "query": "solar kit", "passages": [passage()]}
        self.assertTrue(r.answerability(p)["answerable"])
        self.assertFalse(r.answerability({**p, "query": "diesel fuel"})["answerable"])


if __name__ == "__main__":
    unittest.main()
