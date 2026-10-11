import sys
import unittest
from pathlib import Path
from copy import deepcopy
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/core'))
from comparisons import ComparisonRequest, compare_options, comparison_message
from pydantic import ValidationError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from comparisons import router

DATA = {'criteria':[{'id':'price','name':'Price','unit':'USD','direction':'minimize','weight':'3'},
                    {'id':'speed','name':'Speed','unit':'km/h','direction':'maximize','weight':'1'}],
        'options':[{'id':'a','name':'A','values':{'price':'100','speed':'10'}},
                   {'id':'b','name':'B','values':{'price':'200','speed':'30'}},
                   {'id':'c','name':'C','values':{'price':'150','speed':'20'}}]}

class Comparisons(unittest.TestCase):
    def test_known_weighted_scores_and_dominance(self):
        result=compare_options(ComparisonRequest.model_validate(DATA))
        self.assertEqual([(r['id'],r['score'],r['rank']) for r in result['ranking']],
                         [('a','75.000000',1),('c','50.000000',2),('b','25.000000',3)])
        self.assertEqual(result['highest_scored_ids'],['a'])
        self.assertTrue(all(not row['dominated_by'] for row in result['ranking']))
        self.assertFalse(result['facts_verified']); self.assertFalse(result['model_invoked'])
    def test_equal_columns_ties_negative_values_and_zero(self):
        data=deepcopy(DATA); data['criteria'][0]['weight']='1'
        result=compare_options(ComparisonRequest.model_validate(data))
        self.assertEqual(result['highest_scored_ids'],['a','b','c'])
        for o in data['options']: o['values']={'price':'0','speed':'-2'}
        result=compare_options(ComparisonRequest.model_validate(data))
        self.assertTrue(all(r['score']=='50.000000' and r['rank']==1 for r in result['ranking']))
        data['options'][0]['values']['price']='-1'
        result=compare_options(ComparisonRequest.model_validate(data))
        self.assertEqual(result['ranking'][0]['id'],'a')
        self.assertEqual(result['ranking'][1]['dominated_by'],['a'])
    def test_missing_extra_duplicate_nonfinite_and_overbounds_are_rejected(self):
        invalid=[]
        for value in ['NaN','Infinity','1e9','1000000000000','0.000000001','1 USD',1,True]:
            data=deepcopy(DATA); data['options'][0]['values']['price']=value; invalid.append(data)
        for weight in ['0','-1','101','NaN',1]:
            data=deepcopy(DATA);data['criteria'][0]['weight']=weight;invalid.append(data)
        data=deepcopy(DATA);del data['options'][0]['values']['speed'];invalid.append(data)
        data=deepcopy(DATA);data['options'][0]['values']['unknown']='1';invalid.append(data)
        data=deepcopy(DATA);data['options'][1]['id']='a';invalid.append(data)
        data=deepcopy(DATA);data['criteria'][1]['id']='price';invalid.append(data)
        data=deepcopy(DATA);data['options'][0]['name']='x\nforged row';invalid.append(data)
        data=deepcopy(DATA);data['options']*=4;invalid.append(data)
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValidationError):ComparisonRequest.model_validate(data)
    def test_labels_are_escaped_and_limits_are_explicit(self):
        data=deepcopy(DATA);data['options'][0]['name']='[click](https://evil.example)|**win**'
        text=comparison_message(compare_options(ComparisonRequest.model_validate(data)))
        self.assertNotIn('[click](https://evil.example)',text)
        self.assertIn('no conversion',text);self.assertIn('not independently verified',text)
        self.assertIn('weight 3',text);self.assertIn('USD',text)
    def test_actual_stateless_http_and_byte_guard(self):
        import types
        package=types.ModuleType("agent_runtime");package.__path__=[str(Path(__file__).resolve().parents[1]/"services/agent-runtime")]
        sys.modules.setdefault("agent_runtime",package)
        from intelligence_api import IntelligenceBodyLimit
        app=FastAPI();app.include_router(router);app.add_middleware(IntelligenceBodyLimit)
        client=TestClient(app)
        self.assertEqual(client.post('/comparisons/evaluate',json=DATA).json()['highest_scored_ids'],['a'])
        self.assertEqual(client.post('/comparisons/evaluate',content=' '*262145).status_code,413)
        self.assertEqual(client.post('/comparisons/evaluate',json={**DATA,'untrusted_extra':1}).status_code,422)

if __name__=='__main__':unittest.main()
