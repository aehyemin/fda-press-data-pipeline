import os, json, time
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

RAW_PATH=os.path.join("data", "raw", "raw_articles.jsonl")
OUT_PATH=os.path.join("data", "curate", "processed_articles.jsonl")



def read_jsonl(path:str) -> list[dict]:
    items: list[dict] = []
    
    with open(RAW_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            items.append(data)


def build_llm() -> ChatGoogleGenerativeAI:
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("키가없음")
    
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
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
     "2) keywords: 핵심 키워드(한글/영어 둘다 가능)\n"
     "3) main_entity: 기사에서 중요한 주체 1~4개(회사/기업/인물 등)\n"
     "4) evidence: summary_ko의 근거가 되는 문장 1~3(영문으로)\n"
     "5)출력은 반드시 json하나만 예:\n"
     "{\n"
    '   "summary_ko": "...",\n'
    '   "keywords": ["..."],\n'
    '   "main_entity": ["..."],\n'
    '   "evidence": ["..."]\n'
     "}\n"
     )
])



# def extract_with_llm(llm: ChatGoogleGenerativeAI, body_en: str) -> Dict[str, Any]:
#     """
#     body_en(영문 본문) -> LLM 결과(JSON) 파싱
#     """
#     msg = PROMPT.format_messages(body_en=body_en)
#     resp = llm.invoke(msg)

#     # 모델 응답 텍스트
#     text = resp.content.strip()

#     # 가끔 ```json ... ``` 형태로 오는 경우가 있어 제거
#     if text.startswith("```"):
#         text = text.strip("`")
#         # "json\n{...}" 형태일 수 있어 첫 줄 제거
#         if "\n" in text:
#             text = text.split("\n", 1)[1].strip()

#     # JSON 파싱
#     return json.loads(text)


# # =========================
# # 메인 실행
# # =========================
# def main():
#     # 출력 파일이 이미 있으면 오늘은 덮어쓰지 말고 새로 만들지(원하면 변경 가능)
#     # 여기서는 "새로 생성"을 기본으로 하겠습니다.
#     if os.path.exists(OUT_PATH):
#         os.remove(OUT_PATH)

#     os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)

#     articles = read_jsonl(RAW_PATH)
#     print(f"[*] 입력 로드 완료: {len(articles)}건")

#     llm = build_llm()

#     for i, a in enumerate(articles, 1):
        # body_en = (a.get("body_en") or "").strip()

        # # ✅ 줄바꿈/공백 정리 (LLM 투입 전)
        # body_en = body_en.replace("\n", " ")
        # body_en = " ".join(body_en.split())
#         if not body_en:
#             print(f"[{i}/{len(articles)}] SKIP: 본문 없음 - {a.get('title', '')[:40]}")
#             continue

#         try:
#             extracted = extract_with_llm(llm, body_en)

#             out = {
#                 # 원본 메타
#                 "url_hash": a.get("url_hash"),
#                 "title": a.get("title"),
#                 "date": a.get("date"),
#                 "published_at": a.get("published_at"),
#                 "url": a.get("url"),
#                 "source": a.get("source", "fda_press"),
#                 "fetched_at": a.get("fetched_at"),

#                 # LLM 가공 결과
#                 "summary_ko": extracted.get("summary_ko"),
#                 "keywords": extracted.get("keywords", []),
#                 "main_entities": extracted.get("main_entities", []),
#                 "evidence_sentences": extracted.get("evidence_sentences", []),

#                 # 운영 메타
#                 "processed_at": datetime.now().isoformat(timespec="seconds"),
#             }

#             append_jsonl(OUT_PATH, out)
#             print(f"[{i}/{len(articles)}] OK: {a.get('title','')[:40]}")

#         except Exception as e:
#             # 실패해도 다음 기사로 넘어가게(운영 관점)
#             err = {
#                 "url_hash": a.get("url_hash"),
#                 "title": a.get("title"),
#                 "url": a.get("url"),
#                 "error": str(e),
#                 "processed_at": datetime.now().isoformat(timespec="seconds"),
#             }
#             append_jsonl(OUT_PATH, err)
#             print(f"[{i}/{len(articles)}] FAIL: {a.get('title','')[:40]} - {e}")

#         time.sleep(SLEEP_SECONDS)

#     print(f"[!] 완료: {OUT_PATH} 저장됨")


# if __name__ == "__main__":
#     main()