"""Arranca Ray en local, crea el origen y un borde vacío, y prueba que vive.

Responsabilidad: iniciar Ray, crear el actor Origen (de Rubén) y un actor
Borde, comprobar listo() y que el borde arranca sin copias.
No levanta cliente ni hace pedidos: eso está en fase1/arrancar_sistema.py.
"""

from __future__ import annotations

import ray

from fase1.borde import Borde
from fase1.config import Config
from fase1.origen import Origen


def main() -> None:
    """Inicia Ray, crea origen y borde-1, y muestra el estado vacío.

    Entra: nada. Sale: imprime listo y el estado del borde.
    Si el otro nodo no contesta: si Ray no arranca, el proceso termina con error.
    """
    cfg = Config.desde_entorno()
    ray.init(ignore_reinit_error=True)
    origen = Origen.remote()
    borde = Borde.remote("borde-1", origen, cfg)
    print(f"origen listo: {ray.get(origen.listo.remote())}", flush=True)
    print(f"borde listo: {ray.get(borde.listo.remote())}", flush=True)
    print(f"copias en el borde: {ray.get(borde.estado.remote())}", flush=True)
    ray.shutdown()


if __name__ == "__main__":
    main()
