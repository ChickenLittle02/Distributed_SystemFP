"""Corrida repetible del checklist de la fase 1 (F1-J06).

Responsabilidad: correr seguidos el arranque del sistema y los escenarios
de fase1/escenarios.py, leer solo las líneas que esa corrida dejó en
logs/, y decir, uno por uno, si los diez comportamientos del tablero
quedaron en el historial (y los cinco resultados del cliente, F1-J05).
Imprime una tabla con la línea que sirve de evidencia y termina con
código 1 si falta alguno.
No decide nada del sistema: solo pide y lee el historial. No borra logs/:
distingue lo nuevo por el tamaño que tenía cada archivo al empezar.

Cómo se corre, desde la raíz del repositorio (tarda alrededor de un minuto):

    python3 -m fase1.checklist

Usa TTL=3 s y STALE_LIMIT=4 s salvo que P20_TTL / P20_STALE_LIMIT ya
estén puestos; con los 30 y 60 s provisionales tardaría varios minutos.
Al final muestra el recorrido de un pedido filtrado por pedido_id (F1-J02).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Valores cortos para la corrida, antes de leer la configuración.
os.environ.setdefault("P20_TTL", "3")
os.environ.setdefault("P20_STALE_LIMIT", "4")

import ray  # noqa: E402

from fase1 import arrancar_sistema, escenarios  # noqa: E402
from fase1.config import Config  # noqa: E402
from fase1.registro import registrar  # noqa: E402

_RAIZ = Path(__file__).resolve().parent.parent
_DIR_LOGS = _RAIZ / "logs"
_NODOS = ["origen", "borde-1", "borde-2", "cliente"]

# Qué escenarios forman la corrida, en orden.
_PASOS = ["sistema", "ttl", "lru", "selector", "invalidar", "perdida", "obsoleto", "invalidada"]

# Los diez comportamientos del tablero, cada uno con las líneas que lo
# prueban: (nodo, expresión regular). Todas tienen que aparecer.
_COMPORTAMIENTOS: List[Tuple[str, List[Tuple[str, str]]]] = [
    ("Hit de una copia fresca",
     [("borde-1", r"hit recurso=apunte\.txt version=1 estado=fresca")]),
    ("Miss si no está, y bajada desde el origen",
     [("borde-1", r"miss recurso=apunte\.txt causa=no_esta"),
      ("borde-1", r"pide_origen recurso=apunte\.txt$"),
      ("origen", r"responde recurso=apunte\.txt version=1$"),
      ("borde-1", r"guarda recurso=apunte\.txt version=1 bytes=\d+ expira=")]),
    ("Versión y expiración por TTL",
     [("borde-1", r"guarda recurso=apunte\.txt version=1 .*expira=\d\d:\d\d:\d\d"),
      ("borde-1", r"miss recurso=apunte\.txt causa=expirada version=1 expiro=.* edad_segundos=\d+")]),
    ("Expulsión LRU cuando el borde se llena",
     [("borde-1", r"expulsion recurso=apunte-2\.txt version=1 politica=LRU entra=apunte-3\.txt")]),
    ("Invalidación que llega a los dos bordes",
     [("origen", r"invalidar recurso=apunte-inv\.txt version=2 bordes=borde-1,borde-2"),
      ("borde-1", r"invalidacion_recibida recurso=apunte-inv\.txt .*habia_copia=si"),
      ("borde-2", r"invalidacion_recibida recurso=apunte-inv\.txt .*habia_copia=si"),
      ("borde-1", r"miss recurso=apunte-inv\.txt causa=invalidada")]),
    ("Un borde no aplica la invalidación, y eso queda anotado",
     [("borde-2", r"invalidacion_perdida recurso=apunte-inv\.txt"),
      ("origen", r"invalidar recurso=apunte-inv\.txt version=2 bordes=borde-1$"),
      ("borde-2", r"hit recurso=apunte-inv\.txt version=1 estado=fresca")]),
    ("Revalidación cuando la copia expiró y el origen responde",
     [("borde-1", r"pide_origen recurso=apunte\.txt version=1"),
      ("origen", r"responde recurso=apunte\.txt version=1 misma=si"),
      ("borde-1", r"revalida recurso=apunte\.txt version_local=1 version_origen=1 renovo=si")]),
    ("Un borde no responde y el selector usa el otro",
     [("cliente", r"nodo_caido destino=borde-1"),
      ("cliente", r"solicitud recurso=apunte\.txt fuente=borde-2"),
      ("cliente", r"respuesta version=1 resultado=miss fuente=borde-2")]),
    ("Origen inalcanzable: sirve dentro de STALE_LIMIT, rechaza fuera",
     [("borde-1", r"timeout destino=origen causa=particion"),
      ("borde-1", r"origen_no_responde recurso=apunte\.txt version=1 edad_segundos=\d+ stale_limit=4"),
      ("borde-1", r"sirve_obsoleta recurso=apunte\.txt version=1 edad_segundos=\d+ stale_limit=4"),
      ("borde-1", r"rechaza recurso=apunte\.txt causa=supera_limite version=1 edad_segundos=\d+ stale_limit=4"),
      ("borde-1", r"rechaza recurso=apunte-inv\.txt causa=invalidada")]),
    ("registrar desde la primera operación. cifrado = false",
     [("origen", r"^PRIMERA listo"),
      ("borde-1", r"^PRIMERA listo"),
      ("borde-2", r"^PRIMERA listo"),
      ("cliente", r"^PRIMERA listo"),
      ("checklist", r"config cifrado=false")]),
]

# Los cinco resultados que el cliente tiene que haber anotado (F1-J05).
_RESULTADOS = ["hit", "miss", "sirve_obsoleta", "rechaza", "file_doesnt_exist"]


def _tamanos() -> Dict[str, int]:
    """Cuánto ocupa hoy cada log: desde ahí se leen las líneas de esta corrida."""
    _DIR_LOGS.mkdir(parents=True, exist_ok=True)
    return {n: (_DIR_LOGS / f"{n}.log").stat().st_size
            if (_DIR_LOGS / f"{n}.log").exists() else 0
            for n in _NODOS + ["checklist"]}


def _nuevas(tamanos: Dict[str, int]) -> Dict[str, List[str]]:
    """Las líneas que cada nodo escribió después de tamanos."""
    salida: Dict[str, List[str]] = {}
    for n, desde in tamanos.items():
        ruta = _DIR_LOGS / f"{n}.log"
        if not ruta.exists():
            salida[n] = []
            continue
        with ruta.open("rb") as f:
            f.seek(desde)
            texto = f.read().decode("utf-8", errors="replace")
        salida[n] = [l for l in texto.splitlines() if l.strip()]
    return salida


def _buscar(lineas: List[str], patron: str) -> Optional[str]:
    """La primera línea que cumple el patrón (sin hora, nodo ni pedido), o None.

    El patrón especial ^PRIMERA <op> exige que la primera línea nueva del
    nodo sea esa operación: es la prueba de «desde la primera operación».
    """
    if patron.startswith("^PRIMERA "):
        op = patron[len("^PRIMERA "):]
        if lineas and re.match(rf"\S+ \S+ pedido=\S+ {op}\b", lineas[0]):
            return lineas[0]
        return None
    for l in lineas:
        resto = re.sub(r"^\S+ \S+ pedido=\S+ ", "", l)
        if re.search(patron, resto):
            return l
    return None


def _correr(cfg: Config) -> None:
    """Corre los pasos de _PASOS, cada uno con su propio ray.init / shutdown."""
    registrar("checklist", "arranque", "config", cifrado=str(cfg.cifrado).lower(),
              ttl=int(cfg.ttl_segundos), stale_limit=int(cfg.stale_limit_segundos),
              capacidad=cfg.capacidad, timeout=cfg.timeout_segundos)
    for paso in _PASOS:
        print(f"\n##### paso: {paso}", flush=True)
        if paso == "sistema":
            arrancar_sistema.main()
            continue
        ray.init(ignore_reinit_error=True)
        escenarios.ESCENARIOS[paso](cfg)
        ray.shutdown()


def _recorrido_de_un_pedido(lineas: Dict[str, List[str]]) -> None:
    """F1-J02: el primer miss del cliente, seguido por su pedido_id en todos los logs."""
    for l in lineas["cliente"]:
        m = re.search(r"pedido=(\S+) respuesta .*resultado=miss", l)
        if m:
            pid = m.group(1)
            break
    else:
        return
    print(f"\nRecorrido de un pedido (F1-J02): grep \"pedido={pid}\" logs/*.log")
    todas = [l for n in _NODOS for l in lineas[n] if f"pedido={pid} " in l]
    for l in sorted(todas):
        print("  " + l)


def main() -> int:
    """Corre todo, comprueba el historial y devuelve 0 si los diez pasan."""
    cfg = Config.desde_entorno()
    antes = _tamanos()
    _correr(cfg)
    lineas = _nuevas(antes)

    print("\n" + "=" * 78)
    print("CHECKLIST DE LA FASE 1 (F1-J06)")
    print("=" * 78)
    fallos = 0
    for i, (nombre, pruebas) in enumerate(_COMPORTAMIENTOS, 1):
        evidencia: List[str] = []
        faltan: List[str] = []
        for nodo, patron in pruebas:
            hallada = _buscar(lineas.get(nodo, []), patron)
            if hallada is None:
                faltan.append(f"{nodo}: /{patron}/")
            else:
                evidencia.append(hallada)
        ok = not faltan
        fallos += 0 if ok else 1
        print(f"\n[{'x' if ok else ' '}] {i:>2}. {nombre}")
        for l in evidencia:
            print(f"       {l}")
        for f in faltan:
            print(f"       FALTA {f}")

    print("\n" + "-" * 78)
    vistos = {r for l in lineas["cliente"] for r in _RESULTADOS
              if re.search(rf"respuesta .*resultado={r}\b", l)}
    faltan_res = [r for r in _RESULTADOS if r not in vistos]
    print(f"[{'x' if not faltan_res else ' '}] F1-J05 resultados del cliente: "
          + ", ".join(f"{r}{'' if r in vistos else ' (FALTA)'}" for r in _RESULTADOS))
    fallos += 1 if faltan_res else 0

    _recorrido_de_un_pedido(lineas)

    print("\n" + "=" * 78)
    if fallos:
        print(f"FALLAN {fallos} comprobaciones. Anotarlo en schedule.md (F1-J06) y corregir.")
        return 1
    print("Los diez comportamientos y los cinco resultados están en el historial.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
