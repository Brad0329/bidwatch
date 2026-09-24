"""lets_portal 손 설정 사이트를 bidwatch 기본 제공 사이트(scraper_registry.is_builtin)로 옮긴다.

사용법 (저장소 루트에서):
    backend/.venv/Scripts/python.exe backend/scripts/import_builtin_sites.py --dry-run   # 판정만, DB·AI 안 씀
    backend/.venv/Scripts/python.exe backend/scripts/import_builtin_sites.py             # 등록 + 탈락분 AI 분석

사이트마다 (2026-09-24 사용자 결정 "손 설정 먼저, 실패 시 AI"):
  1. 손 설정으로 시험 수집 — AI 설정과 같은 관문(`trial_collect` + `judge_trial`: 0건·제목 커버리지·제목 길이).
     요청이 SSL 인증서 오류로만 실패하면 verify_ssl=False로 한 번 더 본다(lets_portal은 전 사이트 False였다).
  2. 통과 → 손 설정 그대로 ready 등록 + 첫 수집(최근 30일).
  3. 탈락 → AI 분석(`run_analysis` — 사용자 URL 추가와 같은 경로, 곳당 최대 3회 호출 ⚠️ 과금).
  4. AI도 실패 → failed로 남고 목록에 보고.
이미 같은 URL의 스크래퍼가 있으면 새로 만들지 않고 is_builtin만 켠다(ready면 설정도 그대로 둔다).
이름은 언제나 lets_portal 이름(AI가 읽은 이름으로 덮이지 않게). 재실행은 안전하다 — ready는 이름만 맞추고,
실패로 남은 기본 제공 사이트는 `--retry-failed`를 줘야만 다시 AI 분석한다(사이트 장애가 풀린 뒤 쓰는 옵션).
기본 제공 행은 만든 회사가 없다 — created_by_tenant_id NULL (SCHEMA.md 004).
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)  # app.config의 env_file=".env"는 실행 위치 기준
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select  # noqa: E402

from app.database import get_session_factory  # noqa: E402
from app.models.scraper import ScraperRegistry  # noqa: E402
from app.services import scraper_ai  # noqa: E402
from app.services.scraper_analysis import run_analysis  # noqa: E402
from app.services.scraper_collection import collect_scraper  # noqa: E402

DEFAULT_SOURCE = Path(r"C:\Users\user\Documents\lets_portal\backend\collectors\scraper_configs.json")
WORKERS = 5

logger = logging.getLogger("import_builtin_sites")


async def judge_hand_config(config: dict) -> tuple[dict, str | None, int]:
    """손 설정 시험 수집. (최종 설정, 탈락 이유 또는 None, 수집 건수)."""
    config = dict(config)
    diag = None
    try:
        html = await scraper_ai.fetch_page_html(scraper_ai.normalize_url(config["list_url"]))
        diag = scraper_ai.prefer_better_parser(config, scraper_ai.diagnose_config(config, html), html)
    except Exception as e:
        # 1페이지 진단은 보조 신호다 — 못 받아도(SSL 검증·POST 전용 등) 수집 결과로 판정한다
        logger.info(f"  1페이지 진단 생략 {config['name']}: {type(e).__name__}: {e}")

    try:
        titles = await scraper_ai.trial_collect(config)
    except ValueError as e:
        if "SSL" not in str(e) and "certificate" not in str(e).lower() or config.get("verify_ssl") is False:
            return config, str(e), 0
        config["verify_ssl"] = False
        logger.info(f"  SSL 오류로 verify_ssl=False 재시도: {config['name']}")
        try:
            titles = await scraper_ai.trial_collect(config)
        except Exception as e2:
            return config, f"{type(e2).__name__}: {e2}", 0
    except Exception as e:
        return config, f"{type(e).__name__}: {e}", 0

    return config, scraper_ai.judge_trial(config, diag, titles), len(titles)


async def register(hand: dict, config: dict, passed: bool, retry_failed: bool) -> tuple[int, str]:
    """스크래퍼를 찾거나 만들어 is_builtin을 켠다. (scraper_id, 처리 방식)."""
    url = scraper_ai.normalize_url(hand["list_url"])
    async with get_session_factory()() as db:
        scraper = (await db.execute(
            select(ScraperRegistry).where(ScraperRegistry.url_hash == scraper_ai.hash_url(url))
        )).scalar_one_or_none()
        if scraper is not None and scraper.status == "ready":
            scraper.is_builtin = True
            scraper.name = hand["name"]  # 기본 제공 사이트 이름은 lets_portal 이름으로 통일
            await db.commit()
            return scraper.id, "existing_ready"
        if scraper is not None and scraper.is_builtin and not passed and not retry_failed:
            # 재실행이 조용히 AI 비용을 다시 쓰지 않게 — 실패한 기본 제공 사이트는 --retry-failed일 때만 다시 분석
            return scraper.id, "skip_failed"
        if scraper is None:
            scraper = ScraperRegistry(url=url, url_hash=scraper_ai.hash_url(url), name=hand["name"],
                                      status="pending", created_by_tenant_id=None, is_builtin=True)
            db.add(scraper)
        scraper.is_builtin = True
        scraper.name = hand["name"]
        if passed:
            scraper.scraper_config, scraper.status, scraper.analysis_log = config, "ready", None
        else:
            scraper.status = "pending"
        await db.commit()
        return scraper.id, "hand" if passed else "ai"


async def process(hand: dict, dry_run: bool, retry_failed: bool, sem: asyncio.Semaphore) -> dict:
    async with sem:
        config, reason, count = await judge_hand_config(hand)
        row = {"name": hand["name"], "url": hand["list_url"], "hand_count": count,
               "hand_reason": reason, "verify_ssl_off": config.get("verify_ssl") is False}
        if dry_run:
            row["result"] = "HAND_OK" if reason is None else "HAND_FAIL"
            return row

        scraper_id, how = await register(hand, config, reason is None, retry_failed)
        row["scraper_id"] = scraper_id
        if how == "existing_ready":
            row["result"] = "EXISTING_READY"
            if await never_collected(scraper_id):
                # 실측: 전에 사용자 추가로 ready가 됐지만 수집 기록이 없는 행이 있었다(강원관광재단)
                collected = await collect_scraper(scraper_id)
                row["result"], row["collect"] = "EXISTING_COLLECTED", collected.get("status")
        elif how == "skip_failed":
            row["result"] = "SKIPPED_FAILED"
        elif how == "hand":
            collected = await collect_scraper(scraper_id)
            row["result"], row["collect"] = "HAND_READY", collected.get("status")
        else:
            final = await run_analysis(scraper_id)  # AI 분석 + 성공 시 첫 수집. 예외를 던지지 않는다
            await restore_name(scraper_id, hand["name"])  # run_analysis는 AI가 읽은 이름으로 덮는다
            row["result"] = "AI_READY" if final == "ready" else "FAILED"
        return row


async def never_collected(scraper_id: int) -> bool:
    async with get_session_factory()() as db:
        scraper = await db.get(ScraperRegistry, scraper_id)
        return scraper is not None and scraper.last_collected_at is None


async def restore_name(scraper_id: int, name: str) -> None:
    async with get_session_factory()() as db:
        scraper = await db.get(ScraperRegistry, scraper_id)
        if scraper is None:
            logger.error(f"이름 복원 대상 scraper {scraper_id}가 없다")
            return
        scraper.name = name
        await db.commit()


async def main_async(args) -> int:
    hands = json.loads(Path(args.source).read_text(encoding="utf-8"))
    print(f"{'[dry-run] ' if args.dry_run else ''}사이트 {len(hands)}곳 · 동시 {WORKERS}")
    sem = asyncio.Semaphore(WORKERS)
    rows = await asyncio.gather(*(process(h, args.dry_run, args.retry_failed, sem) for h in hands),
                                return_exceptions=True)

    failures = 0
    for hand, row in zip(hands, rows):
        if isinstance(row, BaseException):
            failures += 1
            logger.error(f"예상 밖 예외 {hand['name']}: {row!r}")
            print(f"  [ERROR] {hand['name']}: {type(row).__name__}: {row}")
            continue
        ssl = " (verify_ssl=False)" if row["verify_ssl_off"] else ""
        detail = f"손 설정 {row['hand_count']}건{ssl}"
        if row["hand_reason"]:
            detail += f" — 탈락: {row['hand_reason'][:120]}"
        print(f"  [{row['result']}] {row['name']}: {detail}")

    counts = Counter(r["result"] for r in rows if isinstance(r, dict))
    print("\n=== 집계 ===")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    if failures:
        print(f"  ERROR: {failures}")
    return 1 if failures else 0


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    logger.setLevel(logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", default=str(DEFAULT_SOURCE))
    ap.add_argument("--dry-run", action="store_true", help="시험 수집 판정만 (DB 쓰기·AI 호출 없음)")
    ap.add_argument("--retry-failed", action="store_true",
                    help="이미 실패로 남은 기본 제공 사이트도 AI로 다시 분석 (⚠️ 곳당 최대 3회 과금)")
    sys.exit(asyncio.run(main_async(ap.parse_args())))


if __name__ == "__main__":
    main()
