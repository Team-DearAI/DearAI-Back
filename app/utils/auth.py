import requests
from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from app.utils.db import get_db
from app.utils.models import User
import os
from dotenv import load_dotenv
import uuid
import datetime
import jwt  # PyJWT 사용
import logging
from urllib.parse import urlencode

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# 구글 OAuth 환경 변수
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
EXTENSION_ID = os.getenv("EXTENSION_ID")  # ex: abcdefghijklmnopabcdefghijklmnop
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v2/userinfo"
WEB_REDIRECT_URI = "https://dearai.cspark.my/auth/callback"

# JWT 환경 변수
JWT_SECRET = os.getenv("JWT_SECRET")
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30

# -------------------------
# 구글 인증 URL 생성
# -------------------------
def create_google_auth_url(redirect_uri: str):
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = f"{GOOGLE_AUTH_URI}?{urlencode(params)}"
    logger.info(f"Generated Google OAuth URL: {auth_url}")
    return auth_url

# -------------------------
# 구글 토큰 요청
# -------------------------
def get_google_token(code: str, redirect_uri: str):
    logger.info(f"Requesting Google Token with code: {code} and redirect_uri: {redirect_uri}")
    response = requests.post(GOOGLE_TOKEN_URI, data={
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    })
    logger.info(f"Google Token Response Status: {response.status_code}")
    if response.status_code != 200:
        logger.error(f"Failed to get Google token: {response.text}")
        raise HTTPException(status_code=400, detail="Failed to get Google token")
    return response.json()

# -------------------------
# 구글 사용자 정보 요청
# -------------------------
def get_google_userinfo(access_token: str):
    logger.info(f"Requesting Google UserInfo with access_token: {access_token[:10]}...")
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(GOOGLE_USERINFO_URI, headers=headers)
    logger.info(f"Google UserInfo Response Status: {response.status_code}")
    if response.status_code != 200:
        logger.error(f"Failed to get user info: {response.text}")
        raise HTTPException(status_code=400, detail="Failed to get user info")
    return response.json()

# -------------------------
# JWT 생성
# -------------------------
def create_access_token(userinfo: dict):
    expiration = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = userinfo.copy()
    payload["exp"] = expiration
    payload["type"] = "access"
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_refresh_token(userinfo: dict):
    expiration = datetime.datetime.utcnow() + datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = userinfo.copy()
    payload["exp"] = expiration
    payload["type"] = "refresh"
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# -------------------------
# JWT 디코드
# -------------------------
def decode_jwt(token: str):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# -------------------------
# 현재 사용자 가져오기
# -------------------------
def get_current_user(token: str):
    return decode_jwt(token)

# -------------------------
# 로그인 엔드포인트
# -------------------------
def login(request: Request):
    origin = request.headers.get("origin", "")
    logger.info(f"Login request from origin: {origin}")

    # 크롬 확장 프로그램인지 확인
    if origin.startswith(f"chrome-extension://{EXTENSION_ID}"):
        redirect_uri = f"https://{EXTENSION_ID}.chromiumapp.org"
    else:
        redirect_uri = WEB_REDIRECT_URI

    auth_url = create_google_auth_url(redirect_uri)
    logger.info(f"Redirecting to Google OAuth URL: {auth_url}")
    return RedirectResponse(auth_url)

# -------------------------
# 콜백 엔드포인트
# -------------------------
def auth_callback(request: Request, code: str, db: Session = Depends(get_db)):
    origin = request.headers.get("origin", "")
    logger.info(f"Auth callback received with code: {code}, origin: {origin}")

    # origin에 따라 redirect_uri 다시 판단
    if origin.startswith(f"chrome-extension://{EXTENSION_ID}"):
        redirect_uri = f"https://{EXTENSION_ID}.chromiumapp.org"
    else:
        redirect_uri = WEB_REDIRECT_URI

    tokens = get_google_token(code, redirect_uri)
    access_token_google = tokens.get("access_token")
    refresh_token_google = tokens.get("refresh_token")

    if not access_token_google:
        raise HTTPException(status_code=400, detail="Google auth failed")

    userinfo = get_google_userinfo(access_token_google)

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

    access_token = create_access_token({"email": user.email})
    refresh_token = create_refresh_token({"email": user.email})

    user.refresh_token = refresh_token
    db.commit()

    if origin.startswith(f"chrome-extension://{EXTENSION_ID}"):
        redirect_params = urlencode({
            "access_token": access_token,
            "refresh_token": refresh_token
        })
        redirect_url = f"https://{EXTENSION_ID}.chromiumapp.org?{redirect_params}"
        logger.info(f"Redirecting back to extension with tokens: {redirect_url}")
        return RedirectResponse(redirect_url)
    else:
        # 웹 앱이면 JSON 응답으로 내려주거나 웹 전용 페이지로 redirect
        return JSONResponse({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "message": "Login successful"
        })

# -------------------------
# Access token 재발급
# -------------------------
def refresh_access_token(refresh_token: str):
    payload = decode_jwt(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    return create_access_token({"email": payload["email"]})