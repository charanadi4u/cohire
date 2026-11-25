from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class Span(Strict):
    id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    excerpt: str = Field(max_length=4000)
    sha256: str

class Skill(Strict):
    term: str = Field(max_length=80)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    evidence_type: Literal['claimed', 'demonstrated'] = 'claimed'

class Profile(Strict):
    skills: list[Skill] = Field(max_length=100)
    warnings: list[str] = Field(default_factory=list, max_length=20)

class Requirement(Strict):
    id: str = Field(max_length=80)
    term: str = Field(max_length=80)
    necessity: Literal['required', 'preferred', 'unclear']
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    weight: float = Field(default=1, gt=0, le=100)

class JobProfile(Strict):
    title: str = Field(max_length=160)
    requirements: list[Requirement] = Field(min_length=1, max_length=50)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    @model_validator(mode='after')
    def unique(self):
        if len({r.id for r in self.requirements}) != len(self.requirements):
            raise ValueError('Duplicate requirement IDs')
        if len({r.term.lower() for r in self.requirements}) != len(self.requirements):
            raise ValueError('Duplicate requirement terms')
        return self

class Assessment(Strict):
    requirement_id: str
    status: Literal['supported', 'partial', 'not_met', 'unknown']
    value: float | None = Field(default=None, ge=0, le=1)
    candidate_evidence_ids: list[str] = Field(max_length=20)
    job_evidence_ids: list[str] = Field(min_length=1, max_length=20)
    rationale: str = Field(max_length=600)
    @model_validator(mode='after')
    def check(self):
        expected = {'supported':1., 'partial':.5, 'not_met':0., 'unknown':None}[self.status]
        if self.value != expected:
            raise ValueError('Status/value mismatch')
        if self.status != 'unknown' and not self.candidate_evidence_ids:
            raise ValueError('Known assessment requires evidence')
        return self

class Assessments(Strict):
    assessments: list[Assessment] = Field(max_length=50)

class SourceApproval(Strict):
    sanitized_text: str = Field(min_length=20, max_length=50000)
    identity_removed: Literal[True]

class RubricApproval(Strict):
    weights: dict[str, float]

class RunRequest(Strict):
    job_id: str
    candidate_ids: list[str] = Field(min_length=1, max_length=50)
    @model_validator(mode='after')
    def unique(self):
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            raise ValueError('Duplicate candidates')
        return self

class Review(Strict):
    action: Literal['advance', 'hold']
    reason: str = Field(min_length=5, max_length=1000)

class Slot(Strict):
    start: str
    end: str
    timezone: str

class Feedback(Strict):
    label: Literal['evidence_correct', 'evidence_incorrect', 'needs_more_evidence']
    note: str = Field(max_length=1000)

class Intent(Strict):
    action: Literal['parse_resume', 'parse_job', 'match', 'status', 'propose_interview', 'clarify']
    explanation: str = Field(max_length=400)
