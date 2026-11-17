"""Actor origen: versiones y respuesta de recursos.

Responsabilidad: leer archivos de contenido/, llevar la versión de cada
uno (hash SHA-256 como única señal de cambio) y responder un pedido con
el archivo o con file_doesnt_exist. Anota responde en el historial.
No es el borde: no hace hit/miss, TTL, STALE_LIMIT ni expulsión.
Todavía no invalida bordes (F1-R06) ni ofrece la API fina de revalidación
(F1-R08); responder ya entrega la versión actual del disco.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import ray

from fase1.registro import registrar

_RAIZ = Path(__file__).resolve().parent.parent
_DIR_CONTENIDO = _RAIZ / "contenido"


@ray.remote
class Origen:
    """Origen dueño de la versión de referencia de cada recurso.

    Entra (al crearlo): nada. Arranca sin estado en memoria; el disco es
    contenido/.
    Sale: listo() y responder(...).
    Si el otro nodo no contesta: este actor no llama a bordes ni cliente.
    """

    def __init__(self) -> None:
        self.nombre = "origen"
        # recurso -> (version, hash_hex)
        self._versiones: Dict[str, Tuple[int, str]] = {}

    def listo(self) -> str:
        """Confirma que el origen está vivo y deja una línea en el historial.

        Entra: nada.
        Sale: el nombre del nodo ("origen").
        Si el otro nodo no contesta: no aplica; no habla con nadie.
        """
        registrar(self.nombre, "arranque", "listo")
        return self.nombre

    def responder(self, pedido_id: str, recurso: str) -> Dict[str, Any]:
        """Entrega el archivo actual o dice que no existe.

        Entra: pedido_id (lo copia el borde desde el cliente) y el nombre
        del recurso (solo el nombre del archivo, sin rutas).
        Sale: dict con existe, version, contenido y, si falta, resultado
        file_doesnt_exist. Siempre anota en el historial.
        Si el otro nodo no contesta: no aplica; solo lee disco local.
        """
        ruta = self._ruta_segura(recurso)
        if ruta is None or not ruta.is_file():
            registrar(
                self.nombre,
                pedido_id,
                "responde",
                recurso=recurso,
                resultado="file_doesnt_exist",
            )
            return {
                "existe": False,
                "version": None,
                "contenido": None,
                "resultado": "file_doesnt_exist",
            }

        version, contenido = self._version_y_bytes(recurso, ruta)
        registrar(
            self.nombre,
            pedido_id,
            "responde",
            recurso=recurso,
            version=version,
        )
        return {
            "existe": True,
            "version": version,
            "contenido": contenido,
            "resultado": "responde",
        }

    def _ruta_segura(self, recurso: str) -> Optional[Path]:
        """Resuelve el recurso dentro de contenido/ sin salir de la carpeta.

        Entra: nombre del recurso.
        Sale: Path al archivo, o None si el nombre no es seguro.
        """
        if not recurso or recurso != Path(recurso).name:
            return None
        if ".." in recurso or "/" in recurso or "\\" in recurso:
            return None
        return _DIR_CONTENIDO / recurso

    def _version_y_bytes(self, recurso: str, ruta: Path) -> Tuple[int, bytes]:
        """Lee el archivo, actualiza la versión si el hash cambió y devuelve ambos.

        Entra: nombre del recurso y Path ya validado.
        Sale: (version, contenido en bytes).
        """
        contenido = ruta.read_bytes()
        huella = hashlib.sha256(contenido).hexdigest()
        anterior = self._versiones.get(recurso)
        if anterior is None:
            version = 1
        elif anterior[1] == huella:
            version = anterior[0]
        else:
            version = anterior[0] + 1
        self._versiones[recurso] = (version, huella)
        return version, contenido
