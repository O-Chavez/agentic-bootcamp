# schemas.py
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field

# 1. The structured output we force the LLM to return during analysis
class ExpenseAnalysis(BaseModel):
    category: Literal["meal", "flight", "software_saas", "other"] = Field(
        description="The primary category of the expense."
    )
    merchant: str = Field(description="The name of the vendor or merchant.")
    amount: float = Field(description="The total dollar amount listed on the receipt.")
    violates_policy: bool = Field(
        description="True if the expense clearly violates company rules (e.g. meal > $75)."
    )
    justification: str = Field(
        description="Brief explanation of the policy evaluation or any red flags found."
    )

# 2. The Global State Machine Object (The single source of truth for a transaction)
class ExpenseState(BaseModel):
    transaction_id: str
    raw_receipt_text: str
    analysis: Optional[ExpenseAnalysis] = None
    status: Literal["triage", "awaiting_manager_approval", "auto_approved", "rejected"] = "triage"
    reviewer_notes: Optional[str] = None
