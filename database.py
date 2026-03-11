from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker                                                                 
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./ec_manager.db"                                                                   
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class JobLog(Base):
    __tablename__ = "job_logs"
    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String)
    status = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.now)


class ProcessedOrder(Base):
    __tablename__ = "processed_orders"
    id = Column(Integer, primary_key=True)
    order_id = Column(String, index=True)
    action = Column(String)
    note = Column(Text)
    processed_at = Column(DateTime, default=datetime.now)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()