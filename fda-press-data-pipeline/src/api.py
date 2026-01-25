from fastapi import FastAPI, HTTPException
import snowflake.connector
import os, json
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FDA Press Monitoring API")

def get_db_conn():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE"),
        database=os.getenv("SNOWFLAKE_DATABASE"),
        schema=os.getenv("SNOWFLAKE_SCHEMA")
    )

@app.get("/")
def root():
    return {"message": "FDA 모니터링 API 서버 가동"}

@app.get("/api/v1/fda/metrics")
def get_metrics():
    """최신 지표 가져오기"""
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        #가장 최근에 생성된 지표 1건
        query = "SELECT metric_json FROM MONITOR_METRIC_DAILY ORDER BY run_ts DESC LIMIT 1"
        cur.execute(query)
        result = cur.fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="지표 데이터가 없습니다.")
            
        metric_data = json.loads(result[0])
        return metric_data
    finally:
        cur.close()
        conn.close()

@app.get("/api/v1/fda/latest")
def get_latest_articles(limit: int = 10):
    """최근 수집된 기사 목록 조회"""
    conn = get_db_conn()
    cur = conn.cursor()
    try:
        query = f"""
            SELECT title, article_date, url, summary_ko 
            FROM FDA_ARTICLES 
            ORDER BY article_date DESC 
            LIMIT {limit}
        """
        cur.execute(query)
        rows = cur.fetchall()
        
        articles = []
        for r in rows:
            articles.append({
                "title": r[0],
                "date": str(r[1]),
                "url": r[2],
                "summary": r[3]
            })
        return {"count": len(articles), "data": articles}
    finally:
        cur.close()
        conn.close()