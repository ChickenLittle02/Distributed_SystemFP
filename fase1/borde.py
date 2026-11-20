"""Actor borde: la caché cercana al cliente (F1-S04 a F1-S06, aviso F1-R06).

Responsabilidad: guardar copias de los recursos con su versión y su
expiración (TTL), decidir hit o miss, pedir al origen cuando no hay copia
usable, guardar lo que baja y expulsar por LRU cuando el borde se llena.
Cuando el origen avisa que una copia ya no vale, no se borra: se marca
invalidada y no se devuelve aunque la pidan. Si perder_avisos está
activo, el aviso no se aplica: la copia sigue válida y se anota
invalidacion_perdida (F1-R07). Esa copia se sigue sirviendo con el TTL.
Anota cada decisión con registrar: hit, miss (con causa), pide_origen,
revalida, guarda, expulsion, borra, invalidacion_recibida, invalidacion_perdida.
Todavía no hay tiempo de espera al origen ni STALE_LIMIT (F1-S09: hoy el
origen que no contesta bloquea el pedido), ni el mensaje de revalidación
sin bajar los bytes (F1-S08, cuando el origen tenga F1-R08).
No es el origen: no tiene la versión de referencia ni decide a quién
avisar. No es el selector: no elige entre bordes; eso vive junto al
cliente. No abre sockets: en la fase 1 habla con el origen por una
llamada de Ray.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import ray

from fase1.config import Config
from fase1.registro import registrar


@dataclass
class Copia:
    """Una copia guardada en el borde. Entra al guardarla; no sale del borde.

    version y contenido son los que entregó el origen. guardada_en es
    time.time() al guardar o al renovar; expira_en = guardada_en + TTL.
    Antes de expira_en la copia está fresca; después, obsoleta.
    invalidada la saca de servicio sin borrarla: no se devuelve.
    """

    version: int
    contenido: bytes
    guardada_en: float
    expira_en: float
    invalidada: bool = False

    def fresca(self, ahora: float) -> bool:
        """True si todavía no pasó el TTL."""
        return ahora < self.expira_en


def _hora(t: float) -> str:
    """Hora legible para el historial (misma forma que registrar)."""
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


@ray.remote
class Borde:
    """Caché de borde.

    Entra (al crearlo): nombre del nodo ("borde-1"), el handle del actor
    origen y la Config (TTL, capacidad, política).
    Sale: listo(), pedir(...), estado(), perder_avisos(...) e invalidar(...).
    Si el otro nodo no contesta: el único «otro nodo» al que llama es el
    origen, desde pedir; por ahora esa llamada espera sin límite. El tiempo
    de espera y la regla de obsoleto llegan con F1-S09. invalidar no llama
    a nadie: es el aviso que llega desde el origen.
    """

    def __init__(self, nombre: str, origen: Any, config: Config) -> None:
        self.nombre = nombre
        self.origen = origen
        self.cfg = config
        # recurso -> Copia, en orden de uso: la primera es la menos usada
        # recientemente (LRU). Un hit o un guardado mueven la copia al final.
        # Solo vive en la memoria del actor: si el borde muere, arranca vacío
        # y el primer pedido vuelve a ser miss.
        self._copias: "OrderedDict[str, Copia]" = OrderedDict()
        # Simulación de F1-R07: Ray entrega la llamada si el actor vive.
        # Con esto activo, invalidar no marca la copia y anota el aviso perdido.
        self._pierde_avisos = False

    # ----------------------------------------------------------------- arranque

    def listo(self) -> str:
        """Confirma que el borde vive y deja una línea en el historial.

        Entra: nada. Sale: el nombre del nodo. Si el otro nodo no contesta: no aplica.
        """
        registrar(self.nombre, "arranque", "listo", capacidad=self.cfg.capacidad,
                  politica=self.cfg.expulsion, ttl=int(self.cfg.ttl_segundos),
                  stale_limit=int(self.cfg.stale_limit_segundos))
        return self.nombre

    # ------------------------------------------------------------------- pedido

    def pedir(self, pedido_id: str, recurso: str) -> Dict[str, Any]:
        """Atiende un pedido del cliente: hit si hay copia fresca y válida.

        Entra: pedido_id (lo creó el cliente) y el nombre del recurso.
        Sale: dict con resultado (hit, miss o file_doesnt_exist), version y
        contenido, con el formato de docs/contrato.md.
        Si el otro nodo no contesta: espera (sin tiempo límite hasta F1-S09).
        Una copia invalidada no se devuelve: se anota miss causa=invalidada
        y se pregunta al origen.
        """
        ahora = time.time()
        copia = self._copias.get(recurso)

        # 1. Copia fresca y no invalidada: hit, sin hablar con el origen.
        #    Cuenta como uso reciente para LRU.
        if copia is not None and not copia.invalidada and copia.fresca(ahora):
            self._copias.move_to_end(recurso)
            registrar(self.nombre, pedido_id, "hit", recurso=recurso,
                      version=copia.version, estado="fresca")
            return self._respuesta("hit", copia)

        # 2. No hay copia usable: miss con su causa.
        if copia is None:
            registrar(self.nombre, pedido_id, "miss", recurso=recurso, causa="no_esta")
            registrar(self.nombre, pedido_id, "pide_origen", recurso=recurso)
        elif copia.invalidada:
            registrar(self.nombre, pedido_id, "miss", recurso=recurso, causa="invalidada",
                      version=copia.version)
            registrar(self.nombre, pedido_id, "pide_origen", recurso=recurso,
                      version=copia.version)
        else:
            registrar(self.nombre, pedido_id, "miss", recurso=recurso, causa="expirada",
                      version=copia.version, expiro=_hora(copia.expira_en),
                      edad_segundos=int(ahora - copia.expira_en))
            registrar(self.nombre, pedido_id, "pide_origen", recurso=recurso,
                      version=copia.version)

        # 3. Pedir al origen. (Sin tiempo de espera hasta F1-S09.)
        r = ray.get(self.origen.responder.remote(pedido_id, recurso))
        return self._con_respuesta_del_origen(pedido_id, recurso, copia, r)

    # ------------------------------------------------------------------ estado

    def estado(self) -> Dict[str, Dict[str, Any]]:
        """Qué copias hay y en qué estado, para pruebas y para el experimento.

        Entra: nada. Sale: recurso -> {version, estado, expira, edad_obsoleta},
        en orden LRU (la primera es la próxima en salir). estado es
        invalidada, fresca u obsoleta. Vacío si no hay copias.
        """
        ahora = time.time()
        return {
            rec: {
                "version": c.version,
                "estado": (
                    "invalidada" if c.invalidada
                    else "fresca" if c.fresca(ahora) else "obsoleta"
                ),
                "expira": _hora(c.expira_en),
                "edad_obsoleta": max(0, int(ahora - c.expira_en)),
            }
            for rec, c in self._copias.items()
        }

    def perder_avisos(self, activo: bool) -> bool:
        """Simula que este borde no aplica los avisos de invalidación.

        Entra: True para no aplicarlos, False para volver a aplicarlos.
        Sale: el valor que quedó guardado.
        Si el otro nodo no contesta: no aplica; no llama a nadie.
        La copia que ya está se queda válida y el siguiente pedido la sirve
        si sigue fresca. No es un borde muerto: el cliente puede seguir pidiendo.
        """
        self._pierde_avisos = activo
        return self._pierde_avisos

    def invalidar(self, pedido_id: str, recurso: str, version: Optional[int]) -> Optional[str]:
        """El origen avisa que la copia de este recurso ya no vale.

        Entra: pedido_id, nombre del recurso y la versión de referencia
        (None si el archivo ya no está en el origen).
        Sale: el nombre de este borde si aplicó el aviso, o None si no lo
        aplicó (perder_avisos). El origen solo cuenta el nombre como avisado.
        Si el otro nodo no contesta: no aplica; esta llamada es la que recibe.
        Si aplica, la copia se marca invalidada y no se devuelve. Si no
        aplica, sigue válida y se anota invalidacion_perdida.
        """
        if self._pierde_avisos:
            copia = self._copias.get(recurso)
            datos: Dict[str, Any] = {"recurso": recurso}
            if copia is not None:
                datos["version"] = copia.version
            registrar(self.nombre, pedido_id, "invalidacion_perdida", **datos)
            return None
        copia = self._copias.get(recurso)
        if copia is not None:
            copia.invalidada = True
        datos = {"recurso": recurso}
        if version is not None:
            datos["version"] = version
        elif copia is not None:
            datos["version"] = copia.version
        registrar(self.nombre, pedido_id, "invalidacion_recibida", **datos)
        return self.nombre

    # ----------------------------------------------------------------- internos

    def _con_respuesta_del_origen(self, pedido_id: str, recurso: str,
                                  copia: Optional[Copia], r: Dict[str, Any]) -> Dict[str, Any]:
        """El origen contestó. Decide entre file_doesnt_exist, hit renovado y miss."""
        # a. El origen dice que el archivo no existe: contrato, se borra la
        #    copia de ese nombre si la hubiera, y no hay versión ni contenido.
        if not r.get("existe"):
            vieja = self._copias.pop(recurso, None)
            if vieja is not None:
                registrar(self.nombre, pedido_id, "borra", recurso=recurso,
                          version=vieja.version, causa="file_doesnt_exist")
            return {"resultado": "file_doesnt_exist", "version": None, "contenido": None}

        # b. Había copia expirada y el origen confirma la misma versión: la
        #    copia sigue, el TTL vuelve a empezar y el cliente ve hit (contrato,
        #    «Frescura»; decisión del 16 nov «Misma versión en la revalidación
        #    es hit»). Es la revalidación mínima: hoy baja el archivo entero
        #    para saber la versión. responder ya acepta version_local
        #    (F1-R08): si coincide, no manda bytes. F1-S08 es quien pasa
        #    copia.version y trata el campo misma.
        #    Se compara con igualdad, no con «mayor que»: el origen manda y
        #    los números son etiquetas (si el origen reinicia y vuelve a 1,
        #    el borde reemplaza su copia por lo que el origen dice).
        # Una copia invalidada no se renueva como hit: el cliente no recibe
        # esos bytes. Lo que mande el origen se guarda como copia nueva (miss).
        if copia is not None and not copia.invalidada and copia.version == r["version"]:
            self._renovar(recurso, copia)
            registrar(self.nombre, pedido_id, "revalida", recurso=recurso,
                      version_local=copia.version, version_origen=r["version"],
                      renovo="si", expira=_hora(copia.expira_en))
            registrar(self.nombre, pedido_id, "hit", recurso=recurso,
                      version=copia.version, estado="fresca")
            return self._respuesta("hit", copia)

        # c. El origen entregó otra versión, o la copia estaba invalidada:
        #    se guarda lo que mandó el origen y se responde miss. bajo_otra
        #    solo si el número de versión cambió.
        if copia is not None:
            datos_rev: Dict[str, Any] = {
                "recurso": recurso,
                "version_local": copia.version,
                "version_origen": r["version"],
                "renovo": "no",
            }
            if copia.version != r["version"]:
                datos_rev["bajo_otra"] = "si"
            registrar(self.nombre, pedido_id, "revalida", **datos_rev)
        nueva = self._guardar(pedido_id, recurso, r["version"], r["contenido"])
        return self._respuesta("miss", nueva)

    def _respuesta(self, resultado: str, copia: Copia) -> Dict[str, Any]:
        """Arma la respuesta del contrato a partir de una copia."""
        return {"resultado": resultado, "version": copia.version, "contenido": copia.contenido}

    def _renovar(self, recurso: str, copia: Copia) -> None:
        """La copia sigue siendo la actual: el TTL vuelve a contar desde ahora."""
        copia.guardada_en = time.time()
        copia.expira_en = copia.guardada_en + self.cfg.ttl_segundos
        self._copias.move_to_end(recurso)

    def _guardar(self, pedido_id: str, recurso: str, version: int, contenido: bytes) -> Copia:
        """Guarda (o reemplaza) la copia y anota guarda. Si el borde está
        lleno y el recurso es nuevo, expulsa primero la copia menos usada
        recientemente y anota expulsion. LRU no mira el estado: una copia
        obsoleta se queda guardada hasta que el origen hable, la invalide
        o la expulse esto (decisión del 16 nov «Cuándo el borde borra»)."""
        if recurso in self._copias:
            # Reemplazo: no cambia cuántas copias hay, no hace falta expulsar.
            del self._copias[recurso]
        elif len(self._copias) >= self.cfg.capacidad:
            sale, vieja = self._copias.popitem(last=False)
            registrar(self.nombre, pedido_id, "expulsion", recurso=sale,
                      version=vieja.version, politica=self.cfg.expulsion, entra=recurso)
        ahora = time.time()
        copia = Copia(version=version, contenido=contenido, guardada_en=ahora,
                      expira_en=ahora + self.cfg.ttl_segundos)
        self._copias[recurso] = copia
        registrar(self.nombre, pedido_id, "guarda", recurso=recurso, version=version,
                  bytes=len(contenido), expira=_hora(copia.expira_en))
        return copia
