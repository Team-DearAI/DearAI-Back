from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .models import engine

# DB 세션 관리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
