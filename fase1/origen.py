"""Actor origen: versiones, respuesta de recursos e invalidación.

Responsabilidad: leer archivos de contenido/, llevar la versión de cada
uno (hash SHA-256 como única señal de cambio), responder un pedido con
el archivo o con file_doesnt_exist, y avisar a los bordes anotados cuando
una copia deja de valer. Anota responde e invalidar en el historial.
No es el borde: no hace hit/miss, TTL, STALE_LIMIT ni expulsión, y no
borra las copias (eso lo hace el borde al recibir el aviso). Si un borde
no aplica el aviso, la línea invalidacion_perdida la escribe él (F1-R07);
un actor ya muerto no puede escribirla. No ofrece la API fina de
revalidación (F1-R08); responder ya entrega la versión actual del disco.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import ray
from ray.exceptions import RayActorError

from fase1.registro import registrar

_RAIZ = Path(__file__).resolve().parent.parent
_DIR_CONTENIDO = _RAIZ / "contenido"


@ray.remote
class Origen:
    """Origen dueño de la versión de referencia de cada recurso.

    Entra (al crearlo): nada. Arranca sin estado en memoria; el disco es
    contenido/. Los bordes se anotan después, con anotar_bordes.
    Sale: listo(), responder(...), anotar_bordes(...) e invalidar(...).
    Si el otro nodo no contesta: en invalidar, el borde que no contesta
    no entra en la lista de avisados. La línea del aviso perdido es F1-R07.
    """

    def __init__(self) -> None:
        self.nombre = "origen"
        # recurso -> (version, hash_hex)
        self._versiones: Dict[str, Tuple[int, str]] = {}
        # nombre del borde -> handle del actor. Lo llena el arranque.
        # El origen no descubre bordes: sin esta lista, invalidar no avisa a nadie.
        self._bordes: Dict[str, Any] = {}

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

    def anotar_bordes(self, bordes: Dict[str, Any]) -> List[str]:
        """El arranque le dice al origen a qué bordes puede avisar.

        Entra: nombre del borde -> handle del actor, en el orden de
        preferencia de la configuración.
        Sale: los nombres anotados, en ese mismo orden.
        Si el otro nodo no contesta: no aplica; solo guarda los handles.
        """
        self._bordes = dict(bordes)
        return list(self._bordes)

    def invalidar(self, pedido_id: str, recurso: str) -> Dict[str, Any]:
        """Avisa a los bordes anotados que su copia de este recurso ya no vale.

        Entra: pedido_id y el nombre del recurso.
        Sale: dict con recurso, version (la de referencia tras leer el disco,
        o None si el archivo no está), bordes (los que contestaron, en orden)
        y resultado file_doesnt_exist cuando el archivo no está.
        Si el otro nodo no contesta: ese borde no entra en bordes. Si el
        actor sigue vivo y no aplica el aviso, él anota invalidacion_perdida
        (F1-R07). Si el actor ya murió, no hay esa línea: no llegó a correr.
        """
        ruta = self._ruta_segura(recurso)
        if ruta is None or not ruta.is_file():
            version: Optional[int] = None
        else:
            version, _contenido = self._version_y_bytes(recurso, ruta)

        avisados: List[str] = []
        for nombre, borde in self._bordes.items():
            try:
                quien = ray.get(borde.invalidar.remote(pedido_id, recurso, version))
            except RayActorError:
                continue
            if quien:
                avisados.append(quien)

        datos: Dict[str, Any] = {"recurso": recurso}
        if version is None:
            datos["resultado"] = "file_doesnt_exist"
        else:
            datos["version"] = version
        datos["bordes"] = ",".join(avisados) if avisados else "ninguno"
        registrar(self.nombre, pedido_id, "invalidar", **datos)
        return {
            "recurso": recurso,
            "version": version,
            "bordes": avisados,
            "resultado": "file_doesnt_exist" if version is None else "invalidar",
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
