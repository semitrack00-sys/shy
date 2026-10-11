import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evaluate_reasoning import run_benchmark
class Benchmark(unittest.TestCase):
    def test_fixed_reference_cases_and_honest_qualification(self):
        report=run_benchmark()
        self.assertEqual(report['case_count'],33)
        self.assertEqual(report['passed_count'],33,report['results'])
        self.assertEqual(len({r['id'] for r in report['results']}),33)
        self.assertFalse(report['qualification_complete'])
        self.assertFalse(report['live_model_quality_measured'])
        self.assertFalse(report['source_truth_verified'])
if __name__=='__main__':unittest.main()
