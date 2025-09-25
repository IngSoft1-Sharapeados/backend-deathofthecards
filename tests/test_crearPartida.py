# tests/test_crearPartida.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from datetime import date
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from game.modelos.db import Base, get_db, get_engine, get_session_local
from main import app

# Base de datos en memoria
@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = get_engine()
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session

# usa los ALIASES con guiones como espera PartidaData
@pytest.fixture
def datosPartida_1():
    return {
        "nombre-partida": "partiditaTEST",  
        "max-jugadores": 4,                 
        "min-jugadores": 2,                 
        "nombre-jugador": "jugador1TEST",   
        "dia-nacimiento": "2000-10-31"      
    }

@patch('game.partidas.endpoints.PartidaService')
@patch('game.partidas.endpoints.JugadorService')
def test_crear_partida_ok(mock_JugadorService, mock_PartidaService, datosPartida_1, session):
    """Test para crear partida exitosamente"""
    
    def get_db_override():
        yield session
    
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Configurar los mocks
    mock_partida = MagicMock()
    mock_partida.id = 1
    
    mock_jugador = MagicMock()
    mock_jugador.id = 1
    
    # Configurar los servicios mock
    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.crear.return_value = mock_partida
    mock_PartidaService.return_value = mock_partida_service_instance
    
    mock_jugador_service_instance = MagicMock()
    mock_jugador_service_instance.crear.return_value = mock_jugador
    mock_JugadorService.return_value = mock_jugador_service_instance

    # Act: usar los datos con aliases correctos
    response = client.post("/partidas", json=datosPartida_1)

    # DEBUG
    if response.status_code != 201:
        print(f"Error: {response.status_code}, Response: {response.json()}")

    # Limpiar
    app.dependency_overrides.clear()
    
    assert response.status_code == 201
    assert response.json() == {"id_partida": 1, "id_jugador": 1}

def test_crear_partida_max_jugadores_excedido(session):
    """Test cuando se excede el máximo de jugadores"""
    
    def get_db_override():
        yield session
    
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    datos_invalidos = {
        "nombre-partida": "partida inválida",
        "max-jugadores": 8,  # Mayor a 6
        "min-jugadores": 2,
        "nombre-jugador": "jugador1",
        "dia-nacimiento": "2000-10-31"
    }

    response = client.post("/partidas", json=datos_invalidos)
    
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "El máximo de jugadores por partida es 6" in response.json()["detail"]


@patch('game.partidas.endpoints.PartidaService')
@patch('game.partidas.endpoints.JugadorService')
def test_crear_partida_error_servicio(mock_JugadorService, mock_PartidaService, session):
    """Test cuando ocurre un error en el servicio"""
    
    def get_db_override():
        yield session
    
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Configurar el mock para que lance una excepción
    mock_partida_service_instance = MagicMock()
    mock_partida_service_instance.crear.side_effect = Exception("Error de base de datos")
    mock_PartidaService.return_value = mock_partida_service_instance

    datos_validos = {
        "nombre-partida": "partida test",
        "max-jugadores": 4,
        "min-jugadores": 2,
        "nombre-jugador": "jugador1",
        "dia-nacimiento": "2000-10-31"
    }

    response = client.post("/partidas", json=datos_validos)
    
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Error de base de datos" in response.json()["detail"]

def test_crear_partida_sin_campos_obligatorios(session):
    """Test cuando faltan campos obligatorios"""
    
    def get_db_override():
        yield session
    
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Datos incompletos - faltan campos requeridos
    datos_incompletos = {
        "nombre-partida": "partida incompleta"
        # Faltan los otros campos obligatorios
    }

    response = client.post("/partidas", json=datos_incompletos)
    
    app.dependency_overrides.clear()

    assert response.status_code == 422  # Unprocessable Entity

def test_crear_partida_formato_fecha_invalido(session):
    """Test con formato de fecha inválido"""
    
    def get_db_override():
        yield session
    
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    datos_fecha_invalida = {
        "nombre-partida": "partida fecha inválida",
        "max-jugadores": 4,
        "min-jugadores": 2,
        "nombre-jugador": "jugador1",
        "dia-nacimiento": "fecha-invalida"  # Formato incorrecto
    }

    response = client.post("/partidas", json=datos_fecha_invalida)
    
    app.dependency_overrides.clear()

    assert response.status_code == 422  # Error de validación

# Test adicional para verificar el mapeo de aliases
def test_partida_data_model():
    """Test que verifica que PartidaData funciona correctamente con aliases"""
    from game.partidas.schemas import PartidaData
    
    # Datos con aliases (como vendrían del frontend)
    datos_con_alias = {
        "nombre-partida": "test partida",
        "max-jugadores": 4,
        "min-jugadores": 2,
        "nombre-jugador": "test jugador",
        "dia-nacimiento": "2000-10-31"
    }
    
    # Debería crear el modelo correctamente
    partida_data = PartidaData(**datos_con_alias)
    
    assert partida_data.nombrePartida == "test partida"
    assert partida_data.maxJugadores == 4
    assert partida_data.minJugadores == 2
    assert partida_data.nombreJugador == "test jugador"
    assert partida_data.fechaNacimiento == date(2000, 10, 31)