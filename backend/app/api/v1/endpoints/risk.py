from fastapi import APIRouter, Depends, Query
from app.core.dependencies import get_current_active_user, RoleChecker
from app.db.models.user import User, UserRole
from app.schemas.risk import RiskAssessmentResponse
from app.services.risk_radar import risk_radar_service

router = APIRouter()

@router.get("/verify", response_model=RiskAssessmentResponse)
async def verify_entity(
    query: str = Query(..., description="The name or ID of the entity to verify"),
    current_user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.ORG_ADMIN, UserRole.LAWYER, UserRole.ASSISTANT]))
):
    """
    Verify an entity (company or individual) against local registries and global sanctions list.
    """
    return await risk_radar_service.verify_entity(query)
