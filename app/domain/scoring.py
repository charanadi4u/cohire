import math
from app.domain.contracts import Assessments, JobProfile
from app.privacy.pipeline import validate_refs, ensure_safe

def score(job, candidate, result):
    rubric=job['rubric']; requirements=JobProfile.model_validate(job['profile']).requirements
    assessments=Assessments.model_validate(result).assessments
    ids={r.id for r in requirements}
    if len(assessments)!=len(ids) or {a.requirement_id for a in assessments}!=ids: raise ValueError('ASSESSMENT_SET_MISMATCH')
    if set(rubric)!=ids or any(not math.isfinite(w) or w<=0 for w in rubric.values()) or abs(sum(rubric.values())-1)>1e-6: raise ValueError('INVALID_RUBRIC')
    total=coverage=0.
    unknown=[]; gaps=[]; strengths=[]
    by_id={r.id:r for r in requirements}
    for a in assessments:
        if a.status=='partial': raise ValueError('PARTIAL_CREDIT_POLICY_NOT_ENABLED')
        validate_refs(a.candidate_evidence_ids,candidate['document']); validate_refs(a.job_evidence_ids,job['document'])
        if not set(a.job_evidence_ids).issubset(by_id[a.requirement_id].evidence_ids): raise ValueError('WRONG_JOB_EVIDENCE')
        ensure_safe(a.rationale)
        if a.status=='unknown': unknown.append(a.requirement_id)
        else:
            total+=rubric[a.requirement_id]*a.value
            coverage+=rubric[a.requirement_id]
            (strengths if a.status=='supported' else gaps).append(a.requirement_id)
    required_unknown=any(by_id[x].necessity!='preferred' for x in unknown)
    return {'score':100*total,'coverage':coverage,'score_upper_bound':100*(total+1-coverage),
            'review_required':True,'proposal_eligible':total>=.8-1e-9 and coverage>=.9-1e-9 and not required_unknown and not gaps,
            'strengths':strengths,'gaps':gaps,'unknowns':unknown,'assessments':[a.model_dump() for a in assessments],
            'scoring_version':'weighted-evidence-v1','rubric':rubric,'candidate_revision':1,'job_revision':1}
