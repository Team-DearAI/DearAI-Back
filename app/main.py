from fastapi import FastAPI, Depends
from app.utils.auth import login, auth_callback
from app.utils.db import get_db
from app.utils.models import User

app = FastAPI()

# 라우터 연결
app.add_api_route("/login", login, methods=["GET"])
app.add_api_route("/auth/callback", auth_callback, methods=["GET"])
