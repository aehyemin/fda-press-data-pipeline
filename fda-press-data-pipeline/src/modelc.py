import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
# genai 라이브러리를 직접 써서 확인 (제일 빠름)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-2.0-flash-lite')

print("연결 시도 중...")
try:
    # 아주 짧은 단어 하나만 시켜봅니다.
    response = model.generate_content("안녕? 한 글자로 대답해.")
    print(f"응답 성공: {response.text}")
except Exception as e:
    print(f"에러 발생: {e}")