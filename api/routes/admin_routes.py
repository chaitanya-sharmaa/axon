"""Admin routes for configuring tenant quotas and system settings."""

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from core.settings import settings
from core.app_config import memory_store

# We check for X-Admin-API-Key header
admin_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)

def verify_admin_key(api_key: str = Security(admin_api_key_header)):
    """Dependency to verify the admin API key."""
    if not settings.admin_api_key:
        raise HTTPException(
            status_code=403, 
            detail="Admin API is disabled (AXON_ADMIN_API_KEY is not set)"
        )
    if not api_key or api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid Admin API Key")
    return api_key

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(verify_admin_key)],
)

class QuotaUpdateRequest(BaseModel):
    monthly_quota_usd: float

class QuotaResponse(BaseModel):
    tenant_id: str
    monthly_quota_usd: float
    current_spend_usd: float

@router.get("/tenants/{tenant_id}", response_model=QuotaResponse)
async def get_tenant_quota(tenant_id: str):
    """Get the current quota and spend for a specific tenant."""
    quota, spend = await memory_store.get_tenant_quota(tenant_id)
    return QuotaResponse(
        tenant_id=tenant_id,
        monthly_quota_usd=quota,
        current_spend_usd=spend
    )

@router.post("/tenants/{tenant_id}", response_model=QuotaResponse)
async def set_tenant_quota(tenant_id: str, request: QuotaUpdateRequest):
    """Set the monthly quota (in USD) for a specific tenant."""
    if request.monthly_quota_usd < 0:
        raise HTTPException(status_code=400, detail="Quota cannot be negative")
        
    await memory_store.set_tenant_quota(tenant_id, request.monthly_quota_usd)
    quota, spend = await memory_store.get_tenant_quota(tenant_id)
    
    return QuotaResponse(
        tenant_id=tenant_id,
        monthly_quota_usd=quota,
        current_spend_usd=spend
    )
