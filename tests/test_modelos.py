import pytest
from sqlalchemy import create_engine
import datetime
from sqlalchemy.orm import sessionmaker
from game.modelos.db import Base
from game.jugadores.models import Jugador
from game.partidas.models import Partida
from game.cartas.models import Carta
from settings import settings

# Base de datos en memoria
engine = create_engine(settings.TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    # Crear tablas
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_crear_partida(db):
    partida = Partida(nombre="partida1", nombreDelAnfitrion="Anfi", cantJugadores=1, iniciada=False, maxJugadores=5)
    db.add(partida)
    db.commit()
    db.refresh(partida)
    assert partida.id is not None
    assert partida.nombre == "partida1"

def test_crear_jugador(db):
    nacimiento = datetime.date(2000, 12, 31)
    jugador = Jugador(nombre="jugador1", fecha_nacimiento=nacimiento, partida_id=1)
    db.add(jugador)
    db.commit()
    db.refresh(jugador)
    assert jugador.id is not None
    assert jugador.nombre == "jugador1"

def test_relaciones(db):
    nacimiento2 = datetime.date(2010, 1, 31)
    partida = Partida(nombre="partida2", nombreDelAnfitrion="Anfi2", cantJugadores=1, iniciada=False, maxJugadores=2)
    jugador = Jugador(nombre="jugador2", fecha_nacimiento=nacimiento2, partida=partida)
    carta = Carta(nombre="You're the murderer", tipo="Secreto", jugador=jugador)
    db.add(partida)
    db.add(jugador)
    db.add(carta)
    db.commit()

    assert partida.jugadores[0].nombre == "jugador2"
    assert jugador.cartas[0].nombre == "You're the murderer"