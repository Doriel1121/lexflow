from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class UserStats(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    users_by_role: dict  # e.g., {"admin": 1, "org_admin": 5, "lawyer": 20, ...}

class OrganizationStats(BaseModel):
    total_organizations: int
    active_organizations: int
    inactive_organizations: int
    avg_users_per_org: float
    total_org_members: int

class SubscriptionStats(BaseModel):
    """Treat each organization as a 'subscription'"""
    total_subscriptions: int
    active_subscriptions: int
    org_id_to_user_count: dict  # Map org_id to member count

class SystemHealthMetrics(BaseModel):
    total_documents: int
    total_cases: int
    total_tags: int
    documents_by_organization: dict  # org_id -> count
    most_active_orgs: List[dict]  # [{"org_id": 1, "name": "...", "member_count": 5, "document_count": 20}, ...]

class AdminDashboard(BaseModel):
    """Complete backoffice dashboard for system admin"""
    timestamp: datetime
    user_stats: UserStats
    organization_stats: OrganizationStats
    subscription_stats: SubscriptionStats
    system_health: SystemHealthMetrics
    summary: dict  # Quick stats for dashboard cards
