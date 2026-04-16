from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.tag import TenantTag
from app.models.tenant import User
from app.schemas.tag import TagCreateRequest, TagResponse, TagUpdateRequest

router = APIRouter(prefix="/api/tags", tags=["tags"])


@router.get("", response_model=list[TagResponse])
async def list_tags(
    tag: str | None = None,
    notice_type: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """테넌트의 태그 목록. tag/notice_type으로 필터 가능."""
    query = (
        select(TenantTag)
        .where(TenantTag.tenant_id == user.tenant_id)
        .order_by(TenantTag.created_at.desc())
    )
    if tag:
        query = query.where(TenantTag.tag == tag)
    if notice_type:
        query = query.where(TenantTag.notice_type == notice_type)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/notice/{notice_type}/{notice_id}", response_model=TagResponse | None)
async def get_notice_tag(
    notice_type: str,
    notice_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특정 공고의 태그 조회."""
    result = await db.execute(
        select(TenantTag).where(
            TenantTag.tenant_id == user.tenant_id,
            TenantTag.notice_type == notice_type,
            TenantTag.notice_id == notice_id,
        )
    )
    return result.scalar_one_or_none()


@router.put("", response_model=TagResponse)
async def upsert_tag(
    req: TagCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """태그 생성 또는 변경 (공고당 1개이므로 upsert)."""
    result = await db.execute(
        select(TenantTag).where(
            TenantTag.tenant_id == user.tenant_id,
            TenantTag.notice_type == req.notice_type,
            TenantTag.notice_id == req.notice_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.tag = req.tag
        existing.memo = req.memo
        existing.tagged_by = user.id
    else:
        existing = TenantTag(
            tenant_id=user.tenant_id,
            notice_type=req.notice_type,
            notice_id=req.notice_id,
            tag=req.tag,
            tagged_by=user.id,
            memo=req.memo,
        )
        db.add(existing)

    await db.commit()
    await db.refresh(existing)
    return existing


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """태그 삭제."""
    tag = await db.get(TenantTag, tag_id)
    if not tag or tag.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="태그를 찾을 수 없습니다")

    await db.delete(tag)
    await db.commit()
