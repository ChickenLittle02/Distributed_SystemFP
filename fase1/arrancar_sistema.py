"""Arranca el sistema completo de la fase 1: origen, dos bordes y un cliente.

Responsabilidad: iniciar Ray, crear los cuatro actores (cada uno en su
proceso), comprobar que viven y hacer un pedido de prueba por el cliente.
No es la corrida del checklist (F1-J06): esa se arma cuando el borde tenga
caché.
"""

from __future__ import annotations

import ray

from fase1.borde import Borde
from fase1.cliente import Cliente
from fase1.config import Config
from fase1.origen import Origen


def main() -> None:
    """Crea origen, borde-1, borde-2 y cliente, y pide apunte.txt una vez.

    Entra: nada. Sale: imprime los listo y la respuesta del pedido.
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

    r = ray.get(cliente.pedir.remote("apunte.txt"))
    print(f"pedido={r['pedido_id']} resultado={r['resultado']} version={r['version']} "
          f"fuente={r['fuente']} bytes={len(r['contenido'] or b'')}", flush=True)
    ray.shutdown()


if __name__ == "__main__":
    main()
