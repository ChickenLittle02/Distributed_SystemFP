"""Arranca el sistema completo de la fase 1: origen, dos bordes y un cliente.

Responsabilidad: iniciar Ray, crear los cuatro actores (cada uno en su
proceso), comprobar que viven y hacer tres pedidos de prueba por el
cliente: el mismo recurso dos veces (miss y luego hit) y uno que no existe
(file_doesnt_exist). Al final muestra las copias que quedaron en el borde.
No es la corrida del checklist (F1-J06): esa se arma cuando el borde tenga
TTL, expulsión y la regla de obsoleto.
"""

from __future__ import annotations

from typing import Any, Dict

import ray

from fase1.borde import Borde
from fase1.cliente import Cliente
from fase1.config import Config
from fase1.origen import Origen


def _mostrar(r: Dict[str, Any]) -> None:
    """Imprime en una línea lo que devolvió el cliente para un pedido."""
    print(f"pedido={r['pedido_id']} resultado={r['resultado']} version={r['version']} "
          f"fuente={r['fuente']} bytes={len(r['contenido'] or b'')}", flush=True)


def main() -> None:
    """Crea origen, borde-1, borde-2 y cliente, y hace los tres pedidos de prueba.

    Entra: nada. Sale: imprime los listo, las tres respuestas y el estado
    del borde preferido.
    Si el otro nodo no contesta: si Ray no arranca, el proceso termina con error.
    """
    cfg = Config.desde_entorno()
    ray.init(ignore_reinit_error=True)
    origen = Origen.remote()
    bordes = {nombre: Borde.remote(nombre, origen, cfg) for nombre in cfg.bordes}
    cliente = Cliente.remote("cliente", bordes, cfg)

    print(f"origen listo: {ray.get(origen.listo.remote())}", flush=True)
    for nombre, b in bordes.items():
        print(f"{nombre} listo: {ray.get(b.listo.remote())}", flush=True)
    print(f"cliente listo: {ray.get(cliente.listo.remote())}", flush=True)

    print("--- primer pedido de apunte.txt: el borde no lo tiene (miss)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    print("--- segundo pedido de apunte.txt: el borde ya lo guardó (hit)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("apunte.txt")))
    print("--- pedido de no-existe.txt: el origen dice que no está (file_doesnt_exist)", flush=True)
    _mostrar(ray.get(cliente.pedir.remote("no-existe.txt")))

    preferido = cfg.bordes[0]
    print(f"copias en {preferido}: {ray.get(bordes[preferido].estado.remote())}", flush=True)
    ray.shutdown()


if __name__ == "__main__":
    main()
