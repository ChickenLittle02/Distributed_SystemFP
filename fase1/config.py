"""Configuración de la fase 1.

Responsabilidad: reunir en un solo sitio los números y las listas que el
README dejó abiertos (TTL, STALE_LIMIT, capacidad, política de expulsión,
tiempo de espera, orden de los bordes) y la frase de la política de
selección, para cambiarlos sin buscarlos por el código.
No decide nada: borde, selector y cliente leen de aquí.
Los valores provisionales (TTL 30 s, STALE_LIMIT 60 s) están justificados
en docs/decisiones.md y se vuelven a decidir al cerrar el experimento.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class Config:
    """Valores de la corrida. Entra: nada (o el entorno). Sale: los campos.

    Las variables de entorno P20_TTL, P20_STALE_LIMIT, P20_CAPACIDAD,
    P20_TIMEOUT y P20_EVITAR_BORDE permiten acortar una corrida de prueba
    sin tocar el código.
    """

    # Una copia recién guardada está fresca este tiempo (segundos).
    ttl_segundos: float = 30.0
    # Cuánto tiempo puede llevar obsoleta una copia para servirla cuando el
    # origen no contesta (segundos). No cuenta desde que se guardó: cuenta
    # desde que expiró.
    stale_limit_segundos: float = 60.0
    # Copias que caben en un borde. Pequeña a propósito para ver la expulsión.
    capacidad: int = 2
    # Política de expulsión cuando el borde está lleno.
    expulsion: str = "LRU"
    # Cuánto espera un nodo la respuesta de otro antes de darlo por no
    # disponible (segundos). Es lo que el proyecto llama «no responde».
    timeout_segundos: float = 2.0
    # Cuánto tiempo el selector deja al final de la lista a un borde que no
    # respondió, antes de volver a probarlo primero (segundos). F1-S07.
    evitar_borde_segundos: float = 10.0
    # El canal va en claro en la fase 1. Ver README, «Transporte y cifrado».
    cifrado: bool = False
    # Orden de preferencia de los bordes para el selector. El primero es el
    # «más cercano» al cliente. Lista estática: arranque estático justificado
    # en docs/decisiones.md.
    bordes: List[str] = field(default_factory=lambda: ["borde-1", "borde-2"])

    # La política de selección, en una frase (README §2 y guía, parte 6;
    # decisión del 2026-11-19 en docs/decisiones.md):
    #   el cliente prueba los bordes en el orden de `bordes`, dejando al
    #   final durante evitar_borde_segundos a los que no respondieron;
    #   el borde decide: copia fresca -> hit; si no, el origen -> miss;
    #   si el origen no responde, copia obsoleta dentro de STALE_LIMIT;
    #   si ese borde no responde (timeout, nodo_caido) o rechaza, el siguiente;
    #   si ninguno entrega, rechazar.

    @classmethod
    def desde_entorno(cls) -> "Config":
        """Lee los valores del entorno si están; si no, los de arriba."""
        c = cls()
        c.ttl_segundos = float(os.environ.get("P20_TTL", c.ttl_segundos))
        c.stale_limit_segundos = float(os.environ.get("P20_STALE_LIMIT", c.stale_limit_segundos))
        c.capacidad = int(os.environ.get("P20_CAPACIDAD", c.capacidad))
        c.timeout_segundos = float(os.environ.get("P20_TIMEOUT", c.timeout_segundos))
        c.evitar_borde_segundos = float(
            os.environ.get("P20_EVITAR_BORDE", c.evitar_borde_segundos))
        return c
