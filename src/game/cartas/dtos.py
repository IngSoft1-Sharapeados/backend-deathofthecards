"""Data transfer objets para cartas"""

from dataclasses import dataclass
from dataclasses import field as dataclass_field


@dataclass
class CartaDTO:
    nombre: str
    tipo: enumerate = { "detective", "secreto",
                       "devious", "insta",
                       "evento", "asesino escapo?"   
                    }
    bocaArriba: bool
    ubicacion: enumerate = { "mano", "mazo", 
                          "descartes"
                        } 
    descripcion: str 
    jugador_id: int
    partida_id: int