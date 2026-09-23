"""AI 스크래퍼 성공률 측정 — 손으로 맞춘 설정(정답)과 AI 생성 설정을 같은 사이트에서 비교.

사용법 (저장소 루트에서):
    backend/.venv/Scripts/python.exe backend/scripts/measure_ai_scraper.py [정답 설정 JSON 경로] [--limit N]

각 사이트마다:
  1. 기준선: 정답 설정으로 GenericScraper 수집 (lets_portal과 같게 verify_ssl=False)
  2. AI: bidwatch 실경로 analyze_url() → GenericScraper 수집 (AI 설정 그대로)
  3. 판정: 기준선 제목과의 겹침 비율로 SUCCESS / PARTIAL / FAIL_* / SITE_EMPTY

⚠️ Claude API를 사이트당 1회 호출한다(과금). 결과 JSON은 임시 디렉토리에 저장하고 경로를 출력한다.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)  # app.config의 env_file=".env"는 실행 위치 기준 — backend/.env를 읽게 한다

from bid_collectors import GenericScraper  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.scraper_ai import analyze_url  # noqa: E402

DEFAULT_TRUTH = Path(r"C:\Users\user\Documents\lets_portal\backend\collectors\scraper_configs.json")
DAYS = 90  # 게시가 뜸한 게시판에서 기간 탓 0건이 나오지 않게 넉넉히
SUCCESS_OVERLAP = 0.5
WORKERS = 5

logger = logging.getLogger("measure_ai_scraper")


async def _collect(config: dict) -> tuple[list[str] | None, str | None]:
    try:
        result = await GenericScraper(config).collect(days=DAYS)
        return [n.title for n in result.notices], None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _classify_ai_error(msg: str) -> str:
    if msg.startswith("페이지를 가져올 수 없습니다") or msg.startswith("페이지 내용이 너무 짧습니다"):
        return "FAIL_FETCH"
    if msg.startswith("AI 분석 실패") or "거부" in msg or "max_tokens" in msg:
        return "FAIL_AI"
    if msg.startswith("시험 수집 실패"):
        return "FAIL_TRIAL"  # 재시도를 모두 써도 시험 수집을 통과하지 못함
    return "FAIL_AI_OUTPUT"  # JSON 파싱·필수 필드 누락


async def _measure_site(truth: dict) -> dict:
    row = {"name": truth["name"], "url": truth["list_url"]}

    base_cfg = dict(truth, verify_ssl=False)
    base_titles, base_err = await _collect(base_cfg)
    row["baseline_count"] = len(base_titles) if base_titles is not None else None
    row["baseline_error"] = base_err

    t0 = time.time()
    try:
        ai_cfg = await analyze_url(truth["list_url"])
    except Exception as e:
        row["ai_seconds"] = round(time.time() - t0, 1)
        row["ai_error"] = str(e)
        row["verdict"] = _classify_ai_error(str(e))
        return row
    row["ai_seconds"] = round(time.time() - t0, 1)
    row["ai_config"] = ai_cfg

    ai_titles, ai_err = await _collect(ai_cfg)
    row["ai_count"] = len(ai_titles) if ai_titles is not None else None
    row["ai_collect_error"] = ai_err

    if ai_titles is None:
        # pydantic 검증 실패(source_key 형식 등) 또는 수집 중 예외
        row["verdict"] = "FAIL_CONFIG" if "ValidationError" in (ai_err or "") else "FAIL_COLLECT"
        return row

    if not base_titles:
        row["verdict"] = "SITE_EMPTY_AI_OK" if ai_titles else "SITE_EMPTY"
        return row

    overlap = len(set(base_titles) & set(ai_titles)) / len(set(base_titles))
    row["overlap"] = round(overlap, 2)
    if not ai_titles:
        row["verdict"] = "FAIL_ZERO"
    elif overlap >= SUCCESS_OVERLAP:
        row["verdict"] = "SUCCESS"
    else:
        row["verdict"] = "PARTIAL"
    return row


def _run_one(truth: dict) -> dict:
    try:
        row = asyncio.run(_measure_site(truth))
    except Exception as e:
        logger.exception("사이트 측정 중 예상 밖 예외: %s", truth.get("name"))
        row = {"name": truth.get("name"), "url": truth.get("list_url"),
               "verdict": "HARNESS_ERROR", "error": f"{type(e).__name__}: {e}"}
    print(f"  [{row['verdict']}] {row['name']}", flush=True)
    return row


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING)

    ap = argparse.ArgumentParser()
    ap.add_argument("truth", nargs="?", default=str(DEFAULT_TRUTH))
    ap.add_argument("--limit", type=int, default=0, help="앞에서 N개만 (0=전체)")
    args = ap.parse_args()

    truths = json.loads(Path(args.truth).read_text(encoding="utf-8"))
    total = len(truths)
    if args.limit:
        truths = truths[: args.limit]
        print(f"--limit {args.limit}: 전체 {total}개 중 {len(truths)}개만 측정")
    print(f"모델 {settings.SCRAPER_AI_MODEL} · 사이트 {len(truths)}개 · days={DAYS} · 동시 {WORKERS}")

    with ThreadPoolExecutor(WORKERS) as ex:
        rows = list(ex.map(_run_one, truths))

    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    evaluable = len(rows) - counts.get("SITE_EMPTY", 0) - counts.get("SITE_EMPTY_AI_OK", 0)

    print("\n=== 집계 ===")
    for k in sorted(counts):
        print(f"  {k}: {counts[k]}")
    print(f"평가 가능(기준선 1건 이상): {evaluable} / 성공: {counts.get('SUCCESS', 0)}")

    out_dir = Path(tempfile.gettempdir()) / "bidwatch_ai_measure"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{settings.SCRAPER_AI_MODEL}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"model": settings.SCRAPER_AI_MODEL, "days": DAYS, "rows": rows},
                              ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"결과: {out}")


if __name__ == "__main__":
    main()
