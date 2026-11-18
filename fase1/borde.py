"""Actor borde: la caché cercana al cliente (F1-S04: miss, bajada, guarda, hit).

Responsabilidad: guardar copias de los recursos con su versión, decidir
hit o miss, pedir al origen cuando no hay copia y guardar lo que baja.
Anota cada decisión con registrar: miss, pide_origen, guarda, hit.
Todavía no hay TTL (toda copia guardada cuenta como usable, F1-S05), ni
expulsión (la caché crece sin tope, F1-S06), ni revalidación (F1-S08),
ni tiempo de espera al origen ni STALE_LIMIT (F1-S09), ni invalidación
(la aplica el borde cuando exista F1-R06).
No es el origen: no tiene la versión de referencia. No es el selector: no
elige entre bordes; eso vive junto al cliente. No abre sockets: en la fase
1 habla con el origen por una llamada de Ray.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

import ray

from fase1.config import Config
from fase1.registro import registrar


@dataclass
class Copia:
    """Una copia guardada en el borde. Entra al guardarla; no sale del borde.

    version y contenido son los que entregó el origen. guardada_en es
    time.time() en el momento de guardar; desde ahí contará el TTL (F1-S05).
    """

    version: int
    contenido: bytes
    guardada_en: float


def _hora(t: float) -> str:
    """Hora legible para el historial (misma forma que registrar)."""
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


@ray.remote
class Borde:
    """Caché de borde.

    Entra (al crearlo): nombre del nodo ("borde-1"), el handle del actor
    origen y la Config.
    Sale: listo(), pedir(...) y estado().
    Si el otro nodo no contesta: el único «otro nodo» al que llama es el
    origen; por ahora la llamada espera sin límite. El tiempo de espera y
    la regla de obsoleto llegan con F1-S09.
    """

    def __init__(self, nombre: str, origen: Any, config: Config) -> None:
        self.nombre = nombre
        self.origen = origen
        self.cfg = config
        # recurso -> Copia. Solo vive en la memoria del actor: si el borde
        # muere, arranca vacío y el primer pedido vuelve a ser miss.
        self._copias: Dict[str, Copia] = {}

    # ----------------------------------------------------------------- arranque

    def listo(self) -> str:
        """Confirma que el borde vive y deja una línea en el historial.

        Entra: nada. Sale: el nombre del nodo. Si el otro nodo no contesta: no aplica.
        """
        registrar(self.nombre, "arranque", "listo", capacidad=self.cfg.capacidad,
                  ttl=int(self.cfg.ttl_segundos), stale_limit=int(self.cfg.stale_limit_segundos))
        return self.nombre

    # ------------------------------------------------------------------- pedido

    def pedir(self, pedido_id: str, recurso: str) -> Dict[str, Any]:
        """Atiende un pedido del cliente: hit si hay copia, si no baja del origen.

        Entra: pedido_id (lo creó el cliente) y el nombre del recurso.
        Sale: dict con resultado (hit, miss o file_doesnt_exist), version y
        contenido, con el formato de docs/contrato.md.
        Si el otro nodo no contesta: espera (sin tiempo límite hasta F1-S09).
        """
        copia = self._copias.get(recurso)

        # 1. Hay copia: hit, sin hablar con el origen. (Sin TTL todavía,
        #    cualquier copia guardada cuenta como fresca: F1-S05.)
        if copia is not None:
            registrar(self.nombre, pedido_id, "hit", recurso=recurso, version=copia.version)
            return self._respuesta("hit", copia)

        # 2. No hay copia: miss, y se baja del origen.
        registrar(self.nombre, pedido_id, "miss", recurso=recurso, causa="no_esta")
        registrar(self.nombre, pedido_id, "pide_origen", recurso=recurso)
        r = ray.get(self.origen.responder.remote(pedido_id, recurso))

        # 3a. El origen dice que el archivo no existe: contrato, se borra la
        #     copia de ese nombre si la hubiera, y no hay versión ni contenido.
        if not r.get("existe"):
            self._copias.pop(recurso, None)
            return {"resultado": "file_doesnt_exist", "version": None, "contenido": None}

        # 3b. El origen entregó el archivo: se guarda y se responde miss.
        nueva = self._guardar(pedido_id, recurso, r["version"], r["contenido"])
        return self._respuesta("miss", nueva)

    # ------------------------------------------------------------------ estado

    def estado(self) -> Dict[str, Dict[str, Any]]:
        """Qué copias hay, para pruebas y para el experimento.

        Entra: nada. Sale: recurso -> {version, guardada}. Vacío si no hay copias.
        """
        return {
            rec: {"version": c.version, "guardada": _hora(c.guardada_en)}
            for rec, c in self._copias.items()
        }

    # ----------------------------------------------------------------- internos

    def _respuesta(self, resultado: str, copia: Copia) -> Dict[str, Any]:
        """Arma la respuesta del contrato a partir de una copia."""
        return {"resultado": resultado, "version": copia.version, "contenido": copia.contenido}

    def _guardar(self, pedido_id: str, recurso: str, version: int, contenido: bytes) -> Copia:
        """Guarda (o reemplaza) la copia y anota guarda. Sin tope de capacidad hasta F1-S06."""
        copia = Copia(version=version, contenido=contenido, guardada_en=time.time())
        self._copias[recurso] = copia
        registrar(self.nombre, pedido_id, "guarda", recurso=recurso, version=version,
                  bytes=len(contenido))
        return copia
