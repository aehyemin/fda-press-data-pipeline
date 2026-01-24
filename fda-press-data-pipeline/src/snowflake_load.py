import os, json
from datetime import datetime, date
from collections import Counter
from dotenv import load_dotenv
import snowflake.connector

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERIFIED_PATH = os.path.join(BASE_DIR, "data", "curated", "verified_articles.jsonl")


def read_jsonl(path:str) -> list[dict]:
    items = []
    if not os.path.exists(path):
        return items
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items

def sf_connect():
    load_dotenv()
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        role=os.getenv("SNOWFLAKE_ROLE"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA"),
    )



MERGE_ARTICLE_SQL = """
MERGE INTO FDA_DB.PUBLIC.FDA_ARTICLES t
USING (
  SELECT
    %(url_hash)s::STRING AS url_hash,
    %(title)s::STRING AS title,
    %(article_date)s::DATE AS article_date,
    %(url)s::STRING AS url,
    %(summary_ko)s::STRING AS summary_ko,
    PARSE_JSON(%(keywords)s) AS keywords,
    PARSE_JSON(%(main_entity)s) AS main_entity,
    PARSE_JSON(%(evidence)s) AS evidence,
    %(is_verified)s::BOOLEAN AS is_verified,
    PARSE_JSON(%(verification_errs)s) AS verification_errs,
    %(processed_at)s::TIMESTAMP_NTZ AS processed_at
) s
ON t.url_hash = s.url_hash

WHEN MATCHED THEN UPDATE SET
  title = s.title,
  article_date = s.article_date,
  url = s.url,
  summary_ko = s.summary_ko,
  keywords = s.keywords,
  main_entity = s.main_entity,
  evidence = s.evidence,
  is_verified = s.is_verified,
  verification_errs = s.verification_errs,
  processed_at = s.processed_at,
  updated_at = CURRENT_TIMESTAMP()
  
WHEN NOT MATCHED THEN INSERT (
  url_hash, title, article_date, url,
  summary_ko, keywords, main_entity, evidence,
  is_verified, verification_errs,
  processed_at, ingested_at, updated_at
) VALUES (
  s.url_hash, s.title, s.article_date, s.url,
  s.summary_ko, s.keywords, s.main_entity, s.evidence,
  s.is_verified, s.verification_errs,
  s.processed_at, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
);
"""

MERGE_METRIC_SQL = """
MERGE INTO FDA_DB.PUBLIC.MONITOR_METRIC_DAILY t
USING (
  SELECT
    %(run_id)s::STRING AS run_id,
    %(run_ts)s::TIMESTAMP_NTZ AS run_ts,
    %(metric_date)s::DATE AS metric_date,
    PARSE_JSON(%(metric_json)s) AS metric_json
) s
ON t.run_id = s.run_id
WHEN MATCHED THEN UPDATE SET
  run_ts = s.run_ts,
  metric_date = s.metric_date,
  metric_json = s.metric_json,
  updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (
  run_id, run_ts, metric_date, metric_json, created_at, updated_at
) VALUES (
  s.run_id, s.run_ts, s.metric_date, s.metric_json, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
);
"""

def build_metrics(records: list[dict]) -> dict:
    total = len(records)
    if total == 0:
        return {"total": 0, "verified_ok": 0, "verified_fail": 0, "fail_rate": 0, "top_errors": []}
    
    ok = sum(1 for r in records if r.get("is_verified") is True)
    fail = total - ok

    c = Counter()
    for r in records:
        if r.get("is_verified") is True:
            continue
        for e in (r.get("verification_errs") or []):
            etype = str(e).split(":")[0]
            c[etype] += 1

    top_errors = [{"type": k, "count": v} for k, v in c.most_common(10)]
    fail_rate = (fail / total)

    return {
        "total": total,
        "verified_ok": ok,
        "verified_fail": fail,
        "fail_rate": fail_rate,
        "top_errors": top_errors,
    }

def main():
    print(f"data from: {VERIFIED_PATH}")
    records = read_jsonl(VERIFIED_PATH)
    
    if not records:
        print("적재할 데이터가 없음")
        return

    conn = sf_connect()
    cur = conn.cursor()

    try:
      
        print(f"적재 시작 ({len(records)}건)")
        for r in records:
            params = {
                "url_hash": r.get("url_hash"),
                "title": r.get("title"),
                "article_date": r.get("date"),
                "url": r.get("url"),
                "summary_ko": r.get("summary_ko"),
                "keywords": json.dumps(r.get("keywords") or [], ensure_ascii=False),
                "main_entity": json.dumps(r.get("main_entity") or [], ensure_ascii=False),
                "evidence": json.dumps(r.get("evidence") or [], ensure_ascii=False),
                "is_verified": bool(r.get("is_verified")) if "is_verified" in r else False,
                "verification_errs": json.dumps(r.get("verification_errs") or [], ensure_ascii=False),
                "processed_at": r.get("processed_at"),
            }
            cur.execute(MERGE_ARTICLE_SQL, params)


        print("모니터링 지표 계산")
        now = datetime.now()
        run_id = date.today().isoformat()
        metric = build_metrics(records)

        cur.execute(
            MERGE_METRIC_SQL,
            {
                "run_id": run_id,
                "run_ts": now.isoformat(timespec="seconds"),
                "metric_date": run_id,
                "metric_json": json.dumps(metric, ensure_ascii=False),
            }
        )

        conn.commit()
        print("Snowflake 적재 완료")

    except Exception as e:
        print(f"에러 발생: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()