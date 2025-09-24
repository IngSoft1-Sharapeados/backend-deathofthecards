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
from game.partidas.models import Partida

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

@pytest.fixture
def partidas_mock():
    p1 = MagicMock()
    p1.id = 1
    p1.nombre = "PartidaUno"
    p1.iniciada = False
    p1.maxJugadores = 4

    p2 = MagicMock()
    p2.id = 2
    p2.nombre = "PartidaDos"
    p2.iniciada = True
    p2.maxJugadores = 5

    return [p1, p2]


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

# --------------------- TEST OBTENER DATOS PARTIDA OK ---------------------
@patch('game.partidas.endpoints.PartidaService')
def test_obtener_datos_partida_ok(mock_PartidaService, datosPartida_1, session: sessionmaker):

    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_service = MagicMock()
    mock_partida = MagicMock()
    mock_partida.id = 1
    mock_partida.nombre = datosPartida_1["nombre"]
    mock_partida.iniciada = False
    mock_partida.maxJugadores = datosPartida_1["maxJugadores"]
    mock_service.obtener_por_id.return_value = mock_partida
    mock_PartidaService.return_value = mock_service

    response = client.get("/partidas/1")

    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    assert response.json() == {
        "nombre_partida": datosPartida_1["nombre"],
        "iniciada": False,
        "maxJugadores": datosPartida_1["maxJugadores"]
    }

# --------------------- TEST OBTENER DATOS PARTIDA NO ENCONTRADA ---------------------
@patch('game.partidas.endpoints.PartidaService')
def test_obtener_datos_partida_no_encontrada(mock_PartidaService, session: sessionmaker):

    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_service = MagicMock()
    mock_service.obtener_por_id.return_value = None
    mock_PartidaService.return_value = mock_service

    response = client.get("/partidas/999")  # ID que no existe

    app.dependency_overrides.clear()
    
    assert response.status_code == 404
    assert response.json() == {"detail": "No se encontró la partida con ID 999"}


# ---------- TEST LISTAR PARTIDAS OK ----------

@patch("game.partidas.endpoints.PartidaService")
def test_listar_partidas_ok(mock_PartidaService, partidas_mock, session: sessionmaker):
    # Override de la dependencia get_db
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock del servicio
    mock_service = MagicMock()
    mock_service.listar.return_value = partidas_mock
    mock_PartidaService.return_value = mock_service

    # Llamada al endpoint
    response = client.get("/partidas")

    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "nombre": "PartidaUno",
            "iniciada": False,
            "maxJugadores": 4,
        },
        {
            "id": 2,
            "nombre": "PartidaDos",
            "iniciada": True,
            "maxJugadores": 5,
        },
    ]



# ---------- TEST LISTAR PARTIDAS VACÍAS ----------
@patch('game.partidas.endpoints.PartidaService')
def test_listar_partidas_vacio(mock_PartidaService, session: sessionmaker):
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mockear servicio que devuelve lista vacía
    mock_service = MagicMock()
    mock_service.listar.return_value = []
    mock_PartidaService.return_value = mock_service

    response = client.get("/partidas")

    app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "No hay partidas disponibles"}
