from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.keyword import TenantKeyword
from app.models.tenant import Tenant, User
from app.schemas.keyword import KeywordCreateRequest, KeywordResponse, KeywordUpdateRequest

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


@router.get("", response_model=list[KeywordResponse])
async def list_keywords(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TenantKeyword)
        .where(TenantKeyword.tenant_id == user.tenant_id)
        .order_by(TenantKeyword.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=KeywordResponse, status_code=201)
async def create_keyword(
    req: KeywordCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 제한 체크
    tenant = await db.get(Tenant, user.tenant_id)
    from sqlalchemy import func
    count = await db.scalar(
        select(func.count()).select_from(TenantKeyword)
        .where(TenantKeyword.tenant_id == user.tenant_id)
    )
    if tenant and count >= tenant.max_keywords:
        raise HTTPException(
            status_code=403,
            detail=f"키워드 최대 개수({tenant.max_keywords})를 초과했습니다",
        )

    # 중복 체크
    existing = await db.scalar(
        select(TenantKeyword.id).where(
            TenantKeyword.tenant_id == user.tenant_id,
            TenantKeyword.keyword == req.keyword,
        )
    )
    if existing:
        raise HTTPException(status_code=409, detail="이미 등록된 키워드입니다")

    kw = TenantKeyword(
        tenant_id=user.tenant_id,
        keyword=req.keyword,
        keyword_group=req.keyword_group,
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw


@router.patch("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: int,
    req: KeywordUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kw = await db.get(TenantKeyword, keyword_id)
    if not kw or kw.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    if req.is_active is not None:
        kw.is_active = req.is_active
    if req.keyword_group is not None:
        kw.keyword_group = req.keyword_group

    await db.commit()
    await db.refresh(kw)
    return kw


@router.delete("/{keyword_id}", status_code=204)
async def delete_keyword(
    keyword_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kw = await db.get(TenantKeyword, keyword_id)
    if not kw or kw.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="키워드를 찾을 수 없습니다")

    await db.delete(kw)
    await db.commit()
