import os, json, time
from datetime import datetime
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate


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