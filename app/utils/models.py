from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine, MetaData
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

# .env 파일에서 DATABASE_URL 읽기 (MySQL 접속 정보 반영)
DATABASE_URL = os.getenv("DATABASE_URL")

# 데이터베이스 엔진 생성
engine = create_engine(DATABASE_URL, echo=True)

# Base 클래스 설정
Base = automap_base()

# 메타데이터 설정
metadata = MetaData()
metadata.reflect(engine, only=['user', 'recipient_lists', 'inputs', 'results'])

Base.prepare(engine, reflect=True)

# 자동으로 생성된 클래스
User = Base.classes.users
Recipient_lists = Base.classes.recipient_lists
Inputs = Base.classes.inputs
Results = Base.classes.results