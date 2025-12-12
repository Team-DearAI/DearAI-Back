import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

# .env 로드
load_dotenv()

# OpenAI 클라이언트 초기화 (환경변수 OPENAI_API_KEY 사용 권장)
client = OpenAI(api_key=os.getenv("GPT_API_KEY"))

# Pydantic 출력 스키마
class ai_result(BaseModel):
    title: str
    mail: str

def call_gpt(text = None, guide = None, recipient: dict=None):
    payload = {
        "language": "Korean",
        "mail": text,
        "guide": guide,
        "recipient": recipient
    }

    # --- 핵심 변경: JSON을 진짜 JSON으로 전달 ---
    # 1) user content에 JSON 문자열을 그대로 넣음 (ensure_ascii=False로 한글 보존)
    # 2) system 프롬프트는 role만 사용 (불필요한 "System:" 접두어 제거)

    system_prompt = (
        "You are a supervisor responsible for managing email communications. "
        "Your goal is to proactively prevent any issues staff may encounter in emails. "
        "Your response should be a structured output: revise and improve both the 'title' and 'mail' fields "
        "in your structured output based on the input's title and mail content. "
        "If 'recipient' field is not None, consider who is the recipient of mail while revising the title and the mail."
        "If there is no 'title' field, create title that best matches."
        "If there is no 'mail' field, create mail content following provided guide."
        "If there is a guide provided in the input, reflect any guidance for revising both the title and the mail based on the guide. "
        "Modify the output language according to the input's specified language. "
        "Review and revise both the email's title and content to ensure there are no inappropriate expressions. "
        "After making revisions, briefly validate that both the email title and content are appropriate and clear, "
        "and proceed or self-correct if validation fails. Respond in the language specified by the input."
    )

    # 모델은 최신 SDK 예시와 호환되는 gpt-4o 계열 권장
    # 참고: SDK README의 Responses API 예시들 (responses.create, input 사용법) :contentReference[oaicite:3]{index=3}
    response = client.responses.parse(
        model="gpt-4o-mini",
        input=[
            {"role": "system", "content": system_prompt},
            # JSON을 유효한 형태(쌍따옴표)로 직렬화해서 전달
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
        ],
        text_format=ai_result,
    )

    return response.output_parsed.dict()