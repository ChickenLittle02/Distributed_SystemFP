"""Arranca Ray en local, crea el origen y prueba responder.

Responsabilidad: iniciar Ray, crear el actor Origen, comprobar listo()
y pedir un recurso de contenido/ (y uno que no existe).
No levanta bordes ni cliente.
"""

from __future__ import annotations

import ray

from fase1.origen import Origen


def main() -> None:
    """Inicia Ray, crea el origen y ejercita responder.

    Entra: nada (se corre desde la raíz del repositorio).
    Sale: imprime listo, la versión del recurso de prueba y el caso
    file_doesnt_exist.
    Si el otro nodo no contesta: aquí solo existe el origen; si Ray
    no arranca, el proceso termina con error.
    """
    ray.init(ignore_reinit_error=True)
    origen = Origen.remote()
    nombre = ray.get(origen.listo.remote())
    print(f"origen listo: {nombre}", flush=True)

    hay = ray.get(origen.responder.remote("prueba-1", "apunte.txt"))
    if hay["existe"]:
        print(
            f"responde apunte.txt version={hay['version']} "
            f"bytes={len(hay['contenido'])}",
            flush=True,
        )
    else:
        print(f"inesperado: {hay}", flush=True)

    falta = ray.get(origen.responder.remote("prueba-2", "no-existe.txt"))
    print(
        f"no-existe.txt -> resultado={falta.get('resultado')} existe={falta['existe']}",
        flush=True,
    )

    ray.shutdown()


if __name__ == "__main__":
    main()
