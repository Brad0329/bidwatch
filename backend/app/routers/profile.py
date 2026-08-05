from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.profile import TenantProfile
from app.models.tenant import User

router = APIRouter(prefix="/api/profile", tags=["profile"])


class RegionPreference(BaseModel):
    regions: list[str]  # ["서울", "부산", ...]


class RegionPreferenceResponse(BaseModel):
    regions: list[str]


@router.get("/regions", response_model=RegionPreferenceResponse)
async def get_region_preference(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 관심 지역 조회."""
    result = await db.execute(
        select(TenantProfile).where(TenantProfile.tenant_id == user.tenant_id)
    )
    profile = result.scalar_one_or_none()
    if not profile or not profile.region:
        return RegionPreferenceResponse(regions=[])
    regions = [r.strip() for r in profile.region.split(",") if r.strip()]
    return RegionPreferenceResponse(regions=regions)


@router.put("/regions", response_model=RegionPreferenceResponse)
async def update_region_preference(
    body: RegionPreference,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """사용자의 관심 지역 저장."""
    result = await db.execute(
        select(TenantProfile).where(TenantProfile.tenant_id == user.tenant_id)
    )
    profile = result.scalar_one_or_none()
    region_str = ",".join(body.regions) if body.regions else ""

    if profile:
        profile.region = region_str
    else:
        profile = TenantProfile(tenant_id=user.tenant_id, region=region_str)
        db.add(profile)

    await db.commit()
    return RegionPreferenceResponse(regions=body.regions)
