"""Offline fixed-case checks. Does not measure live-model or source-truth accuracy."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'services'));sys.path.insert(0, str(ROOT/'services/core'))
from tools.arithmetic import calculator_result
from comparisons import ComparisonRequest, compare_options
from document_diff import ordered_preview
from research.synthesis_guard import synthesis_sources, validate_synthesis
from research.claim_checks import disagreement_pairs
from research.freshness import source_timing

FIXTURE = ROOT/'docs/examples/reasoning-benchmark.json'


def evaluate_case(case):
    kind, data = case['kind'], case['input']
    if kind == 'arithmetic': return calculator_result(data)['decimal_result']
    if kind == 'comparison':
        return [(row['id'],row['score']) for row in compare_options(ComparisonRequest.model_validate(data))['ranking']]
    if kind == 'ordered_document_lines':
        result=ordered_preview(data['left'],data['right'])
        return {key:result.get(key) for key in ['status','inserted_lines','deleted_lines','line_sequence_equal','text_identical']}
    if kind == 'citation_membership':
        sources=synthesis_sources(data['evidence']);validate_synthesis(data['answer'],sources);return 'accepted'
    if kind == 'possible_disagreement':
        return len(disagreement_pairs(data,synthesis_sources(data)))
    if kind == 'provider_date_estimate':
        return source_timing(data['date'],datetime(2026,10,11,12,tzinfo=timezone.utc),data['window'])['source_date_status']
    raise ValueError('Unknown benchmark kind')


def run_benchmark(path=FIXTURE):
    raw=path.read_bytes();cases=json.loads(raw)['cases'];results=[]
    for case in cases:
        try:
            actual=evaluate_case(case)
            # Compare JSON representations so tuple/list implementation details do not matter.
            passed='reject' not in case and json.dumps(actual)==json.dumps(case['expected'])
            detail={'actual':actual}
        except ValueError as exc:
            passed=case.get('reject') is True
            detail={'rejected':True,'error':str(exc)[:200]}
        except Exception as exc:
            passed=False;detail={'unexpected_error':type(exc).__name__}
        results.append({'id':case['id'],'kind':case['kind'],'passed':passed,**detail})
    return {'benchmark':'bounded_research_reasoning_v2','fixture_sha256':hashlib.sha256(raw).hexdigest(),
            'case_count':len(results),'passed_count':sum(r['passed'] for r in results),'results':results,
            'live_model_quality_measured':False,'source_truth_verified':False,'hardware_performance_measured':False,
            'qualification_complete':False,
            'remaining':['live provider and model answer quality','semantic claim support','representative user questions','target hardware latency']}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',required=True);args=parser.parse_args()
    report=run_benchmark();destination=Path(args.report);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(f"Bounded reasoning checks: {report['passed_count']}/{report['case_count']}; live-model qualification remains pending.")
    return 0 if report['passed_count']==report['case_count'] else 1

if __name__=='__main__':sys.exit(main())
