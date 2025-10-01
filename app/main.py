from fastapi import FastAPI
from app.utils.auth import login, auth_callback
from app.apis.contacts import app as contact_router
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

EXTENSION_ID=os.getenv("EXTENSION_ID")

app = FastAPI()

# 크롬 익스텐션의 ID를 아래처럼 실제 확장ID로 지정합니다.
origins = [
    "https://dearai.cspark.my",
    f"chrome-extension://{EXTENSION_ID}"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 연결
app.add_api_route("/login", login, methods=["GET"])
app.add_api_route("/auth/callback", auth_callback, methods=["GET"])
app.include_router(contact_router, prefix="/contacts", tags=["contact"])