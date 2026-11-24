from datetime import date
from typing import Literal

from pydantic import BaseModel

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
