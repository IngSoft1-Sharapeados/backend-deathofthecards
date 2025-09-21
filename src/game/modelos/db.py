from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from settings import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit = False, autoflush=False, bind=engine)

Base = declarative_base()

from game.cartas.models import Carta
from game.jugadores.models import Jugador
from game.partidas.models import Partida

#Dependencia
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
