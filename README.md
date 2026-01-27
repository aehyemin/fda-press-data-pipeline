## LLM기반 FDA 보도자료 자동화 파이프라인
LangChain을 활용한 외부 데이터 수집 · 정형화 · 검증 · 운영 프로젝트

---

### 1. 프로젝트 개요

본 프로젝트는 FDA 보도자료를 자동 수집하고,  
LLM(LangChain + Gemini API)을 활용해 비정형 텍스트를 정형 데이터로 가공한 뒤,  
AI 환각을 검증 로직으로 제어하여 **운영 가능한 데이터 파이프라인**으로 구축한 프로젝트입니다.

단순한 크롤링이나 요약이 아니라,  
**AI가 생성한 데이터를 실제 비즈니스 환경에서 신뢰하고 사용할 수 있도록 설계**하는 것을 목표로 했습니다.

---

### 2. 문제 정의

- FDA 보도자료는 대부분 비정형 텍스트 형태
- 그대로는 검색·분석·의사결정에 활용하기 어려움
- LLM을 활용하면 정보 추출은 쉬워지지만  
  → 환각으로 인한 데이터 신뢰성 문제 발생

핵심 질문:
> LLM을 사용하면서도, 데이터 품질과 신뢰성을 어떻게 운영 수준에서 보장할 수 있을까?

---

### 3. 해결 전략

본 프로젝트는 다음 4단계 파이프라인으로 구성됩니다.

---

### 3-1. 데이터 수집

- Selenium 기반 FDA 보도자료 수집
- 과도한 요청으로 인한 차단을 방지하기 위해:
  - 랜덤 딜레이
  - 재시도 로직 적용
- 수집 대상:
  - 기사 메타데이터
  - 영문 본문 텍스트
- 결과물: `raw_articles.jsonl`

---

### 3-2. LLM 기반 데이터 가공 
- LangChain을 사용해 LLM 호출 구조화
- 영문 본문을 입력으로 받아 다음 정보를 JSON 형태로 추출:
  - 한국어 요약 (`summary_ko`)
  - 핵심 키워드 (`keywords`)
  - 주요 엔티티 (`main_entities`)
  - 요약 근거 문장 (`evidence_sentences`)

LLM을 자유 생성이 아닌 **구조적 추출 도구**로 활용했습니다.

---

### 3-3. 데이터 검증

- LLM 결과에 대해 규칙 기반 검증 로직 적용
  - Evidence 문장이 실제 원문에 존재하는지 대조
  - 요약 최소 길이 검증
  - 필수 필드 누락 여부 확인
- 검증 결과를 운영 지표로 활용 가능하도록 설계

---

### 3-4. 데이터 적재 및 서빙 

- 검증된 데이터를 Snowflake에 적재
- FastAPI 기반 API 제공
  - 최신 FDA 보도자료 요약 조회
  - 특정 기사 상세 정보 및 근거 문장 확인
- 데이터 품질과 수집 상태를 운영 관점에서 확인 가능

---
```
fda-press-data-pipeline/
├─ src/
│  ├─ fda_press_collect.py   # Selenium 기반 데이터 수집 (Raw)
│  ├─ fda_process.py         # LangChain/LLM 기반 정보 추출
│  ├─ fda_validate.py        # 규칙 기반 환각 검증 로직
│  ├─ snowflake_load.py      # Snowflake 데이터 적재
│  ├─ pipeline.py            #자동 적재 파이프라인
│  └─ api.py                 # FastAPI 서빙 및 모니터링
│
└─ data/
  ├─ curated/
  │  ├─ processed_articles.jsonl  # LLM을 통해 1차 가공(추출)된 데이터
  │  └─ verified_articles.jsonl   # 검증 로직을 통과하여 신뢰성이 확보된 최종 데이터
  └─ raw/
     └─ raw_articles.jsonl        # 수집 직후의 영문 원본 데이터
```
### 4. api 서버
검증된 고품질 데이터를 Snowflake에 적재하고, FastAPI를 통해 실시간 데이터 서빙 체계를 구현했습니다.
최신 지표
<img width="998" height="814" alt="스크린샷 2026-01-27 185549" src="https://github.com/user-attachments/assets/c838d67f-2d4b-4c00-9c5a-edbddbeeae3f" />

최근에 수집된 기사 10개
<img width="970" height="585" alt="스크린샷 2026-01-27 185715" src="https://github.com/user-attachments/assets/65747160-0ffa-4b11-b221-c0d2174ec4b4" />

