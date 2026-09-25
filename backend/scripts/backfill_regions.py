"""기존 공고의 region 값을 normalize_region()으로 소급 정규화.

normalize_region()은 수집 시점에만 적용되므로, Phase 1-8 이전에 수집된 공고는
"전라남도 여수시" 같은 원본 값이 그대로 남아 지역 필터에 걸리지 않는다.
이 스크립트를 한 번 실행하면 기존 데이터도 정규화된다.

    python -m scripts.backfill_regions --dry-run   # 변경 예정 내역만 출력
    python -m scripts.backfill_regions             # 실제 반영

distinct 값 단위로 UPDATE하므로 행 수가 아니라 고유 지역 표기 수만큼만 쿼리한다.
"""

import argparse
import asyncio

import asyncpg

from app.config import settings
from app.services.region import normalize_region, notice_region

TABLES = ["bid_notices", "scraped_notices"]


def _dsn() -> str:
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def backfill_table(conn: asyncpg.Connection, table: str, dry_run: bool) -> None:
    rows = await conn.fetch(
        f"select region, count(*) as n from {table} "
        "where coalesce(region, '') <> '' group by region"
    )

    changes = []
    for row in rows:
        raw = row["region"]
        normalized = normalize_region(raw)
        if normalized != raw:
            changes.append((raw, normalized, row["n"]))

    if not changes:
        print(f"[{table}] 변경할 값 없음 (고유 표기 {len(rows)}개)")
        return

    changes.sort(key=lambda c: -c[2])
    affected = sum(c[2] for c in changes)
    print(
        f"[{table}] 고유 표기 {len(rows)}개 중 {len(changes)}개 정규화 "
        f"→ 공고 {affected}건 영향"
    )
    for raw, normalized, n in changes[:15]:
        print(f"    {n:5d}  {raw!r} -> {normalized!r}")
    if len(changes) > 15:
        print(f"    ... 외 {len(changes) - 15}개")

    if dry_run:
        print(f"[{table}] --dry-run 이므로 반영하지 않음")
        return

    async with conn.transaction():
        for raw, normalized, _ in changes:
            await conn.execute(
                f"update {table} set region = $1 where region = $2", normalized, raw
            )
    print(f"[{table}] 반영 완료")


async def backfill_site_region(conn: asyncpg.Connection, dry_run: bool) -> None:
    """나라장터 공사: 공사현장 지역(extra.cnstrtsiteRgnNm)으로 (2026-09-25, notice_region과 같은 규칙).

    수요기관명에서 뽑은 region이 기관명 그대로 남아 지역 필터에 안 걸리던 행이 대부분이다.
    """
    rows = await conn.fetch(
        "select coalesce(region, '') as region, extra->>'cnstrtsiteRgnNm' as site, count(*) as n "
        "from bid_notices where coalesce(extra->>'cnstrtsiteRgnNm', '') <> '' group by 1, 2"
    )
    changes = []
    for row in rows:
        new = notice_region(row["region"], {"cnstrtsiteRgnNm": row["site"]})
        if new != row["region"]:
            changes.append((row["region"], row["site"], new, row["n"]))

    affected = sum(c[3] for c in changes)
    print(f"[bid_notices 공사현장] (지역, 현장) 조합 {len(rows)}개 중 {len(changes)}개 변경 → 공고 {affected}건 영향")
    for old, site, new, n in sorted(changes, key=lambda c: -c[3])[:15]:
        print(f"    {n:5d}  {old!r} (현장 {site!r}) -> {new!r}")
    if dry_run or not changes:
        if dry_run:
            print("[bid_notices 공사현장] --dry-run 이므로 반영하지 않음")
        return

    async with conn.transaction():
        for old, site, new, _ in changes:
            await conn.execute(
                "update bid_notices set region = $1 "
                "where coalesce(region, '') = $2 and extra->>'cnstrtsiteRgnNm' = $3",
                new, old, site,
            )
    print("[bid_notices 공사현장] 반영 완료")


async def main(dry_run: bool) -> None:
    conn = await asyncpg.connect(_dsn())
    try:
        for table in TABLES:
            await backfill_table(conn, table, dry_run)
        await backfill_site_region(conn, dry_run)
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true", help="변경 내역만 출력하고 DB는 건드리지 않음"
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
