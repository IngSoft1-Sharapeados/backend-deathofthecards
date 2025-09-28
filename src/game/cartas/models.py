"""Modelo Carta"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from game.modelos.db import Base

class Carta(Base):
    __tablename__ = "cartas"
 
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    bocaArriba: Mapped[bool] = mapped_column(Boolean, default=True)
    ubicacion: Mapped[str] = mapped_column(String, nullable=True)
    descripcion: Mapped[str] = mapped_column(String, nullable=True)
 
    # Relación de muchos a 1 con Jugador
    jugador_id: Mapped[int] = mapped_column(Integer, ForeignKey("jugadores.id"))
    jugador: Mapped["Jugador"] = relationship("Jugador", back_populates="cartas")

    # Relacion de muchos a 1 con partida
    partida_id: Mapped[int] = mapped_column(Integer, ForeignKey("partidas.id"))
    partida: Mapped["Partida"] = relationship("Partida", back_populates="cartas")