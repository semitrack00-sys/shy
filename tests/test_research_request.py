import sys
import unittest
from pathlib import Path
from pydantic import ValidationError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services'))
from research.request import ResearchRequest, validate_research_action
from research.freshness import window_selection

class Requests(unittest.TestCase):
    def test_typed_modes_and_explicit_overrides(self):
        for mode,days in [('same_day',0),('past_week',7),('past_month',30),('any_date',None)]:
            request=ResearchRequest.model_validate({'freshness':mode})
            self.assertEqual(window_selection('latest jodi a',request.freshness),(days,'user_selected'))
        self.assertEqual(window_selection('jodi a','auto'),(0,'haitian_creole_hint'))
        with self.assertRaises(ValueError):window_selection('latest','unsupported')
        for value in [{},{'freshness':7},{'freshness':True},{'freshness':None},{'freshness':'unsupported'},{'freshness':'auto','shell':'run'}]:
            with self.assertRaises(ValidationError):ResearchRequest.model_validate(value)
    def test_mixed_actions_and_query_bounds(self):
        valid={'research_request':{'freshness':'any_date'},'message':'Istwa Ayiti'}
        self.assertEqual(validate_research_action(valid),valid)
        self.assertEqual(validate_research_action({**valid,'message':' '*2000+'Istwa Ayiti'+' '*2000})['message'],'Istwa Ayiti')
        for patch in [{'message':' '},{'message':'x'*1001},{'message':7},{'task_id':'id'},{'cancel_task':True},{'pending_step_id':0},{'approval_token':'token'},{'document_question':{}},{'option_comparison':{}},{'local_only':True}]:
            with self.subTest(patch=patch),self.assertRaises(ValueError):validate_research_action({**valid,**patch})
        self.assertEqual(validate_research_action({'message':'ordinary'}),{'message':'ordinary'})

if __name__=='__main__':unittest.main()
