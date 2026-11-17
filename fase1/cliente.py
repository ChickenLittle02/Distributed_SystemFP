"""Actor cliente: quien quiere el archivo (esqueleto, F1-S03).

Responsabilidad: crear el pedido_id, pedir el recurso por su nombre al
borde preferido y anotar solicitud y respuesta.
Todavía no hay selección de fuente: si el borde no responde o rechaza, no
prueba otro (F1-S07).
No guarda caché, no numera versiones y no aplica STALE_LIMIT. No habla con
el origen.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import ray

from fase1.config import Config
from fase1.registro import registrar


@ray.remote
class Cliente:
    """Cliente del sistema, en su propio proceso.

    Entra (al crearlo): nombre ("cliente"), dict nombre_de_borde -> handle
    del actor borde, y la Config (de ahí sale el orden de preferencia).
    Sale: listo() y pedir(recurso).
    Si el otro nodo no contesta: por ahora espera; el paso a otro borde es F1-S07.
    """

    def __init__(self, nombre: str, bordes: Dict[str, Any], config: Config) -> None:
        self.nombre = nombre
        self.bordes = bordes
        self.cfg = config
        self.preferidos = [b for b in config.bordes if b in bordes]

    def listo(self) -> str:
        """Confirma que el cliente vive. Entra: nada. Sale: el nombre."""
        registrar(self.nombre, "arranque", "listo", bordes=",".join(self.preferidos))
        return self.nombre

    def pedir(self, recurso: str, pedido_id: Optional[str] = None) -> Dict[str, Any]:
        """Pide un recurso al borde preferido y devuelve la respuesta.

        Entra: nombre del recurso; pedido_id opcional (si no viene, el
        cliente lo crea).
        Sale: dict con resultado, version, contenido, fuente y pedido_id.
        Si el otro nodo no contesta: espera (hasta F1-S07).
        """
        pedido_id = pedido_id or uuid.uuid4().hex[:6]
        borde = self.preferidos[0]
        registrar(self.nombre, pedido_id, "solicitud", recurso=recurso, fuente=borde)
        r = ray.get(self.bordes[borde].pedir.remote(pedido_id, recurso))
        registrar(self.nombre, pedido_id, "respuesta", version=r.get("version"),
                  resultado=r["resultado"], fuente=borde)
        r["fuente"] = borde
        r["pedido_id"] = pedido_id
        return r
