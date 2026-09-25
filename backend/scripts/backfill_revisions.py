"""기존 공고에 나라장터 차수 정리(이전 차수·취소·태그 이동)를 소급 적용한다 (F-017, 006 이후 1회).

수집 저장 직후와 같은 함수(services/collection.refresh_revisions)를 모든 공공 출처에 부른다.

    python -m scripts.backfill_revisions --dry-run   # 바뀔 건수만 (반영 안 함)
    python -m scripts.backfill_revisions             # 실제 반영
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.database import get_session_factory
from app.models.notice import SystemSource
from app.services.collection import refresh_revisions


async def main(dry_run: bool) -> None:
    async with get_session_factory()() as db:
        sources = (await db.execute(select(SystemSource.id, SystemSource.collector_type))).all()
        for source_id, ctype in sources:
            if dry_run:
                # 같은 계산을 트랜잭션 안에서 하고 되돌린다 — commit 대신 rollback
                db.commit = db.rollback  # type: ignore[method-assign]
            result = await refresh_revisions(source_id, db)
            print(f"[{ctype}] {result}" + (" (dry-run — 되돌림)" if dry_run else ""))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="바뀔 건수만 출력하고 되돌린다")
    asyncio.run(main(parser.parse_args().dry_run))
