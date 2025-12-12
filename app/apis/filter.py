# filter.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.utils.db import get_db
from app.utils.models import User, Recipient_lists, Inputs, Results
from app.utils.auth import get_current_user
from app.utils.call_gpt import call_gpt
from pydantic import BaseModel
import uuid
from datetime import datetime
from typing import Optional, Any, Dict, List


app = APIRouter()

class FilterKeywordSchema(BaseModel):
    """유저가 제외할 키워드 목록"""
    filter_keywords: List[str] = None


class ExternalRequestSchema(FilterKeywordSchema):
    """프론트엔드에서 넘어오는 실제 페이로드"""
    email: str
    recipient: str = None
    title: str = None
    data: str = None
    guide: str = None

class ExternalResultSchema(BaseModel):
    """외부 API 호출 결과"""
    result: Dict[str, Any]

@app.get("/keywords", response_model=FilterKeywordSchema)
async def get_filter_keywords(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user: User = (
        db.query(User)
        .filter(User.id == current_user.id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=404, detail="User not found"
        )

    return FilterKeywordSchema(
        filter_keywords=user.filter_keyword or []
    )


@app.post("/keywords", response_model=FilterKeywordSchema)
async def add_filter_keywords(payload: FilterKeywordSchema, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user: User = (
        db.query(User)
        .filter(User.id == current_user.id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=404, detail="User not found"
        )

    existing = set(user.filter_keyword or [])
    existing.update(payload.filter_keywords)
    user.filter_keyword = list(existing)
    user.time_modified = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    return FilterKeywordSchema(filter_keywords=user.filter_keyword)

@app.put("/keywords", response_model=FilterKeywordSchema)
async def update_filter_keywords(
    payload: FilterKeywordSchema, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user: User = (
        db.query(User)
        .filter(User.id == current_user.id)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=404, detail="User not found"
        )

    user.filter_keyword = payload.filter_keywords
    user.time_modified = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    return FilterKeywordSchema(filter_keywords=user.filter_keyword)

@app.post("/", response_model=ExternalResultSchema)
async def process_external_request(payload: ExternalRequestSchema, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if payload.email == None and payload.guide == None:
        raise HTTPException(status_code=400, detail="Server received empty request")

    input_id = uuid.uuid4()
    input_row = Inputs(
        id=input_id,
        data=payload,
        time_requested=datetime.utcnow(),
        recipient_email =  payload.email
    )

    recipient = None
    if recipient_data := db.query(Recipient_lists).filter(Recipient_lists.email == payload.recipient_email, Recipient_lists.user_id == current_user.id).first():
        recipient = {
            "name": recipient_data.recipient_name,
            "group": recipient_data.recipient_group
        }
        input_row.recipient_id = recipient_data.id

    # inputs 테이블에 요청 페이로드 저장
    db.add(input_row)
    db.flush()  # input_row가 세션에 반영되도록

    result_row = Results(
        id=uuid.uuid4(),
        data=call_gpt(payload.data, payload.guide, recipient),
        time_returned=datetime.utcnow(),
        input_id=input_row.id,
    )
    
    db.add(result_row)
    db.commit()
    db.refresh(result_row)

    # 4. API 응답으로 외부 API 결과 반환
    return ExternalResultSchema(result=result_row.data)

