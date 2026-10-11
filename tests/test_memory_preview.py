import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/core'))
from memory_controls import PreviewRequest
from pydantic import ValidationError
class MemoryPreview(unittest.TestCase):
    def test_preview_is_bounded_and_needs_no_mutation_confirmation(self):
        request=PreviewRequest(subject_key='project.database',category='PROJECT',content='  PostgreSQL 16.  ')
        self.assertEqual(request.content,'PostgreSQL 16.')
        for content in ['', ' ', 'x'*501, 'My password is secret123']:
            with self.assertRaises(ValidationError):PreviewRequest(subject_key='project.database',content=content)
        with self.assertRaises(ValidationError):PreviewRequest(subject_key='project.database',content='Value',confirmed=True)
if __name__=='__main__':unittest.main()
