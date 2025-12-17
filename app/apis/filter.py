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

from app.tasks.filter import process_external_request_task

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
    option: str
    language: str

class ExternalResultSchema(BaseModel):
    """외부 API 호출 결과"""
    result: Dict[str, Any]

class JobCreateResponse(BaseModel):
    job_id: str
    task_id: str

class JobPollResponse(BaseModel):
    status: str  # PENDING | SUCCESS | FAILURE
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.get("/keywords", response_model=FilterKeywordSchema)
async def get_filter_keywords(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user: User = (
        db.query(User)
        .filter(User.id == current_user)
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
        .filter(User.id == current_user)
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
        .filter(User.id == current_user)
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
        input_data=payload.dict(),
        time_requested=datetime.utcnow(),
        recipient_email =  payload.email
    )

    recipient = None
    if payload.recipient:
        if recipient_data := db.query(Recipient_lists).filter(
            Recipient_lists.email == payload.recipient,
            Recipient_lists.user_id == current_user,
        ).first():
            recipient = {
                "name": recipient_data.recipient_name,
                "group": recipient_data.recipient_group,
            }
            input_row.recipient_id = recipient_data.id

    # inputs 테이블에 요청 페이로드 저장
    db.add(input_row)
    db.flush()  # input_row가 세션에 반영되도록

    result_row = Results(
        id=uuid.uuid4(),
        result_data=call_gpt(payload.data, payload.guide, recipient),
        time_returned=datetime.utcnow(),
        input_id=input_row.id,
    )
    
    db.add(result_row)
    db.commit()
    db.refresh(result_row)

    # 4. API 응답으로 외부 API 결과 반환
    return ExternalResultSchema(result=result_row.result_data)

@app.post("/job", response_model=JobCreateResponse)
async def enqueue_job(
    payload: ExternalRequestSchema,
    db: Session = Depends(get_db),
    current_user_id = Depends(get_current_user), 
):
    if payload.email is None and payload.guide is None:
        raise HTTPException(status_code=400, detail="Server received empty request")

    input_id = uuid.uuid4()

    input_row = Inputs(
        id=input_id,
        input_data=payload.dict(),
        time_requested=datetime.utcnow(),
        recipient_email=payload.email,
    )

    # recipient 매핑(기존 로직 유지)
    if payload.recipient:
        recipient_data = (
            db.query(Recipient_lists)
            .filter(
                Recipient_lists.email == payload.recipient,
                Recipient_lists.user_id == current_user_id,
            )
            .first()
        )
        if recipient_data:
            input_row.recipient_id = recipient_data.id

    db.add(input_row)
    db.commit()
    db.refresh(input_row)

    # Celery task enqueue
    async_result = process_external_request_task.delay(str(input_id), str(current_user_id), db)

    return JobCreateResponse(job_id=str(input_id), task_id=async_result.id)

@app.get("/job/{job_id}", response_model=JobPollResponse)
async def poll_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user_id = Depends(get_current_user),
):
    result_row = (
        db.query(Results)
        .filter(Results.input_id == job_id)
        .first()
    )

    if result_row:
        return JobPollResponse(status="SUCCESS", result=result_row.result_data)

    input_exists = (
        db.query(Inputs)
        .filter(Inputs.id == job_id)
        .first()
    )
    if not input_exists:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobPollResponse(status="PENDING")