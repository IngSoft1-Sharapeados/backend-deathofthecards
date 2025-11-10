import pytest
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from game.modelos.db import Base, get_db, get_session_local
from main import app
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch, AsyncMock
from game.partidas.utils import *
from game.partidas.models import Partida
from game.jugadores.models import Jugador
from game.cartas.models import Carta

# ---------- FIXTURE DE DB ----------
@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session

@pytest.fixture(name="partida1")
def partida1_fixture():
    partida = Partida(
        id=1, 
        nombre="Partida 1", 
        anfitrionId=1, 
        cantJugadores=4, 
        iniciada=True,
        minJugadores=4,
        maxJugadores=6,
        turno_id=5,
        accion_en_progreso= {
        "tipo_accion": "evento_another_victim",
        "cartas_originales_db_ids": [90], # Confiamos en esta lista
        "id_jugador_original": 2,
        "nombre_accion": "Another Victim",
        "payload_original": {"id_objetivo":3,"id_representacion_carta":18,"ids_cartas":[8,9]},
        "pila_respuestas": [{
            "id_jugador": 6,
            "id_carta_db": 90,
            "id_carta_tipo": 85,
            "nombre": "Not So Fast"
        }],    
        "id_carta_tipo_original": 22,
        }
    )
    return partida


@pytest.fixture(name="jugador1")
def jugador1_fixture():
    jugador1 = Jugador(
    id=5, 
    nombre="J1", 
    partida_id=1, 
    fecha_nacimiento=date(1990, 1, 1),
    desgracia_social=False
    )
    return jugador1


@pytest.fixture(name="carta_nsf")
def cartaNSF_fixture():
    carta_nsf = Carta(
    id=101, 
    partida_id=1, 
    jugador_id=5, 
    id_carta=16, 
    nombre="Not So Fast",
    tipo="respuesta", 
    ubicacion="mano",
    bocaArriba=True
    )
    return carta_nsf

# Mock para base de datos
@pytest.fixture(name="mock_db")
def mock_db():
    return MagicMock()

@pytest.fixture(name="partida_iniciada")
def mock_partida():
    mock = MagicMock()
    mock.id = 1
    mock.nombre = "PartidaChat"
    mock.anfitrionId = 1
    mock.cantJugadores = 2    
    mock.iniciada = True
    return mock


@pytest.fixture(name="jugadorChat")
def mock_jugadorChat():
    # Mock de un objeto Partida con los atributos necesarios
    mock = MagicMock()
    mock.id = 1
    mock.nombre = "Fran"
    mock.partida_id = 1
    mock.fechaNacimiento = date(1990, 3, 3)    
    mock.desgracia_social = False
    return mock


@pytest.fixture(name="mensaje")
def mock_mensaje():
    return Mensaje(nombreJugador="Fran", texto="hola como andas")