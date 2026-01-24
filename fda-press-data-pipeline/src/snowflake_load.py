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

GET_METRIC_JSON_SQL = """
WITH base AS (
    SELECT 
        COUNT(*) as total,
        SUM(IFF(is_verified, 1, 0)) as verified_ok,
        SUM(IFF(NOT is_verified, 1, 0)) as verified_fail
    FROM FDA_DB.PUBLIC.FDA_ARTICLES
    WHERE article_date >= DATEADD('day', -30, CURRENT_DATE())
),
errors AS (
  SELECT
    SPLIT_PART(f.value::string, ':', 1) AS err_type,
    COUNT(*) AS cnt
  FROM FDA_DB.PUBLIC.FDA_ARTICLES a,
  LATERAL FLATTEN(input => COALESCE(a.verification_errs, PARSE_JSON('[]'))) f
  WHERE a.article_date >= DATEADD('day', -30, CURRENT_DATE())
  GROUP BY 1
  ORDER BY 2 DESC
  LIMIT 5
),
errors_arr AS (
  SELECT
    COALESCE(
      ARRAY_AGG(OBJECT_CONSTRUCT('type', err_type, 'count', cnt)),
      PARSE_JSON('[]')
    ) AS top_errors
  FROM errors
)
SELECT
    OBJECT_CONSTRUCT(
        'window_days', 30,
        'total', (SELECT total FROM base),
        'verified_ok', (SELECT verified_ok FROM base),
        'verified_fail', (SELECT verified_fail FROM base),
        'fail_rate', IFF((SELECT total FROM base)=0, 0, (SELECT verified_fail FROM base)/(SELECT total FROM base)),
        'top_errors', (SELECT top_errors FROM errors_arr)
  ) AS metric_json;
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
            
        print("snowflake 테이블기반 지표 생성")
        cur.execute(GET_METRIC_JSON_SQL)
        cal_metric_obj = cur.fetchone()[0]
        
        
        now = datetime.now()
        run_id = date.today().isoformat()
        
        cur.execute(
            MERGE_METRIC_SQL,
            {
                "run_id": run_id,
                "run_ts": now.isoformat(timespec="seconds"),
                "metric_date": run_id,
                "metric_json": cal_metric_obj,
            }
        )
        conn.commit()
        print("적재 및 지표 업데이트 완료")
    except Exception as e:
        print(f"에러발생:{e}")
    finally:
        cur.close()
        conn.close()




if __name__ == "__main__":
    main()