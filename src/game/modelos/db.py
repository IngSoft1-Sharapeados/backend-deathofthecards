from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from settings import settings


def get_engine():
    return create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})

def get_session_local(engine):
    return sessionmaker(autocommit = False, autoflush=False, bind=engine)

Base = declarative_base()

#Dependencia
def get_db():
    engine = get_engine()
    SessionLocal = get_session_local(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
