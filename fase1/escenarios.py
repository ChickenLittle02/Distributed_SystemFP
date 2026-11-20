"""Escenarios de prueba del borde, del selector y de la invalidación.

Responsabilidad: levantar origen, dos bordes y cliente (como
fase1/arrancar_sistema.py) y provocar, uno por uno, los comportamientos
que el tablero pide ver en el historial: expiración por TTL, expulsión
LRU, el paso a otro borde cuando uno no responde, y la invalidación que
sale del origen hacia los dos bordes (F1-R06).
No es la corrida del checklist (F1-J06): esa se arma cuando el borde tenga
la regla de obsoleto. No decide nada: solo pide y muestra lo que anotan
los nodos. No simula un aviso perdido (F1-R07).

Cómo se corre, desde la raíz del repositorio:

    python3 -m fase1.escenarios ttl        # espera el TTL y vuelve a pedir
    python3 -m fase1.escenarios lru        # tres recursos en un borde de 2
    python3 -m fase1.escenarios selector   # mata borde-1 y pide otra vez
    python3 -m fase1.escenarios invalidar  # el origen avisa a los dos bordes
    python3 -m fase1.escenarios todos      # los cuatro seguidos

Para no esperar los 30 s del TTL provisional: P20_TTL=3.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict

import ray

from fase1.borde import Borde
from fase1.cliente import Cliente
from fase1.config import Config
from fase1.origen import Origen


def _mostrar(r: Dict[str, Any]) -> None:
    """Imprime en una línea lo que devolvió el cliente para un pedido."""
    print(f"  => pedido={r['pedido_id']} resultado={r['resultado']} version={r['version']} "
          f"fuente={r['fuente']} bytes={len(r['contenido'] or b'')}", flush=True)


def _arrancar(cfg: Config):
    """Crea origen, los bordes de la configuración y el cliente; espera sus listo."""
    origen = Origen.remote()
    bordes = {nombre: Borde.remote(nombre, origen, cfg) for nombre in cfg.bordes}
    ray.get(origen.anotar_bordes.remote(bordes))
    cliente = Cliente.remote("cliente", bordes, cfg)
    ray.get([origen.listo.remote(), cliente.listo.remote()]
            + [b.listo.remote() for b in bordes.values()])
    return origen, bordes, cliente


def escenario_ttl(cfg: Config) -> None:
    """F1-S05: miss, hit fresca, espera el TTL, miss causa=expirada y revalida.

    Entra: la Config. Sale: imprime los pedidos y el estado del borde antes
    y después de expirar. Si el otro nodo no contesta: el pedido se queda
    esperando (no hay timeout al origen hasta F1-S09).
    """
    print(f"=== TTL: una copia está fresca {cfg.ttl_segundos:g} s y después queda obsoleta", flush=True)
    origen, bordes, cliente = _arrancar(cfg)
    preferido = bordes[cfg.bordes[0]]
    print("--- pedido 1: no está (miss, guarda con expira)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    print("--- pedido 2: copia fresca (hit estado=fresca)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    print(f"    estado: {ray.get(preferido.estado.remote())}", flush=True)
    espera = cfg.ttl_segundos + 1
    print(f"--- esperando {espera:g} s a que expire...", flush=True)
    time.sleep(espera)
    print(f"    estado: {ray.get(preferido.estado.remote())}", flush=True)
    print("--- pedido 3: copia obsoleta (miss causa=expirada, pide_origen con versión,"
          " revalida renovo=si, hit)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    print(f"    estado: {ray.get(preferido.estado.remote())}", flush=True)


def escenario_lru(cfg: Config) -> None:
    """F1-S06: con capacidad 2, el tercer recurso expulsa al menos usado.

    Entra: la Config (capacidad 2 por defecto). Sale: imprime los pedidos y
    el estado del borde en orden LRU. Si el otro nodo no contesta: igual
    que arriba.
    """
    print(f"=== LRU: el borde guarda {cfg.capacidad} copias; la tercera expulsa", flush=True)
    origen, bordes, cliente = _arrancar(cfg)
    preferido = bordes[cfg.bordes[0]]
    print("--- apunte.txt y apunte-2.txt: dos miss, el borde queda lleno", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    _mostrar(ray.get(cliente.pedir.remote("apunte-2.txt")))
    print("--- apunte.txt otra vez: hit; pasa a ser la más usada", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    print(f"    estado (orden LRU, la primera es la próxima en salir): "
          f"{list(ray.get(preferido.estado.remote()))}", flush=True)
    print("--- apunte-3.txt: miss; expulsion de apunte-2.txt (la menos usada), guarda", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte-3.txt")))
    print(f"    estado: {list(ray.get(preferido.estado.remote()))}", flush=True)
    print("--- apunte-2.txt otra vez: ya no está (miss causa=no_esta); sale apunte.txt", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte-2.txt")))
    print(f"    estado: {list(ray.get(preferido.estado.remote()))}", flush=True)


def escenario_selector(cfg: Config) -> None:
    """F1-S07: borde-1 muere; el cliente anota nodo_caido y usa borde-2.

    Entra: la Config. Sale: imprime los pedidos; el segundo lo resuelve
    borde-2. Si el otro nodo no contesta: eso es lo que se prueba.
    """
    print("=== Selector: si el borde preferido no responde, el cliente usa el otro", flush=True)
    origen, bordes, cliente = _arrancar(cfg)
    primero, segundo = cfg.bordes[0], cfg.bordes[1]
    print(f"--- pedido 1: lo atiende {primero} (miss)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    print(f"--- se mata el actor de {primero} (ray.kill): deja de responder", flush=True)
    ray.kill(bordes[primero])
    time.sleep(0.5)
    print(f"--- pedido 2: solicitud a {primero}, nodo_caido, solicitud a {segundo} (miss)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    print(f"--- pedido 3: {primero} sigue evitado {cfg.evitar_borde_segundos:g} s;"
          f" va directo a {segundo} (hit)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))


def escenario_invalidar(cfg: Config) -> None:
    """F1-R06: el origen avisa a los dos bordes y el historial lleva la lista.

    Entra: la Config. Sale: imprime el estado de cada borde antes y después
    del aviso, la lista de avisados y el pedido que baja la versión nueva.
    Si el otro nodo no contesta: ese borde no saldría en la lista; este
    escenario no apaga a nadie. El aviso perdido es F1-R07.
    """
    print("=== Invalidar: el origen avisa a los dos bordes y anota la lista", flush=True)
    origen, bordes, cliente = _arrancar(cfg)
    ruta = Path(__file__).resolve().parent.parent / "contenido" / "apunte-inv.txt"
    try:
        ruta.write_text("archivo para invalidar\n", encoding="utf-8")
        print("--- los dos bordes bajan apunte-inv.txt (version 1) y lo guardan", flush=True)
        for nombre, borde in bordes.items():
            r = ray.get(borde.pedir.remote(f"previo-{nombre}", "apunte-inv.txt"))
            print(f"  {nombre}: resultado={r['resultado']} version={r['version']}", flush=True)
        print("--- estado antes del aviso:", flush=True)
        for nombre, borde in bordes.items():
            print(f"    {nombre}: {list(ray.get(borde.estado.remote()))}", flush=True)
        ruta.write_text("archivo para invalidar, version nueva\n", encoding="utf-8")
        print("--- el origen invalida: versión nueva y bordes que contestaron", flush=True)
        aviso = ray.get(origen.invalidar.remote("inv-1", "apunte-inv.txt"))
        print(f"  => version={aviso['version']} bordes={aviso['bordes']}", flush=True)
        print("--- estado después: la copia ya no está en ningún borde", flush=True)
        for nombre, borde in bordes.items():
            print(f"    {nombre}: {list(ray.get(borde.estado.remote()))}", flush=True)
        print("--- el siguiente pedido baja la versión nueva (miss)", flush=True)
        _mostrar(ray.get(cliente.pedir.remote("apunte-inv.txt")))
    finally:
        ruta.unlink(missing_ok=True)


ESCENARIOS = {
    "ttl": escenario_ttl,
    "lru": escenario_lru,
    "selector": escenario_selector,
    "invalidar": escenario_invalidar,
}


def main(argv) -> int:
    """Corre el escenario pedido (o todos). Entra: argv. Sale: código de salida."""
    nombres = argv[1:] or ["todos"]
    if nombres == ["todos"]:
        nombres = list(ESCENARIOS)
    desconocidos = [n for n in nombres if n not in ESCENARIOS]
    if desconocidos:
        print(f"escenario desconocido: {desconocidos}. Opciones: {list(ESCENARIOS)} o todos")
        return 2
    cfg = Config.desde_entorno()
    for nombre in nombres:
        ray.init(ignore_reinit_error=True)
        ESCENARIOS[nombre](cfg)
        ray.shutdown()
        print(flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
