"""Selector de fuente: en qué orden el cliente prueba los bordes (F1-S07).

Responsabilidad: dar el orden de bordes para un pedido y recordar qué borde
no respondió para no insistir con él primero durante un rato. Vive junto
al cliente, como dice docs/contrato.md; no es un nodo.
No decide hit, miss ni obsoleto: eso lo decide cada borde con su copia.
No llama a nadie: solo ordena. El origen no está en la lista: el cliente
nunca le habla; es el borde quien baja del origen.
"""

from __future__ import annotations

import time
from typing import Dict, List


class Selector:
    """Política de selección (docs/decisiones.md, 2026-11-19).

    Entra (al crearlo): la lista de bordes en orden de preferencia (el
    primero es el más cercano al cliente) y cuántos segundos se deja al
    final un borde que no respondió.
    Sale: orden(), no_respondio(), respondio().
    Si el otro nodo no contesta: no aplica; no habla con nadie.
    """

    def __init__(self, bordes: List[str], evitar_segundos: float) -> None:
        self.bordes = list(bordes)
        self.evitar_segundos = evitar_segundos
        # borde -> hasta cuándo (time.time()) se le deja al final de la lista
        self._evitados: Dict[str, float] = {}

    def orden(self) -> List[str]:
        """Orden para este pedido: la preferencia fija, con los bordes que no
        respondieron hace poco movidos al final. Nunca se descarta un borde:
        si los demás fallan, también se le pregunta a él."""
        ahora = time.time()
        buenos = [b for b in self.bordes if self._evitados.get(b, 0) <= ahora]
        malos = [b for b in self.bordes if self._evitados.get(b, 0) > ahora]
        return buenos + malos

    def no_respondio(self, borde: str) -> None:
        """Anota que el borde no contestó: va al final durante evitar_segundos."""
        self._evitados[borde] = time.time() + self.evitar_segundos

    def respondio(self, borde: str) -> None:
        """El borde contestó (aunque sea rechaza): recupera su lugar."""
        self._evitados.pop(borde, None)
