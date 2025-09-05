import requests
from fastapi import Depends, HTTPException
from jose import jwt
from app.utils.db import get_db
from app.utils.models import User
from sqlalchemy.orm import Session
from starlette.responses import RedirectResponse
import os
from dotenv import load_dotenv
import uuid
import datetime

load_dotenv()

# 구글 API 관련 환경 변수
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
JWT_SECRET = os.getenv("JWT_SECRET")

# 구글 인증 URL 생성
def create_google_auth_url():
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent"
    }
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{GOOGLE_AUTH_URI}?{query}"

# 구글 토큰 요청
def get_google_token(code: str):
    response = requests.post(GOOGLE_TOKEN_URI, data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code"
    })
    return response.json()

# 구글 사용자 정보 요청
def get_google_userinfo(access_token: str):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(GOOGLE_USERINFO_URI, headers=headers)
    return response.json()

# JWT 생성
def create_jwt(userinfo: dict):
    return jwt.encode(userinfo, JWT_SECRET, algorithm="HS256")

# JWT 디코드
def decode_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# 현재 사용자 가져오기
def get_current_user(token: str):
    user = decode_jwt(token)
    return user

# 로그인 엔드포인트
def login():
    return RedirectResponse(create_google_auth_url())

# 콜백 엔드포인트
def auth_callback(code: str, db: Session = Depends(get_db)):
    tokens = get_google_token(code)
    access_token = tokens.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google auth failed")
    
    userinfo = get_google_userinfo(access_token)

    # DB에서 사용자 찾기
    user = db.query(User).filter(User.email == userinfo["email"]).first()
    if not user:
        user = User(
            id=str(uuid.uuid4()),
            email=userinfo["email"],
            filter_keyword=None,
            time_created=datetime.datetime.now(),
            time_modified=datetime.datetime.now()
        )
        db.add(user)
        db.commit()

    jwt_token = create_jwt({
        "email": user.email
    })

    return {"access_token": jwt_token}
