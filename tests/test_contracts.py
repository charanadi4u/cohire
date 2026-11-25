import pytest, copy
from app.privacy.pipeline import document,extract,validate_refs,preview
from app.agents.specialists import demo,factory
from app.domain.contracts import Assessment,Profile
from app.domain.scoring import score
from app.config import settings
from app.evaluation.release import evaluate

def sample():
    jd=document('Required: Python\nRequired: FastAPI\nPreferred: GCP')
    cd=document('Built Python API services.')
    j={'document':jd,'profile':demo('job',{'document':jd}),'rubric':{'R1':.5,'R2':.3,'R3':.2}}
    c={'document':cd,'profile':demo('resume',{'document':cd})}
    a=demo('match',{'job':j,'candidate':c})
    return j,c,a

def test_scoring_unknown_bound():
    j,c,a=sample();r=score(j,c,a)
    assert r['score']==50 and r['coverage']==.5 and r['score_upper_bound']==100
    assert not r['proposal_eligible']

def test_fabricated_citation_blocked():
    j,c,a=sample();a['assessments'][0]['candidate_evidence_ids']=['invented']
    with pytest.raises(ValueError):score(j,c,a)

def test_tampered_excerpt_blocked():
    j,c,a=sample();c['document']['spans'][0]['excerpt']='fabricated'
    with pytest.raises(ValueError):score(j,c,a)

@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1])
def test_invalid_weight(value):
    j,c,a=sample();j['rubric']['R1']=value
    with pytest.raises(ValueError):score(j,c,a)

def test_missing_assessment():
    j,c,a=sample();a['assessments'].pop()
    with pytest.raises(ValueError):score(j,c,a)

def test_known_requires_evidence():
    with pytest.raises(ValueError):Assessment(requirement_id='R1',status='supported',value=1,candidate_evidence_ids=[],job_evidence_ids=['E1'],rationale='test')

def test_identity_fields_rejected():
    with pytest.raises(ValueError):Profile(skills=[],name='Person')

def test_identity_only_edits_same_scores():
    p1=preview('Name: Aarav Rao\nBuilt Python backend services.')
    p2=preview('Name: Meera Das\nBuilt Python backend services.')
    assert p1==p2

def test_scanned_or_empty_fails():
    with pytest.raises(ValueError):extract(b'   ','resume.txt')

def test_adk_agent_construction(monkeypatch):
    monkeypatch.setattr(settings(),'gemini_parse_model','integration-test-model')
    monkeypatch.setattr(settings(),'gemini_match_model','integration-test-model')
    for kind in ('resume','job','match','intent'):
        agent=factory(kind);assert agent.output_schema and not agent.tools

def test_evaluation_duplicate_leakage():
    row={'candidate_id':'a','job_id':'b','split':'test','predicted':'supported','expected':'supported'}
    with pytest.raises(ValueError):evaluate([row,row])
