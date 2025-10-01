from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.utils.db import get_db
from app.utils.models import User, Recipient_lists, Inputs, Results
from app.utils.auth import get_current_user
from pydantic import BaseModel, EmailStr
from typing import Optional, Any, Dict
from datetime import datetime
import logging

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# 주소록 (Recipient_lists)
# -------------------------
class ContactBase(BaseModel):
    name: str
    email: EmailStr
    group: Optional[str] = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    group: Optional[str] = None


class ContactResponse(ContactBase):
    id: str
    time_modified: datetime

    class Config:
        orm_mode = True


# -------------------------
# 입력 내역 (Inputs)
# -------------------------
class InputBase(BaseModel):
    recipient_id: str
    data: Dict[str, Any]


class InputCreate(InputBase):
    pass


class InputResponse(InputBase):
    id: str
    time_requested: datetime

    class Config:
        orm_mode = True


# -------------------------
# 결과 (Results)
# -------------------------
class ResultResponse(BaseModel):
    id: str
    input_id: str
    data: Dict[str, Any]
    time_returned: datetime

    class Config:
        orm_mode = True


app = APIRouter()

# -------------------------
# 주소록 API
# -------------------------
@app.get("/")
def get_contacts(db: Session = Depends(get_db), user_id: str = Depends(get_current_user)):
    # 받은 user_id를 사용하여 recipient_lists를 조회
    contacts = db.query(Recipient_lists).filter(Recipient_lists.user_id == user_id).all()

    if not contacts:
        raise HTTPException(status_code=404, detail="No contacts found for this user")

    return contacts  # FastAPI가 자동으로 SQLAlchemy 객체를 직렬화하여 JSON으로 반환


@app.post("/", response_model=ContactResponse)
def create_contact(contact: ContactCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    new_contact = Recipient_lists(user_id=user.id, **contact.dict())
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact


@app.patch("/{contact_id}", response_model=ContactResponse)
def update_contact(contact_id: str, update: ContactUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    contact = db.query(Recipient_lists).filter(Recipient_lists.id == contact_id, Recipient_lists.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    for k, v in update.dict(exclude_unset=True).items():
        setattr(contact, k, v)
    db.commit()
    db.refresh(contact)
    return contact


@app.delete("/{contact_id}")
def delete_contact(contact_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    contact = db.query(Recipient_lists).filter(Recipient_lists.id == contact_id, Recipient_lists.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"message": "deleted"}


# -------------------------
# 입력 내역 API
# -------------------------
@app.post("/inputs", response_model=InputResponse)
def create_input(data: InputCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    new_input = Inputs(**data.dict())
    db.add(new_input)
    db.commit()
    db.refresh(new_input)
    return new_input


@app.get("/inputs", response_model=list[InputResponse])
def list_inputs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Inputs).join(Recipient_lists).filter(Recipient_lists.user_id == user.id).all()


# -------------------------
# 결과 API
# -------------------------
@app.get("/results/{input_id}", response_model=ResultResponse)
def get_result(input_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    result = db.query(Results).join(Inputs).join(Recipient_lists).filter(
        Results.input_id == input_id,
        Recipient_lists.user_id == user.id
    ).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result