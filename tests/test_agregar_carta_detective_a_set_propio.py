import pytest
import os
import json
from datetime import date

# --- 1. Configuración Inicial ---
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# --- 2. IMPORTACIÓN DE MODELOS ---
from game.partidas.models import Partida
from game.cartas.models import Carta, SetJugado 
from game.jugadores.models import Jugador

# --- 3. Imports de App y BBDD ---
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from game.modelos.db import Base, get_db, get_session_local
from main import app


# --- 4. FIXTURE DE BBDD ---
@pytest.fixture(name="session")
def db_test_fixture():
    """
    Fixture de Pytest que crea una nueva base de datos en memoria para cada test.
    """
    engine = create_engine(
        "sqlite:///:memory:", 
        connect_args={"check_same_thread": False}, 
        poolclass=StaticPool
    )
    
    TestingSessionLocal = get_session_local(engine)
    
    # Crea todas las tablas
    Base.metadata.create_all(bind=engine)
    
    with TestingSessionLocal() as session:
        yield session
    
    Base.metadata.drop_all(bind=engine)


# ----------------------------------------------------------------------
# Test API para /agregar-a-set (Caso OK)
# ----------------------------------------------------------------------
def test_api_agregar_a_set_ok(session):
    """
    Test de integración para agregar una carta a un set con éxito.
    Verifica que la API funciona y que la base de datos se actualiza 
    correctamente por la lógica de negocio (sin mocks).
    """
    
    # --- Override de la Dependencia de BBDD ---
    def get_db_override():
        yield session
    
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # --- Arrange (Configuración de la Base de Datos) ---
    
    ID_PARTIDA = 1
    ID_JUGADOR = 2
    ID_TIPO_SET = 10
    ID_SET_JUGADO_PK = 3
    ID_CARTA_INSTANCIA = 12

    partida = Partida(
        id=ID_PARTIDA,
        nombre="PartidaDePrueba",
        anfitrionId=ID_JUGADOR,
        minJugadores=4,
        maxJugadores=12,
        cantJugadores=1,         
        accion_en_progreso=None,
        iniciada=True
    )
    
    jugador = Jugador(
        id=ID_JUGADOR,
        partida_id=ID_PARTIDA,
        nombre="JugadorDePrueba",
        fecha_nacimiento=date(1990, 1, 1), 
        desgracia_social=0 
    )
    
    set_existente = SetJugado(
        id=ID_SET_JUGADO_PK,
        partida_id=ID_PARTIDA,
        jugador_id=ID_JUGADOR,
        representacion_id_carta=ID_TIPO_SET,
        cartas_ids_csv="10,14"
    )
    
    carta_para_agregar = Carta(
        id=ID_CARTA_INSTANCIA,
        id_carta=ID_TIPO_SET,
        nombre="Parker Pyne",
        tipo="Detective",
        partida_id=ID_PARTIDA,
        jugador_id=ID_JUGADOR, 
        ubicacion="mano"
    )

    session.add_all([partida, jugador, set_existente, carta_para_agregar])
    session.commit()
    
    session.refresh(partida)
    session.refresh(jugador)
    session.refresh(set_existente)
    session.refresh(carta_para_agregar)

    # --- Act (Llamada a la API) ---
    
    payload_json = {
        "id_carta_instancia": ID_CARTA_INSTANCIA,
        "id_jugador_set": ID_JUGADOR,
        "id_tipo_set": ID_TIPO_SET
    }

    response = client.post(
        f"/partidas/{ID_PARTIDA}/agregar-a-set",
        json=payload_json
    )

    # Verificar que la API respondió 200 OK
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.json()}"
    assert response.json()["detail"] == "Carta agregada al set"
    assert response.json()["set_id"] == ID_SET_JUGADO_PK 

    # Verificar los cambios en la Base de Datos
    session.refresh(carta_para_agregar) 
    session.refresh(set_existente)
    
    assert carta_para_agregar.ubicacion == "set_jugado"
    assert carta_para_agregar.jugador_id == ID_JUGADOR 
    assert set_existente.cartas_ids_csv == "10,14,10"

    # --- Limpieza ---
    app.dependency_overrides.clear()