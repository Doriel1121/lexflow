from pydantic import BaseModel, Field
from typing import Optional, List, Any

# Local Israeli Gov Data Responses
class LocalRiskMatchedEntity(BaseModel):
    id: str
    name: str
    address: Optional[str] = None
    status: Optional[str] = None
    is_high_risk: bool = False
    risk_reason: Optional[str] = None

# Global OpenSanctions Data Responses
class GlobalRiskMatchedEntity(BaseModel):
    id: str
    name: str
    datasets: List[str] = []
    is_high_risk: bool = False
    risk_reason: Optional[str] = None

# Unified Response
class RiskAssessmentResponse(BaseModel):
    query: str
    auto_fill_name: Optional[str] = None
    auto_fill_address: Optional[str] = None
    is_high_risk: bool = False
    local_risk: Optional[LocalRiskMatchedEntity] = None
    global_risk: Optional[GlobalRiskMatchedEntity] = None
    warnings: List[str] = []

