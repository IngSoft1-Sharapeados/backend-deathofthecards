import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from main import app
from game.modelos.db import Base, get_db

# ---------------- Fixture de base de datos en memoria ----------------
@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session

# ---------------- Test completo para Another Victim ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_ok(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_jugar_carta_evento, mock_CartaService, session
):
    """Test completo para el evento Another Victim (OK)"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock de validaciones
    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.return_value = None

    # Mock del servicio de cartas
    mock_carta_service_instance = MagicMock()
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 2,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/1/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    # ---- Assertions ----
    assert response.status_code == 200
    mock_CartaService.return_value.robar_set.assert_called_once_with(
        1, 1, 2, 10, [101, 102, 103]
    )
    mock_verif_evento.assert_called_once_with("Another Victim", 99)
    mock_verif_jugador_objetivo.assert_called_once()

# ---------------- Test evento con partida inexistente ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_partida_inexistente(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_CartaService, session
):
    """Test para verificar que se maneja correctamente cuando la partida no existe"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock de validaciones
    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.return_value = None

    # Mock del servicio de cartas para lanzar excepción
    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.robar_set.side_effect = ValueError("No se ha encontrado la partida")
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 2,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/999/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404

# ---------------- Test evento con jugador inexistente ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_jugador_no_encontrado(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_CartaService, session
):
    """Test cuando el jugador objetivo no se encuentra"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.side_effect = ValueError("objetivo no se encontro")

    mock_carta_service_instance = MagicMock()
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 999,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/1/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from main import app
from game.modelos.db import Base, get_db

# ---------------- Fixture de base de datos en memoria ----------------
@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session

# ---------------- Test completo para Another Victim ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_ok(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_jugar_carta_evento, mock_CartaService, session
):
    """Test completo para el evento Another Victim (OK)"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock de validaciones
    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.return_value = None

    # Mock del servicio de cartas
    mock_carta_service_instance = MagicMock()
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 2,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/1/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    # ---- Assertions ----
    assert response.status_code == 200
    mock_CartaService.return_value.robar_set.assert_called_once_with(
        1, 1, 2, 10, [101, 102, 103]
    )
    mock_verif_evento.assert_called_once_with("Another Victim", 99)
    mock_verif_jugador_objetivo.assert_called_once()

# ---------------- Test evento con partida inexistente ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_partida_inexistente(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_CartaService, session
):
    """Test para verificar que se maneja correctamente cuando la partida no existe"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock de validaciones
    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.return_value = None

    # Mock del servicio de cartas para lanzar excepción
    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.robar_set.side_effect = ValueError("No se ha encontrado la partida")
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 2,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/999/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404

# ---------------- Test evento con jugador inexistente ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_jugador_no_encontrado(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_CartaService, session
):
    """Test cuando el jugador objetivo no se encuentra"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.side_effect = ValueError("objetivo no se encontro")

    mock_carta_service_instance = MagicMock()
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 999,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/1/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from main import app
from game.modelos.db import Base, get_db

# ---------------- Fixture de base de datos en memoria ----------------
@pytest.fixture(name="session")
def dbTesting_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as session:
        yield session

# ---------------- Test jugar Another Victim ok ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.jugar_carta_evento")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_ok(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_jugar_carta_evento, mock_CartaService, session
):
    """Test completo para el evento Another Victim (OK)"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock de validaciones
    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.return_value = None

    # Mock del servicio de cartas
    mock_carta_service_instance = MagicMock()
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 2,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/1/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    # ---- Assertions ----
    assert response.status_code == 200
    mock_CartaService.return_value.robar_set.assert_called_once_with(
        1, 1, 2, 10, [101, 102, 103]
    )
    mock_verif_evento.assert_called_once_with("Another Victim", 99)
    mock_verif_jugador_objetivo.assert_called_once()

# ---------------- Test evento con partida inexistente ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_partida_inexistente(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_CartaService, session
):
    """Test para verificar que se maneja correctamente cuando la partida no existe"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    # Mock de validaciones
    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.return_value = None

    # Mock del servicio de cartas para lanzar excepción
    mock_carta_service_instance = MagicMock()
    mock_carta_service_instance.robar_set.side_effect = ValueError("No se ha encontrado la partida")
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 2,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/999/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404

# ---------------- Test evento con jugador inexistente ----------------
@patch("game.partidas.endpoints.CartaService")
@patch("game.partidas.endpoints.verif_jugador_objetivo")
@patch("game.partidas.endpoints.verif_evento")
def test_another_victim_jugador_no_encontrado(
    mock_verif_evento, mock_verif_jugador_objetivo,
    mock_CartaService, session
):
    """Test cuando el jugador objetivo no se encuentra"""

    def get_db_override():
        yield session
    app.dependency_overrides[get_db] = get_db_override
    client = TestClient(app)

    mock_verif_evento.return_value = True
    mock_verif_jugador_objetivo.side_effect = ValueError("objetivo no se encontro")

    mock_carta_service_instance = MagicMock()
    mock_CartaService.return_value = mock_carta_service_instance

    payload = {
        "id_objetivo": 999,
        "id_representacion_carta": 10,
        "ids_cartas": [101, 102, 103]
    }

    response = client.put(
        "/partidas/1/evento/AnotherVictim?id_jugador=1&id_carta=99",
        json=payload
    )

    app.dependency_overrides.clear()

    assert response.status_code == 404
