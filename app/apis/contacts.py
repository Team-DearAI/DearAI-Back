from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.utils.db import get_db
from app.utils.models import User, Recipient_lists, Inputs, Results
from app.utils.auth import get_current_user
from pydantic import BaseModel, EmailStr
from typing import Optional
import uuid

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


# -------------------------
# 입력 내역 (Inputs)
# -------------------------
class InputBase(BaseModel):
    recipient_id: str
    data: dict


class InputCreate(InputBase):
    pass


app = APIRouter()

# -------------------------
# 주소록 API
# -------------------------
@app.get("/")
def get_contacts(db: Session = Depends(get_db), user_id: User = Depends(get_current_user)):
    contacts = db.query(Recipient_lists).filter(Recipient_lists.user_id == user_id).all()
    if not contacts:
        raise HTTPException(status_code=404, detail="No contacts found for this user")
    return contacts

@app.get("/groups")
def get_groups(db: Session = Depends(get_db), user_id: str = Depends(get_current_user)):
    groups = (
        db.query(Recipient_lists.recipient_group)
        .filter(Recipient_lists.user_id == user_id, Recipient_lists.recipient_group.isnot(None))
        .distinct()
        .all()
    )
    group_list = [g[0] for g in groups if g[0]]
    return {"groups": group_list}


@app.post("/")
def create_contact(contact: ContactCreate, db: Session = Depends(get_db), user_id: str = Depends(get_current_user)):
    new_contact = Recipient_lists(
        id=str(uuid.uuid4()),
        user_id=user_id,
        email=contact.email,
        recipient_name=contact.name,        # name → recipient_name
        recipient_group=contact.group       # group → recipient_group
    )
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact

@app.patch("/{contact_id}")
def update_contact(contact_id: str, update: ContactUpdate, db: Session = Depends(get_db), user_id: str = Depends(get_current_user)):
    contact = db.query(Recipient_lists).filter(
        Recipient_lists.id == contact_id, Recipient_lists.user_id == user_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")

    update_data = update.dict(exclude_unset=True)
    if "name" in update_data:
        setattr(contact, "recipient_name", update_data.pop("name"))
    if "email" in update_data:
        setattr(contact, "email", update_data.pop("email"))
    if "group" in update_data:
        setattr(contact, "recipient_group", update_data.pop("group"))

    db.commit()
    db.refresh(contact)
    return contact


@app.delete("/{contact_id}")
def delete_contact(contact_id: str, db: Session = Depends(get_db), user_id: User = Depends(get_current_user)):
    contact = db.query(Recipient_lists).filter(
        Recipient_lists.id == contact_id, Recipient_lists.user_id == user_id
    ).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    db.delete(contact)
    db.commit()
    return {"message": "deleted"}


# -------------------------
# 입력 내역 API
# -------------------------
@app.post("/inputs")
def create_input(data: InputCreate, db: Session = Depends(get_db), user_id: User = Depends(get_current_user)):
    recipient = db.query(Recipient_lists).filter(
        Recipient_lists.id == data.recipient_id, Recipient_lists.user_id == user_id
    ).first()
    if not recipient:
        raise HTTPException(status_code=403, detail="Recipient not found or not yours")

    new_input = Inputs(**data.dict())
    db.add(new_input)
    db.commit()
    db.refresh(new_input)
    return new_input


@app.get("/inputs")
def list_inputs(db: Session = Depends(get_db), user_id: User = Depends(get_current_user)):
    return db.query(Inputs).join(Recipient_lists).filter(Recipient_lists.user_id == user_id).all()


# -------------------------
# 결과 API
# -------------------------
@app.get("/results/{input_id}")
def get_result(input_id: str, db: Session = Depends(get_db), user_id: User = Depends(get_current_user)):
    result = (
        db.query(Results)
        .join(Inputs, Results.input_id == Inputs.id)
        .join(Recipient_lists, Inputs.recipient_id == Recipient_lists.id)
        .filter(Results.input_id == input_id, Recipient_lists.user_id == user_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    return result
