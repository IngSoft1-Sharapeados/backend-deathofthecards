import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
from game.modelos.db import Base, get_db, get_engine, get_session_local
from settings import settings
from main import app
from game.partidas.endpoints import get_manager
from fastapi import WebSocketDisconnect
import json
from starlette.websockets import WebSocket
from sqlalchemy.pool import StaticPool

#from game.jugadores.models import Jugador
#from game.partidas.models import Partida
#from game.cartas.models import Carta

# Base de datos en memoria
@pytest.fixture(name="session")
def dbTesting_fixture():
    #engine = get_engine()
    #engine = get_engine(settings.TEST_DATABASE_URL)
    engine = (
        create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
        )
    )
    TestingSessionLocal = get_session_local(engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session

@pytest.fixture
def partidas_mock():
    partida1 = MagicMock()
    partida1.id = 1
    partida1.nombre = "PartidaUno"
    partida1.iniciada = False
    partida1.maxJugadores = 4
    partida1.minJugadores = 2
    partida1.cantJugadores = 1

    partida2 = MagicMock()
    partida2.id = 2
    partida2.nombre = "PartidaDos"
    partida2.iniciada = False
    partida2.maxJugadores = 5
    partida2.minJugadores = 2
    partida2.cantJugadores = 1


    return [partida1, partida2]

@pytest.fixture
def jugadores_mock():
    j1 = MagicMock()
    j1.id = 1
    j1.nombre = "Pepito"
    j1.fecha_nacimiento = date(2023, 2, 2)

    j2 = MagicMock()
    j2.id = 2
    j2.nombre = "Raul"
    j2.fecha_nacimiento = date(1023, 3, 12)

    return [j1, j2]


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

@pytest.fixture(name="client")
def client_fixture(session):
    """
    Fixture que crea el TestClient de FastAPI y anula la dependencia de la DB
    para usar la sesión de prueba (session). Además, limpia el override al finalizar.
    """
    
    # 1. Función de override que usa el fixture 'session'
    def get_db_override():
        try:
            yield session 
        finally:
            # Puedes omitir session.close() aquí, ya que el fixture 'session' lo hace al final
            pass 

    # 2. Aplicar el override antes de crear el cliente
    app.dependency_overrides[get_db] = get_db_override
    
    # 3. Limpiar el ConnectionManager global para aislar tests de WebSocket (Opcional, pero recomendado)
    from game.partidas.endpoints import manager 
    manager.active_connections.clear() 
    manager.active_connections_personal.clear()
    
    # 4. Crear el TestClient
    client = TestClient(app)
    
    yield client
    
    # 5. Limpieza final: Quitar el override al finalizar el test
    app.dependency_overrides.clear()

# --------------------- TEST CREAR PARTIDA OK --------------------------------
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
    print("response:", response.json())
    
    assert response.status_code == 201
    assert response.json() == {"id_partida": 1, "id_jugador": 1, "id_Anfitrion": 1}

# --------- TESTS CREAR PARTIDA MAX JUGADORES EXCEDIDOS --------------------------------

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


# --------------- TESTS CREAR PARTIDA ERROR SERVICIO --------------------------------


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

# ------------- TESTS CREAR PARTIDA SIN CAMPOS OBLIGATORIOS--------------------------------

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

# ------------ TESTS CREAR PARTIDA FORMATO FECHA INVALIDO--------------------------------


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

# --------------------- TEST OBTENER DATOS PARTIDA OK ---------------------
@patch('game.partidas.endpoints.listar_jugadores') 
@patch('game.partidas.endpoints.PartidaService')
def test_obtener_datos_partida_ok(mock_PartidaService, mock_listar_jugadores, datosPartida_1, session):
    """Test para obtener los datos de una partida exitosamente"""

    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_service = MagicMock()
    mock_partida = MagicMock()
    mock_partida.id = 1
    mock_partida.nombre = datosPartida_1["nombre-partida"]
    mock_partida.iniciada = False
    mock_partida.maxJugadores = datosPartida_1["max-jugadores"]
    mock_partida.minJugadores = datosPartida_1["min-jugadores"]
    mock_partida.cantJugadores = 1
    mock_partida.anfitrionId = 1
    mock_service.obtener_por_id.return_value = mock_partida
    mock_PartidaService.return_value = mock_service

    response = client.get("/partidas/1")

    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    assert response.json() == {
        "nombre_partida": "partiditaTEST",
        "iniciada": False,
        "maxJugadores": datosPartida_1["max-jugadores"],
        "minJugadores": datosPartida_1["min-jugadores"],
        "listaJugadores": [],
        "cantidad_jugadores": 1,
        "id_anfitrion": 1
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
            "minJugadores": 2,
            "cantJugadores": 1,

        },
        {
            "id": 2,
            "nombre": "PartidaDos",
            "iniciada": False,
            "maxJugadores": 5,
            "minJugadores": 2,
            "cantJugadores": 1,
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

    assert response.status_code == 200
    assert response.json() == []
    
    # ---------------- FIXTURE ----------------
@pytest.fixture
def jugador_data():
    return {
        "nombreJugador": "Jtest",
        "fechaNacimiento": "2000-10-31"
    }

# ---------------- TEST OK ----------------
@patch("game.partidas.endpoints.PartidaService")
@patch("game.partidas.endpoints.JugadorService")
def test_unir_jugador_a_partida_ok(mock_JugadorService, mock_PartidaService, jugador_data, session):
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock de partida con espacio disponible
    mock_partida = MagicMock()
    mock_partida.id = 1
    mock_partida.cantJugadores = 2
    mock_partida.maxJugadores = 4
    mock_PartidaService.return_value.obtener_por_id.return_value = mock_partida

    # Mock de jugador creado
    mock_jugador = MagicMock()
    mock_jugador.id = 99
    mock_jugador.nombre = "Jtest"
    mock_jugador.fecha_nacimiento = "2000-10-31"
    mock_JugadorService.return_value.crear_unir.return_value = mock_jugador

    # Mock de unir_jugador (no devuelve nada relevante)
    mock_PartidaService.return_value.unir_jugador.return_value = None

    response = client.post("/partidas/1", json=jugador_data)
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id_jugador": 99,
        "nombre_jugador": "Jtest",
        "fecha_nacimiento": "2000-10-31"
    }
    
# ---------------- TEST PARTIDA LLENA ----------------
@patch("game.partidas.endpoints.PartidaService")
def test_unir_jugador_partida_llena(mock_PartidaService, jugador_data, session):
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_partida = MagicMock()
    mock_partida.cantJugadores = 4
    mock_partida.maxJugadores = 4
    mock_PartidaService.return_value.obtener_por_id.return_value = mock_partida

    response = client.post("/partidas/1", json=jugador_data)
    app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json()["detail"] == "La partida ya tiene el máximo de jugadores."

# ---------------- TEST PARTIDA NO ENCONTRADA ----------------
@patch("game.partidas.endpoints.PartidaService")
def test_unir_jugador_partida_no_encontrada(mock_PartidaService, jugador_data, session):
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_PartidaService.return_value.obtener_por_id.side_effect = Exception("No se encontró")


#----------------------TEST INICIAR PARTIDA OK --------------------

@pytest.fixture
def datos_jugador():
    return {
        "id_jugador": 1,
    }

@patch("game.partidas.endpoints.PartidaService")
def test_iniciar_partida_ok(mock_PartidaService, datos_jugador, jugadores_mock, session):
   # Mock PartidaService
    mock_service = MagicMock()
    mock_partida = MagicMock()
    mock_partida.jugadores = jugadores_mock
    mock_service.iniciar.return_value = mock_partida
    mock_service.obtener_por_id.return_value = mock_partida
    mock_PartidaService.return_value = mock_service

    # Override de la DB
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Hacemos la request simulando query + body
    response = client.put(
        "/partidas/1",
        json=datos_jugador
    )

    app.dependency_overrides.clear()

    # Assertions
    assert response.status_code == 200
    assert response.json()["detail"] == "Partida iniciada correctamente."

#---------------------- TEST INICIAR PARTIDA NO AUTORIZADO ----------------------

@pytest.fixture
def datos_jugadorNoAutorizado():
    return {
        "id_jugador": 2,
    }

@patch("game.partidas.endpoints.PartidaService")
def test_iniciar_partida_no_autorizado(mock_PartidaService, datos_jugadorNoAutorizado, session):
    # Creamos un mock del servicio que lanza PermissionError
    mock_service = MagicMock()
    mock_service.iniciar.side_effect = PermissionError("Solo el anfitrión puede iniciar la partida")
    mock_PartidaService.return_value = mock_service

    # Override de la DB
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Hacemos la request simulando query + body
    response = client.put(
        "/partidas/1",
        json=datos_jugadorNoAutorizado
    )

    app.dependency_overrides.clear()
    
    # Assertions
    assert response.status_code == 403
    assert response.json() == {"detail": "Solo el anfitrión puede iniciar la partida"}

    # Verificamos que se llamó correctamente al servicio
    mock_service.iniciar.assert_called_once_with(1, 2)

#---------------------- TEST INICIAR PARTIDA NO ENCONTRADA ----------------------
@patch("game.partidas.endpoints.PartidaService")
def test_iniciar_partida_no_encontrada(mock_PartidaService, datos_jugador, session):
    # Creamos un mock del servicio que lanza ValueError
    mock_service = MagicMock()
    mock_service.iniciar.side_effect = ValueError("No se encontró la partida con ID 999")
    mock_PartidaService.return_value = mock_service

    # Override de la DB
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Hacemos la request simulando query + body
    response = client.put(
        "/partidas/999",
        json=datos_jugador
    )

    app.dependency_overrides.clear()
    
    # Assertions
    assert response.status_code == 400
    assert response.json() == {"detail": "No se encontró la partida con ID 999"}

    # Verificamos que se llamó correctamente al servicio
    mock_service.iniciar.assert_called_once_with(999, 1)

#----------------------------TEST INICIAR PARTIDA YA INICIADA--------------------
@patch("game.partidas.endpoints.PartidaService")
def test_iniciar_partida_ya_iniciada(mock_PartidaService, datos_jugador, session):
    # Creamos un mock del servicio que lanza ValueError
    mock_service = MagicMock()
    mock_service.iniciar.side_effect = ValueError("La partida con ID {id_partida} ya está iniciada")
    mock_PartidaService.return_value = mock_service

    # Override de la DB
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Hacemos la request simulando query + body
    response = client.put(
        "/partidas/1",
        json=datos_jugador
    )

    app.dependency_overrides.clear()
    
    # Assertions
    assert response.status_code == 400
    assert response.json() == {"detail": "La partida con ID {id_partida} ya está iniciada"}

    # Verificamos que se llamó correctamente al servicio
    mock_service.iniciar.assert_called_once_with(1, 1)

#----------------------TEST INICIAR PARTIDA CON JUGADORES INSUFICIENTES--------------------
@patch("game.partidas.endpoints.PartidaService")
def test_iniciar_partida_jugadores_insuficientes(mock_PartidaService, datos_jugador, session):
    # Creamos un mock del servicio que lanza ValueError
    mock_service = MagicMock()
    mock_service.iniciar.side_effect = ValueError("No hay suficientes jugadores para iniciar la partida (mínimo {partida.minJugadores}")
    mock_PartidaService.return_value = mock_service

    # Override de la DB
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Hacemos la request simulando query + body
    response = client.put(
        "/partidas/1",
        json=datos_jugador
    )

    app.dependency_overrides.clear()
    
    # Assertions
    assert response.status_code == 400
    assert response.json() == {"detail": "No hay suficientes jugadores para iniciar la partida (mínimo {partida.minJugadores}"}

    # Verificamos que se llamó correctamente al servicio
    mock_service.iniciar.assert_called_once_with(1, 1)


# La ruta para crear la partida es /partidas/
CREATE_PARTIDA_PATH = "/partidas" 

def test_websocket_broadcast_al_unir_jugador(session):
    """
    Verifica que al unirse un segundo jugador mediante el endpoint HTTP, 
    el primer jugador conectado al WebSocket reciba el mensaje de broadcast.
    """
    # Override de la DB
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    jugador1_data = {
        "nombre-partida": "PartidaUnidad",
        "max-jugadores": 4,
        "min-jugadores": 2,
        "nombre-jugador": "Jugador1_Oye",
        "dia-nacimiento": "2000-01-01"
    }
    
    response_creacion = client.post(CREATE_PARTIDA_PATH, json=jugador1_data)
    print("Status code:", response_creacion.status_code)
    print("Response body:", response_creacion.text)
    assert response_creacion.status_code == 201
    
    data_creacion = response_creacion.json()
    partida_id = data_creacion["id_partida"]
    jugador1_id = data_creacion["id_jugador"]
    
    with client.websocket_connect(f"/partidas/ws/{partida_id}/{jugador1_id}") as ws_oyente:
        
        jugador2_data = {
            "nombreJugador": "Jugador2_Nuevo",
            "fechaNacimiento": "2001-02-02"
        }

        union_path = f"{CREATE_PARTIDA_PATH}/{partida_id}"
        response_union = client.post(union_path, json=jugador2_data)
        assert response_union.status_code == 200
        
        data_union = response_union.json()
        jugador2_id = data_union["id_jugador"]
        nombre_jugador2 = data_union["nombre_jugador"]
        
        try:
            message = ws_oyente.receive_json() 
            
            assert message["evento"] == "union-jugador"
            assert message["id_jugador"] == jugador2_id
            assert message["nombre_jugador"] == nombre_jugador2

            app.dependency_overrides.clear()
            
        except TimeoutError:
            assert False, "El WebSocket del Jugador 1 no recibió el mensaje de 'union-jugador' dentro del tiempo límite."
        except json.JSONDecodeError:
            assert False, "El mensaje recibido no era JSON válido."



# Ruta del endpoint HTTP que dispara el broadcast
UNIR_JUGADOR_PATH = "/partidas/{id_partida}" 

@patch("game.partidas.endpoints.JugadorService")
@patch("game.partidas.endpoints.PartidaService")
def test_unir_jugador_triggea_broadcast_mockedCHATGPT(
    mock_PartidaService, 
    mock_JugadorService, 
    session
):
    
    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override

    # mock manager
    mock_manager_instance = MagicMock()
    mock_manager_instance.broadcast = AsyncMock()

    def get_manager_override():
        return mock_manager_instance
    app.dependency_overrides[get_manager] = get_manager_override

    client = TestClient(app)

    PARTIDA_ID = 42
    JUGADOR_ID_NUEVO = 99
    NOMBRE_JUGADOR_NUEVO = "JugadorMockeado"
    FECHA_NAC_JUGADOR = date(2000,1, 31)

    # Mock partida
    mock_partida = MagicMock()
    mock_partida.cantJugadores = 2
    mock_partida.maxJugadores = 4
    mock_partida.minJugadores = 2
    mock_partida.iniciada = False
    mock_PartidaService.return_value.obtener_por_id.return_value = mock_partida

    # Mock jugador
    mock_jugador = MagicMock()
    mock_jugador.id = JUGADOR_ID_NUEVO
    mock_jugador.nombre = NOMBRE_JUGADOR_NUEVO
    mock_jugador.fecha_nacimiento = FECHA_NAC_JUGADOR
    mock_JugadorService.return_value.crear_unir.return_value = mock_jugador

    mock_PartidaService.return_value.unir_jugador.return_value = None

    jugador2_data = {
        "nombreJugador": NOMBRE_JUGADOR_NUEVO,
        "fechaNacimiento": "2001-02-02"
    }

    response = client.post(f"{UNIR_JUGADOR_PATH.format(id_partida=PARTIDA_ID)}", json=jugador2_data)


    app.dependency_overrides.clear()

    assert response.status_code == 200

    expected_message = json.dumps({
        "evento": "union-jugador",
        "id_jugador": JUGADOR_ID_NUEVO,
        "nombre_jugador": NOMBRE_JUGADOR_NUEVO
    })

    mock_manager_instance.broadcast.assert_awaited_once_with(PARTIDA_ID, expected_message)

#----------------- Test obtener orden turnos ok-------------------------

@patch("game.partidas.endpoints.PartidaService")
def test_obtener_orden_turnos(mock_PartidaService, session):
    # Override de la DB
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    orden_de_turnos = [3,1,2]
    mock_partida = MagicMock()
    mock_partida.ordenTurnos = json.dumps(orden_de_turnos)

    # Configuro el mock del servicio para devolver la partida
    mock_PartidaService.return_value.obtener_por_id.return_value = mock_partida
 

    response = client.get("/partidas/1/turnos") 

    assert response.status_code == 200
    data = response.json()
    assert data == orden_de_turnos

#----------------- Test obtener orden turnos partida no encontrada-------------------------

@patch("game.partidas.endpoints.PartidaService")
def test_orden_turnos_partida_no_existe(mock_PartidaService, session):
    # Override de la DB
    def get_db_override():
        yield session  

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_PartidaService.return_value.obtener_por_id.side_effect = Exception("No encontrada")

    client = TestClient(app)
    response = client.get("/partidas/999/turnos")

    assert response.status_code == 404
    assert response.json()["detail"] == "No existe la partida con el ID proporcionado."


#--------------- TEST OBTENER MANO ------------------------

@patch("game.partidas.endpoints.CartaService")
def test_obtener_mano_ok(mock_CartaService, session):
    """Test para obtener mano de un jugador exitosamente"""

    # Override de DB con la sesión de prueba
    def get_db_override():
        yield session

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # 1. Crear mocks de cartas (similar a mock_partida, mock_jugador en otros tests)
    mock_carta1 = MagicMock()
    mock_carta1.id_carta = 16
    mock_carta1.nombre = "Not so fast"

    mock_carta2 = MagicMock()
    mock_carta2.id_carta = 9
    mock_carta2.nombre = "Mr Satterthwaite"

    # 2. Configurar instancia mock de CartaService
    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.obtener_mano_jugador.return_value = [mock_carta1, mock_carta2]
    mock_CartaService.return_value = mock_carta_service_instance

    # 3. Act
    response = client.get("partidas/1/mano", params={"id_jugador": 1})

    # 4. Limpieza
    app.dependency_overrides.clear()

    # 5. Assert
    assert response.status_code == 200
    assert response.json() == [
        {"id": 16, "nombre": "Not so fast"},
        {"id": 9, "nombre": "Mr Satterthwaite"},
    ]

    # Verificamos que el método se llamó correctamente
    mock_carta_service_instance.obtener_mano_jugador.assert_called_once_with(1, 1)

#---------------- TEST NO SE PUDO OBTENER MANO----------------

@patch("game.partidas.endpoints.CartaService")
def test_obtener_mano_error(mock_CartaService, session):
    """Test cuando no se pudo obtener la mano de un jugador (404)"""

    # Override de DB
    def get_db_override():
        yield session

    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock del servicio
    mock_instance = MagicMock()
    # Para que el endpoint entre al except y devuelva 404
    mock_instance.obtener_mano_jugador.side_effect = Exception("Error inesperado")
    mock_CartaService.return_value = mock_instance

    # Act: llamar al endpoint
    response = client.get("/partidas/1/mano", params={"id_jugador": 999})

    # Limpieza
    app.dependency_overrides.clear()

    # Assert
    assert response.status_code == 404
    assert "No se pudo obtener la mano" in response.json()["detail"]
    assert "Error inesperado" in response.json()["detail"]

    # Verificación de llamada
    mock_instance.obtener_mano_jugador.assert_called_once_with(999, 1)
