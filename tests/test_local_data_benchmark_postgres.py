import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evaluate_local_data import run_benchmark
@unittest.skipUnless(os.environ.get('DATABASE_URL'),'Disposable PostgreSQL required')
class LocalDataBenchmark(unittest.TestCase):
    def test_fixed_persistence_isolation_and_provenance_cases(self):
        report=run_benchmark()
        self.assertEqual(report['case_count'],62)
        self.assertEqual(report['passed_count'],62,report['results'])
        self.assertEqual(len({row['id'] for row in report['results']}),62)
        self.assertFalse(report['qualification_complete'])
        self.assertFalse(report['generated_answer_accuracy_measured'])
if __name__=='__main__':unittest.main()
