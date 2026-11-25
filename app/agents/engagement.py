"""Candidate-safe deterministic FAQ fallback; no private recruiter notes."""
FAQ={'format':'The proposed interview is a technical discussion. Duration will be confirmed with your slot.',
     'status':'Your application is under recruiter review. No hiring decision has been communicated.'}
def draft_answer(question_key):
    if question_key not in FAQ:return {'draft':'A recruiter will need to answer this question.','escalate':True,'sent':False}
    return {'draft':FAQ[question_key],'faq_version':'v1','escalate':False,'sent':False}
