"""Actor borde: la caché cercana al cliente (esqueleto, F1-S03).

Responsabilidad: recibir el pedido del cliente, pedírselo al origen y
devolver la respuesta. Anota lo que hace con registrar.
Todavía no guarda copias: no hay hit ni miss (F1-S04), ni TTL (F1-S05),
ni expulsión (F1-S06), ni revalidación (F1-S08), ni STALE_LIMIT (F1-S09).
Es el «borde que reenvía» de la guía (parte 6, paso 2).
No es el origen: no tiene la versión de referencia. No es el selector: no
elige entre bordes; eso vive junto al cliente. No abre sockets: en la fase
1 habla con el origen por una llamada de Ray.
"""

from __future__ import annotations

from typing import Any, Dict

import ray

from fase1.config import Config
from fase1.registro import registrar


@ray.remote
class Borde:
    """Caché de borde.

    Entra (al crearlo): nombre del nodo ("borde-1"), el handle del actor
    origen y la Config.
    Sale: listo(), pedir(...) y estado().
    Si el otro nodo no contesta: por ahora la llamada al origen espera sin
    límite; el tiempo de espera y la regla de obsoleto llegan con F1-S09.
    """

    def __init__(self, nombre: str, origen: Any, config: Config) -> None:
        self.nombre = nombre
        self.origen = origen
        self.cfg = config
        # recurso -> copia. Vacío hasta F1-S04.
        self._copias: Dict[str, Any] = {}

    def listo(self) -> str:
        """Confirma que el borde vive y deja una línea en el historial.

        Entra: nada. Sale: el nombre del nodo. Si el otro nodo no contesta: no aplica.
        """
        registrar(self.nombre, "arranque", "listo", capacidad=self.cfg.capacidad,
                  ttl=int(self.cfg.ttl_segundos), stale_limit=int(self.cfg.stale_limit_segundos))
        return self.nombre

    def pedir(self, pedido_id: str, recurso: str) -> Dict[str, Any]:
        """Atiende un pedido del cliente: hoy, lo reenvía al origen.

        Entra: pedido_id (lo creó el cliente) y el nombre del recurso.
        Sale: dict con resultado (miss o file_doesnt_exist), version y
        contenido, con el formato de docs/contrato.md.
        Si el otro nodo no contesta: espera (sin tiempo límite hasta F1-S09).
        """
        registrar(self.nombre, pedido_id, "pide_origen", recurso=recurso)
        r = ray.get(self.origen.responder.remote(pedido_id, recurso))
        if not r.get("existe"):
            return {"resultado": "file_doesnt_exist", "version": None, "contenido": None}
        return {"resultado": "miss", "version": r["version"], "contenido": r["contenido"]}

    def estado(self) -> Dict[str, Any]:
        """Qué copias hay. Entra: nada. Sale: recurso -> datos (vacío por ahora)."""
        return dict(self._copias)
