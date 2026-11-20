"""Actor borde: la caché cercana al cliente (F1-S04 a S09; avisos F1-R06, R07).

Responsabilidad: guardar copias de los recursos con su versión y su
expiración (TTL), decidir hit o miss, pedir al origen cuando no hay copia
usable, guardar lo que baja, expulsar por LRU cuando el borde se llena,
aplicar el aviso de invalidación (la copia queda marcada y no se sirve) y,
cuando el origen no contesta, aplicar la regla de contenido obsoleto:
sirve_obsoleta si la copia no está invalidada y lleva obsoleta como mucho
STALE_LIMIT, rechaza en otro caso.
Anota cada decisión con registrar: hit, miss (con causa), pide_origen,
revalida, guarda, expulsion, borra, invalidacion_recibida,
invalidacion_perdida, timeout, nodo_caido, origen_no_responde,
sirve_obsoleta, rechaza, particion.
«El origen no responde» es una de tres cosas, cada una con su línea: la
llamada no vuelve en timeout_segundos (timeout), el actor origen murió
(nodo_caido), o la partición simulada está activa (timeout causa=particion).
Al revalidar una copia expirada manda su versión al origen (F1-S08 con
F1-R08): si el origen contesta misma=True no viajan bytes y la copia se
renueva. Una copia invalidada nunca se renueva: se pide el archivo entero
y lo que mande el origen la reemplaza (decisión de Rubén del 19 nov).
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
from ray.exceptions import RayActorError, RayError

from fase1.config import Config
from fase1.registro import registrar


@dataclass
class Copia:
    """Una copia guardada en el borde. Entra al guardarla; no sale del borde.

    version y contenido son los que entregó el origen. guardada_en es
    time.time() al guardar o al renovar; expira_en = guardada_en + TTL.
    Antes de expira_en la copia está fresca; después, obsoleta.
    invalidada: el origen avisó que esta versión ya no vale. No se sirve
    nunca, ni dentro de STALE_LIMIT (decisión del 16 nov), ni se renueva
    como hit. Se queda para que el historial diga causa=invalidada y para
    que lo que mande el origen la reemplace.
    """

    version: int
    contenido: bytes
    guardada_en: float
    expira_en: float
    invalidada: bool = False

    def fresca(self, ahora: float) -> bool:
        """True si todavía no pasó el TTL (sin mirar la invalidación)."""
        return ahora < self.expira_en

    def usable(self, ahora: float) -> bool:
        """True si se puede servir como hit: fresca y no invalidada."""
        return self.fresca(ahora) and not self.invalidada

    def estado(self, ahora: float) -> str:
        """invalidada, fresca u obsoleta."""
        if self.invalidada:
            return "invalidada"
        return "fresca" if self.fresca(ahora) else "obsoleta"


def _hora(t: float) -> str:
    """Hora legible para el historial (misma forma que registrar)."""
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


@ray.remote
class Borde:
    """Caché de borde.

    Entra (al crearlo): nombre del nodo ("borde-1"), el handle del actor
    origen y la Config (TTL, STALE_LIMIT, capacidad, política, timeout).
    Sale: listo(), pedir(...), estado(), invalidar(...), perder_avisos(...)
    y particion(...).
    Si el otro nodo no contesta: el único «otro nodo» al que llama es el
    origen, desde pedir. Si no contesta en timeout_segundos, si murió, o si
    la partición simulada está activa, aplica la regla de obsoleto sobre su
    copia. invalidar no llama a nadie: es el aviso que llega desde el origen.
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
        # Simulación de la partición borde→origen (F1-S09, F1-R09): con esto
        # activo el borde no llama al origen y lo trata como «no responde».
        # El cliente sigue llegando: el camino cliente→borde no se corta.
        self._partido = False

    # ----------------------------------------------------------------- arranque

    def listo(self) -> str:
        """Confirma que el borde vive y deja una línea en el historial.

        Entra: nada. Sale: el nombre del nodo. Si el otro nodo no contesta: no aplica.
        """
        registrar(self.nombre, "arranque", "listo", capacidad=self.cfg.capacidad,
                  politica=self.cfg.expulsion, ttl=int(self.cfg.ttl_segundos),
                  stale_limit=int(self.cfg.stale_limit_segundos),
                  timeout=self.cfg.timeout_segundos)
        return self.nombre

    # ------------------------------------------------------------------- pedido

    def pedir(self, pedido_id: str, recurso: str) -> Dict[str, Any]:
        """Atiende un pedido del cliente y decide qué rama de la regla se toma.

        Entra: pedido_id (lo creó el cliente) y el nombre del recurso.
        Sale: dict con resultado (hit, miss, sirve_obsoleta, rechaza o
        file_doesnt_exist), version y contenido, con el formato de
        docs/contrato.md. rechaza y file_doesnt_exist van sin versión ni bytes.
        Si el otro nodo no contesta: si el origen no responde en
        timeout_segundos (o murió, o hay partición), aplica STALE_LIMIT sobre
        la copia local: sirve_obsoleta o rechaza.
        """
        ahora = time.time()
        copia = self._copias.get(recurso)

        # 1. Copia fresca y no invalidada: hit, sin hablar con el origen.
        #    Cuenta como uso reciente para LRU.
        if copia is not None and copia.usable(ahora):
            self._copias.move_to_end(recurso)
            registrar(self.nombre, pedido_id, "hit", recurso=recurso,
                      version=copia.version, estado="fresca")
            return self._respuesta("hit", copia)

        # 2. No hay copia usable: miss con su causa (README, «Qué se anota»).
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

        # 3. Pedir al origen, con tiempo de espera. Si la copia solo expiró,
        #    se manda su versión (revalidación, F1-S08): el origen contesta
        #    misma=True sin bytes si no cambió. Si está invalidada o no hay
        #    copia, se pide el archivo entero.
        version_local = copia.version if copia is not None and not copia.invalidada else None
        r = self._hablar_con_origen(pedido_id, recurso, version_local)
        if r is not None:
            return self._con_respuesta_del_origen(pedido_id, recurso, copia, r)

        # 4. El origen no contestó: regla de contenido obsoleto.
        return self._sin_origen(pedido_id, recurso, copia, ahora)

    # ------------------------------------------------------------ invalidación

    def perder_avisos(self, activo: bool) -> bool:
        """Simula que este borde no aplica los avisos de invalidación (F1-R07).

        Entra: True para no aplicarlos, False para volver a aplicarlos.
        Sale: el valor que quedó guardado.
        Si el otro nodo no contesta: no aplica; no llama a nadie.
        La copia que ya está se queda sin marcar y el siguiente pedido la
        sirve si sigue fresca. No es un borde muerto: el cliente puede seguir pidiendo.
        """
        self._pierde_avisos = activo
        return self._pierde_avisos

    def invalidar(self, pedido_id: str, recurso: str, version: Optional[int]) -> Optional[str]:
        """El origen avisa que la copia de este recurso ya no vale: queda marcada.

        Entra: pedido_id, nombre del recurso y la versión de referencia
        (None si el archivo ya no está en el origen).
        Sale: el nombre de este borde si aplicó el aviso, o None si no lo
        aplicó (perder_avisos). El origen solo cuenta el nombre como avisado.
        Si el otro nodo no contesta: no aplica; esta llamada es la que recibe.
        Si aplica y había copia, la copia se queda con invalidada=True: no
        se sirve nunca, el siguiente pedido anota miss causa=invalidada y
        pide el archivo entero al origen (lo que mande la reemplaza); si el
        origen calla, rechaza causa=invalidada.
        Si no aplica, la copia sigue válida y se anota invalidacion_perdida.
        """
        copia = self._copias.get(recurso)
        datos: Dict[str, Any] = {"recurso": recurso}
        if copia is not None:
            datos["version_local"] = copia.version
        if version is not None:
            datos["version"] = version
        if self._pierde_avisos:
            registrar(self.nombre, pedido_id, "invalidacion_perdida", **datos)
            return None
        datos["habia_copia"] = "si" if copia is not None else "no"
        if copia is not None:
            copia.invalidada = True
        registrar(self.nombre, pedido_id, "invalidacion_recibida", **datos)
        return self.nombre

    # ---------------------------------------------------------------- partición

    def particion(self, activa: bool) -> bool:
        """Simula el corte entre este borde y el origen (README §9, guía parte 6).

        Entra: True para cortar, False para reparar.
        Sale: el estado nuevo.
        Si el otro nodo no contesta: con el corte activo, el borde no llama
        al origen y lo trata como «no responde» (línea timeout
        causa=particion). El cliente sigue llegando a este borde.
        """
        self._partido = activa
        registrar(self.nombre, "particion", "particion", con="origen",
                  estado="cortada" if activa else "reparada")
        return self._partido

    # ------------------------------------------------------------------ estado

    def estado(self) -> Dict[str, Dict[str, Any]]:
        """Qué copias hay y en qué estado, para pruebas y para el experimento.

        Entra: nada. Sale: recurso -> {version, estado (fresca, obsoleta o
        invalidada), expira, edad_obsoleta}, en orden LRU (la primera es la
        próxima en salir). Vacío si no hay copias.
        """
        ahora = time.time()
        return {
            rec: {
                "version": c.version,
                "estado": c.estado(ahora),
                "expira": _hora(c.expira_en),
                "edad_obsoleta": max(0, int(ahora - c.expira_en)),
            }
            for rec, c in self._copias.items()
        }

    # ----------------------------------------------------------------- internos

    def _hablar_con_origen(self, pedido_id: str, recurso: str,
                           version_local: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Llama al origen con tiempo de espera. None significa «no responde».

        Entra: pedido_id, recurso y, si se revalida, la versión local de la
        copia. Sale: la respuesta del origen o None.
        Con version_local el origen contesta misma=True sin bytes si la
        versión coincide (F1-R08); si no, manda el archivo.
        Cada forma de «no responde» deja su línea: timeout (la llamada no
        volvió en timeout_segundos), nodo_caido (el actor murió) o timeout
        causa=particion (corte simulado). Ray no reintenta la llamada y el
        borde tampoco: el reintento es decisión de la regla de obsoleto.
        """
        if self._partido:
            registrar(self.nombre, pedido_id, "timeout", destino="origen",
                      causa="particion", segundos=self.cfg.timeout_segundos)
            return None
        try:
            ref = self.origen.responder.remote(pedido_id, recurso, version_local)
            listos, _ = ray.wait([ref], timeout=self.cfg.timeout_segundos)
            if not listos:
                registrar(self.nombre, pedido_id, "timeout", destino="origen",
                          segundos=self.cfg.timeout_segundos)
                return None
            return ray.get(listos[0])
        except RayActorError:
            registrar(self.nombre, pedido_id, "nodo_caido", destino="origen")
            return None
        except RayError as e:
            registrar(self.nombre, pedido_id, "nodo_caido", destino="origen",
                      causa=type(e).__name__)
            return None

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

        # b. Había copia expirada y el origen confirma la misma versión
        #    (misma=True, sin bytes, F1-R08): la copia sigue, el TTL vuelve a
        #    empezar y el cliente ve hit (contrato, «Frescura»; decisión del
        #    16 nov «Misma versión en la revalidación es hit»). Una copia
        #    invalidada no entra aquí: nunca se renueva como hit, se pidió el
        #    archivo entero y lo que mande el origen la reemplaza (rama c).
        #    Se compara con igualdad, no con «mayor que»: el origen manda y
        #    los números son etiquetas (si el origen reinicia y vuelve a 1,
        #    el borde reemplaza su copia por lo que el origen dice).
        if (copia is not None and not copia.invalidada
                and (r.get("misma") or copia.version == r["version"])):
            self._renovar(recurso, copia)
            registrar(self.nombre, pedido_id, "revalida", recurso=recurso,
                      version_local=copia.version, version_origen=r["version"],
                      renovo="si", expira=_hora(copia.expira_en))
            registrar(self.nombre, pedido_id, "hit", recurso=recurso,
                      version=copia.version, estado="fresca")
            return self._respuesta("hit", copia)

        # c. El origen entregó otra versión, o la copia estaba invalidada, o
        #    no había copia: se guarda lo que mandó y se responde miss.
        #    bajo_otra solo si el número de versión cambió.
        if copia is not None:
            datos_rev: Dict[str, Any] = {"recurso": recurso, "version_local": copia.version,
                                         "version_origen": r["version"], "renovo": "no"}
            if copia.version != r["version"]:
                datos_rev["bajo_otra"] = "si"
            registrar(self.nombre, pedido_id, "revalida", **datos_rev)
        nueva = self._guardar(pedido_id, recurso, r["version"], r["contenido"])
        return self._respuesta("miss", nueva)

    def _sin_origen(self, pedido_id: str, recurso: str,
                    copia: Optional[Copia], ahora: float) -> Dict[str, Any]:
        """El origen no contestó. Aplica STALE_LIMIT a la copia local, si la hay.

        La edad que se compara es el tiempo que la copia lleva obsoleta
        (desde expira_en), no desde que se guardó (contrato, «Frescura»).
        Una copia invalidada no entra en la regla. La copia que supera el
        límite no se borra: se queda hasta que el origen hable o LRU la saque.
        """
        limite = int(self.cfg.stale_limit_segundos)
        sin = {"resultado": "rechaza", "version": None, "contenido": None}

        if copia is None:
            registrar(self.nombre, pedido_id, "origen_no_responde", recurso=recurso,
                      edad_segundos="sin_copia", stale_limit=limite)
            registrar(self.nombre, pedido_id, "rechaza", recurso=recurso, causa="no_esta")
            return sin

        edad = max(0, int(ahora - copia.expira_en))
        registrar(self.nombre, pedido_id, "origen_no_responde", recurso=recurso,
                  version=copia.version, edad_segundos=edad, stale_limit=limite)

        if copia.invalidada:
            registrar(self.nombre, pedido_id, "rechaza", recurso=recurso,
                      causa="invalidada", version=copia.version)
            return sin

        if edad <= limite:
            registrar(self.nombre, pedido_id, "sirve_obsoleta", recurso=recurso,
                      version=copia.version, edad_segundos=edad, stale_limit=limite)
            return self._respuesta("sirve_obsoleta", copia)

        registrar(self.nombre, pedido_id, "rechaza", recurso=recurso, causa="supera_limite",
                  version=copia.version, edad_segundos=edad, stale_limit=limite)
        return sin

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
        obsoleta o invalidada se queda guardada hasta que el origen hable
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
