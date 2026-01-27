import os, json, time
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_PATH = os.path.join(BASE_DIR, "data", "raw", "raw_articles.jsonl")
OUT_PATH = os.path.join(BASE_DIR, "data", "curated", "processed_articles.jsonl")
SLEEP_SECONDS = 5

def error_429(e:Exception) -> bool:
    s = str(e)
    if "429" in s:
        return True
    return False


def read_jsonl(path:str) -> list[dict]:
    items: list[dict] = []
    
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            items.append(data)
    return items

def append_jsonl(path:str, obj:dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def build_llm() -> ChatGoogleGenerativeAI:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("키가없음")
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        temperature=0.2,
        google_api_key=api_key)
    return llm



PROMPT = ChatPromptTemplate.from_messages([
    ("system", "너는 fda의 보도 자료를 읽고 핵심을 뽑아주는 분석가야."
        "반드시 json 형식으로만 답변해"
    ),
    
    ("user", 
     "다음은 fda 보도자료 본문이야. \n"
     "[본문 시작]\n{body_en}\n[본문 끝]\n"
     "아래 규칙을 준수해서 json으로 만들어.\n"
     "1) summary_ko: 한국어로 1~3문장 요약\n"
     "2) keywords: keywords는 명사/명사구로만, 1~5개, 중복/동의어 최소화(한글/영어 둘다 가능)\n"
     "3) main_entity: 기사에서 중요한 주체 1~5개(회사/기업/인물 등)\n"
     "4) evidence: summary_ko의 근거가 되는 문장 1~3개(영문으로)\n"
     "5)출력은 반드시 json하나만\n"
     "6) JSON 외 텍스트 출력 금지\n"
     "7)코드블록(```) 사용 금지\n"
     "8)중복 키 금지\n"
     "{{\n"
    '   "summary_ko": "...",\n'
    '   "keywords": ["..."],\n'
    '   "main_entity": ["..."],\n'
    '   "evidence": ["..."]\n'
     "}}\n"
     )
])

#llm에게 보내고 json으로 결과 받아오기
def extract_json_llm(llm: ChatGoogleGenerativeAI, body_en: str, max_retries: int = 5) -> dict:
    msg = PROMPT.format_messages(body_en=body_en)
    backoffs = [2, 4, 8, 16, 30]
    
    for t in range(max_retries+1):
        try:
            response = llm.invoke(msg)
            text = str(response.content).strip()

            if not text:
                raise ValueError("LLM returned empty content")


            if text.startswith("```"):
                lines = text.splitlines()

                if lines and lines[-1].strip().startswith("```"):
                    lines = lines[:-1]
                if lines and lines[0].strip().startswith("```"):
                    lines = lines[1:]
                text = "\n".join(lines).strip()

            l = text.find("{")
            r = text.rfind("}")
            if l == -1 or r == -1 or r < l:
                raise ValueError(f"JSON block not found. raw={text[:200]}")
            text = text[l:r+1]

            return json.loads(text)
        
        except Exception as e:
            last_err = e
            if not error_429(e):
                raise
            
            if t >= max_retries:
                raise
            
            delay = backoffs[min(t, len(backoffs) - 1)]
            print(f"[429] - {delay}s 후 재시도 ({t+1}/{max_retries})")
            time.sleep(delay)



def main():
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    
    processed_hash = set()
    if os.path.exists(OUT_PATH):
        with open(OUT_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    if "url_hash" in data and "error" not in data:
                        processed_hash.add(data["url_hash"])
                except:
                     continue
    
    print(f"이미 처리된 기사: {len(processed_hash)}건 스킵 준비 완료")
    all_articles = read_jsonl(RAW_PATH)
    target_articles = [a for a in all_articles if a.get("url_hash") not in processed_hash]
    
    if not target_articles:
        print("새로 가공할 기사가 없음")
        return
    llm = build_llm()
    for i, a in enumerate(target_articles,1):
        print(f"{i}번째 기사 시작")
        body_en = (a.get("body_en") or "").strip()
        body_en = body_en.replace("\n", " ")
        body_en = " ".join(body_en.split())
        
        if not body_en:
            print("본문없음")
            continue
        
        try:
            extracted = extract_json_llm(llm, body_en)
            output = {
                "url_hash": a.get("url_hash"),
                "title": a.get("title"),
                "date": a.get("date"),
                "url": a.get("url"),
                
                "summary_ko": extracted.get("summary_ko"),
                "keywords": extracted.get("keywords", []),
                "main_entity": extracted.get("main_entity", []),
                "evidence": extracted.get("evidence", []),
                
                "processed_at": datetime.now().isoformat(timespec="seconds"),
            }
            append_jsonl(OUT_PATH, output)
          
        except Exception as e:
            err = {
                "url_hash": a.get("url_hash"),
                "title": a.get("title"),
                "date": a.get("date"),
                "url": a.get("url"),
                
                "error": str(e),
                "processed_at": datetime.now().isoformat(timespec="seconds"),
            }
            append_jsonl(OUT_PATH, err)
            
        print(f"{i}번째 기사 LLM 응답 완료")
        time.sleep(SLEEP_SECONDS)
        

    print(f"완료: {OUT_PATH} 저장됨")

if __name__ == "__main__":
    main()
