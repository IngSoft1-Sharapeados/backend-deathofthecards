"""Data transfer objets para jugador"""

from datetime import date

from dataclasses import dataclass
from dataclasses import field as dataclass_field


@dataclass
class JugadorDTO:
    nombre: str
    fecha_nacimiento: date
    