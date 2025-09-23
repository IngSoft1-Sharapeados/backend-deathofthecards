import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
#import datetime
from sqlalchemy.orm import sessionmaker
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from game.modelos.db import Base, get_db, get_engine, get_session_local
from settings import settings
from main import app

#from game.jugadores.models import Jugador
#from game.partidas.models import Partida
#from game.cartas.models import Carta

# Base de datos en memoria
@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = get_engine()
    #engine = get_engine(settings.TEST_DATABASE_URL)
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session

@pytest.fixture
def datosPartida_1():
    return {
        "nombre": "partiditaTEST",
        "maxJugadores": 4
    }

@patch('game.partidas.endpoints.PartidaService')
def test_crear_partida_ok(mock_PartidaService, datosPartida_1, session:sessionmaker):

    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_service = MagicMock()
    mock_partida = MagicMock()
    mock_partida.id = 1
    mock_service.crear.return_value = mock_partida
    mock_PartidaService.return_value = mock_service

    response = client.post("/partidas", json=datosPartida_1)

    app.dependency_overrides.clear()
    
    assert response.status_code == 201
    assert response.json() == {"id_partida": 1}

@patch('game.partidas.endpoints.PartidaService')
def test_crear_partida_sin_cant_jugadores(mock_PartidaService, session:sessionmaker):

    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_service = MagicMock()
    mock_PartidaService.return_value = mock_service
    datos_incompletos = {"nombre": "partida sin cantidad"}

    response = client.post("/partidas", json=datos_incompletos)
    
    app.dependency_overrides.clear()

    assert response.status_code == 422
