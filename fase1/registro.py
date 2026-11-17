"""Registro compartido del historial.

Responsabilidad: armar una línea de historial con el formato del README,
mostrarla en consola y agregarla al archivo del nodo en logs/.
No decide hit, miss, invalidación ni STALE_LIMIT. No abre sockets.
No guarda el contenido de los archivos repartidos.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

# Carpeta de logs relativa a la raíz del repositorio.
_RAIZ = Path(__file__).resolve().parent.parent
_DIR_LOGS = _RAIZ / "logs"


def registrar(nodo: str, pedido_id: str, operacion: str, **datos) -> str:
    """Escribe una línea de historial y la muestra.

    Entra: nombre del nodo, pedido_id, nombre de la operación y pares
    clave=valor (recurso, version, causa, etc.).
    Sale: la línea escrita, sin salto final.
    Si el otro nodo no contesta: esta función no habla con nadie; solo anota.
    """
    hora = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    partes = [hora, nodo, f"pedido={pedido_id}", operacion]
    for clave, valor in datos.items():
        partes.append(f"{clave}={valor}")
    linea = " ".join(partes)

    _DIR_LOGS.mkdir(parents=True, exist_ok=True)
    archivo = _DIR_LOGS / f"{nodo}.log"
    with archivo.open("a", encoding="utf-8") as salida:
        salida.write(linea + "\n")

    print(linea, flush=True)
    return linea
