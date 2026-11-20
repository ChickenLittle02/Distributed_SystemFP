"""Actor cliente: quien quiere el archivo (F1-S03, F1-S07).

Responsabilidad: crear el pedido_id, pedir el recurso por su nombre al
borde que diga el selector, pasar al siguiente borde si ese no responde
(timeout o nodo_caido) o rechaza, y anotar solicitud y respuesta.
No guarda caché, no numera versiones y no aplica STALE_LIMIT. No elige el
borde a mano: lo hace el selector (fase1/selector.py). No habla con el
origen.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

import ray
from ray.exceptions import RayActorError, RayError

from fase1.config import Config
from fase1.registro import registrar
from fase1.selector import Selector


@ray.remote
class Cliente:
    """Cliente del sistema, en su propio proceso.

    Entra (al crearlo): nombre ("cliente"), dict nombre_de_borde -> handle
    del actor borde, y la Config (orden de preferencia, timeout, cuánto se
    evita un borde que no respondió).
    Sale: listo() y pedir(recurso).
    Si el otro nodo no contesta: si un borde no responde en
    timeout_segundos o su actor murió, lo anota y prueba el siguiente del
    selector. Si ninguno entrega, el resultado es rechaza.
    """

    def __init__(self, nombre: str, bordes: Dict[str, Any], config: Config) -> None:
        self.nombre = nombre
        self.bordes = bordes
        self.cfg = config
        self.selector = Selector([b for b in config.bordes if b in bordes],
                                 config.evitar_borde_segundos)

    def listo(self) -> str:
        """Confirma que el cliente vive. Entra: nada. Sale: el nombre."""
        registrar(self.nombre, "arranque", "listo", bordes=",".join(self.selector.bordes),
                  timeout=self.cfg.timeout_segundos)
        return self.nombre

    def pedir(self, recurso: str, pedido_id: Optional[str] = None) -> Dict[str, Any]:
        """Pide un recurso y devuelve la respuesta final.

        Entra: nombre del recurso; pedido_id opcional (si no viene, el
        cliente lo crea; darlo sirve para repetir un pedido en las pruebas).
        Sale: dict con resultado, version, contenido, fuente (el borde que
        entregó, o None si rechaza) y pedido_id.
        Si el otro nodo no contesta: pasa al siguiente borde del selector;
        si ninguno entrega, el resultado es rechaza.
        Historial: un mismo pedido_id puede dejar varias líneas solicitud
        (una por borde probado); la línea respuesta lleva la fuente que
        entregó. El cliente nunca nombra el borde: lo elige el selector
        (docs/decisiones.md, 16 nov «El cliente pide por nombre»).
        """
        pedido_id = pedido_id or uuid.uuid4().hex[:6]
        for borde in self.selector.orden():
            registrar(self.nombre, pedido_id, "solicitud", recurso=recurso, fuente=borde)
            r = self._llamar_borde(pedido_id, borde, recurso)
            if r is None:
                self.selector.no_respondio(borde)
                continue
            self.selector.respondio(borde)
            if r["resultado"] == "rechaza":
                # El rechaza de un borde no es final: ese borde agotó sus
                # fuentes y el contrato dice probar el otro. El rechaza final
                # lo anota el cliente abajo, cuando no queda ningún borde
                # (docs/decisiones.md, 16 nov «rechaza solo cuando ninguna
                # fuente entrega»).
                continue
            registrar(self.nombre, pedido_id, "respuesta", version=r.get("version"),
                      resultado=r["resultado"], fuente=borde)
            r["fuente"] = borde
            r["pedido_id"] = pedido_id
            return r
        registrar(self.nombre, pedido_id, "respuesta", resultado="rechaza", fuente="ninguna")
        return {"resultado": "rechaza", "version": None, "contenido": None,
                "fuente": None, "pedido_id": pedido_id}

    def _llamar_borde(self, pedido_id: str, borde: str, recurso: str) -> Optional[Dict[str, Any]]:
        """Llama al borde con tiempo de espera. None significa «no responde».

        «No responde» es: la llamada no vuelve en timeout_segundos (línea
        timeout) o el actor del borde murió (línea nodo_caido).
        """
        try:
            ref = self.bordes[borde].pedir.remote(pedido_id, recurso)
            listos, _ = ray.wait([ref], timeout=self.cfg.timeout_segundos)
            if not listos:
                registrar(self.nombre, pedido_id, "timeout", destino=borde,
                          segundos=self.cfg.timeout_segundos)
                return None
            return ray.get(listos[0])
        except RayActorError:
            registrar(self.nombre, pedido_id, "nodo_caido", destino=borde)
            return None
        except RayError as e:
            registrar(self.nombre, pedido_id, "nodo_caido", destino=borde,
                      causa=type(e).__name__)
            return None
