import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/core'))
from document_diff import ordered_preview
class OrderedDiff(unittest.TestCase):
    def test_duplicate_and_reordered_lines_are_not_false_equal(self):
        result=ordered_preview('A\nA\nB','A\nB')
        self.assertEqual((result['deleted_lines'],result['inserted_lines']),(1,0));self.assertFalse(result['line_sequence_equal'])
        changed=ordered_preview('A\nB','B\nA')
        self.assertEqual((changed['deleted_lines'],changed['inserted_lines']),(1,1));self.assertFalse(changed['line_sequence_equal'])
        self.assertEqual(changed['change_hunk_count'],2)
    def test_known_insert_delete_replace_ranges_and_no_execution(self):
        result=ordered_preview('same\nold\ntail','same\nnew\ntail')
        self.assertEqual(result['equal_lines'],2);self.assertEqual(result['hunks'][0]['kind'],'replace')
        self.assertEqual(result['hunks'][0]['left']['samples'],[{'line':2,'text':'old','truncated':False}])
        for left,right,kind in [('', 'x','insert'),('x','','delete'),('x','x\nx','insert')]:
            result=ordered_preview(left,right);self.assertEqual(result['hunks'][0]['kind'],kind)
        result=ordered_preview('=1+2\n<script>run()</script>','=1+3\n<script>run()</script>')
        self.assertEqual(result['hunks'][0]['left']['samples'][0]['text'],'=1+2')
        self.assertFalse(result['semantic_equivalence_checked']);self.assertFalse(result['minimal_patch_guaranteed'])
    def test_line_endings_are_explicitly_outside_the_comparison(self):
        result=ordered_preview('A\r\nB\r\n','A\nB\n')
        self.assertTrue(result['line_sequence_equal']);self.assertFalse(result['text_identical']);self.assertFalse(result['line_endings_compared'])
        self.assertEqual(result['change_hunk_count'],0)
        self.assertTrue(ordered_preview('A\n','A\n')['text_identical'])
    def test_bounded_algorithm_and_accurate_omission_counts(self):
        self.assertEqual(ordered_preview('x\n'*1001,'x')['status'],'unavailable')
        self.assertEqual(ordered_preview('x'*100001,'x')['reason'],'ordered_text_character_limit')
        result=ordered_preview('x\n'*1000,'x\n'*1000);self.assertEqual(result['status'],'evaluated');self.assertEqual(result['equal_lines'],1000)
        result=ordered_preview('\n'.join(f'old{i}\nsame{i}' for i in range(30)),'\n'.join(f'new{i}\nsame{i}' for i in range(30)))
        self.assertEqual(result['change_hunk_count'],30);self.assertEqual(len(result['hunks']),10);self.assertEqual(result['omitted_hunks'],20);self.assertTrue(result['preview_truncated'])
        result=ordered_preview(('x'*300+'\n')*10,('y'*300+'\n')*10)
        self.assertEqual(result['hunks'][0]['left']['omitted_lines'],8);self.assertTrue(result['hunks'][0]['left']['samples'][0]['truncated'])
        self.assertEqual(len(result['hunks'][0]['left']['samples'][0]['text']),150)
if __name__=='__main__':unittest.main()
