from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ClaimStatus = Literal["approved", "partially_approved", "rejected", "pending"]


class Member(BaseModel):
    id: str
    name: str
    plan_id: str
    policy_start_date: date
    age: int


class Claim(BaseModel):
    id: str
    hospital: str
    procedure: str
    amount_claimed: int
    amount_approved: int | None
    status: ClaimStatus
    rejection_reason: str | None
    submitted_on: date


class Citation(BaseModel):
    source_file: str
    section: str
    quote: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    tools_used: list[str]
    refused: bool
    ticket_id: int | None = None
    request_id: str
