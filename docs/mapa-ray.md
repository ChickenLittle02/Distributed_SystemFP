# Mapa de Ray en la fase 1 (F1-S11)

Para cada requisito del README: qué lo resuelve hoy el código del repositorio, qué pone Ray sin que lo hayamos escrito, y qué habrá que hacer explícito en la fase 2, cuando Ray deje de ser dependencia. Cubre los cuatro ejes que pide el tablero: ejecución remota, estado, fallo y observabilidad.

La regla que guía la tabla: **Ray no decide ninguna regla de caché**. Hit, miss, TTL, LRU, invalidación, revalidación y `STALE_LIMIT` están en `fase1/`. Lo que Ray pone es el transporte y el ciclo de vida de los procesos.

## Qué usa el código de Ray, exactamente

| Llamada | Dónde | Para qué |
| --- | --- | --- |
| `ray.init()` / `ray.shutdown()` | `arrancar_*.py`, `escenarios.py` | Levantar y apagar el runtime local |
| `@ray.remote` sobre una clase | `origen.py`, `borde.py`, `cliente.py` | Que cada nodo viva en su propio proceso y conserve estado entre llamadas |
| `Clase.remote(...)` | arranques | Crear el proceso del nodo |
| `actor.metodo.remote(...)` | `cliente.py` → borde, `borde.py` → origen, `origen.py` → bordes | Mandar un mensaje a otro proceso con sus argumentos (incluidos los bytes del archivo) |
| `ray.get(ref)` | los tres actores y los arranques | Esperar la respuesta |
| `ray.wait([ref], timeout=…)` | `cliente.py` (`_llamar_borde`), `borde.py` (`_hablar_con_origen`) | Esperar con tiempo límite: es lo que permite decir `timeout` |
| `RayActorError` | `cliente.py`, `borde.py`, `origen.py` | Saber que el actor al que se llamó murió: es la línea `nodo_caido` |
| `ray.kill(actor)` | `escenarios.py` | Provocar un borde o un origen muerto en las pruebas |
| el *handle* de un actor | `Borde(origen=…)`, `Cliente(bordes=…)`, `origen.anotar_bordes(...)` | Saber «dónde está» el otro nodo |

Nada más. No se usan tareas (`@ray.remote` sobre funciones), ni el object store a mano, ni placement, ni reintentos de Ray.

## Por requisito

| Requisito (README) | Lo que hace el código del repo | Lo que pone Ray hoy | Qué habrá que hacer explícito en la fase 2 |
| --- | --- | --- | --- |
| **Ejecución: un origen, varios bordes, clientes, en procesos distintos** | Las clases `Origen`, `Borde`, `Cliente` y los scripts de arranque | Arranca cada actor en un *worker*, elige el proceso, lo supervisa | Un programa por nodo, arrancado a mano con su dirección y puerto (`docker run`, sin compose). Un `main` por rol |
| **Comunicación entre nodos** | Las firmas `pedir`, `responder`, `invalidar` y sus dicts | Serializa argumentos y resultado (dict + bytes) y los mueve entre procesos; garantiza entrega y orden por actor | `enviar(destino, mensaje)` / `recibir()` sobre TCP en claro; formato de mensaje en texto (recurso, versión, `pedido_id`, invalidación); *framing* de los bytes del archivo |
| **Quién sabe dónde está quién (membresía)** | `Config.bordes` (lista estática) y `anotar_bordes` | El *handle* del actor: una referencia opaca que Ray resuelve | Direcciones en la configuración (arranque estático, ya justificado en `decisiones.md`); el origen necesita la lista de bordes para invalidar |
| **Selección de fuente** | `selector.py` + `cliente.py` | Nada | Nada nuevo: la política es nuestra |
| **Hit / miss, TTL, versiones, LRU** | `borde.py` (`Copia`, `pedir`, `_guardar`) y `origen.py` (`_version_y_bytes`) | Nada | Nada nuevo |
| **Estado del origen (versiones)** | `_versiones` en memoria, hash de `contenido/` | La memoria del actor dura lo que dura el proceso | Persistir versión y hash (si el origen reinicia hoy, vuelve a versión 1) |
| **Estado del borde (copias)** | `_copias` en memoria | Igual: si el actor muere, arranca vacío | Decidir si la caché sobrevive al reinicio (hoy no; la ficha F3-S03 lo describe tal cual) |
| **Invalidación y revalidación** | `origen.invalidar` → `borde.invalidar` (marca la copia); `borde.pedir` manda `version_local` y el origen contesta `misma` sin bytes (F1-S08/R08) | La llamada origen→borde y la respuesta | El mensaje de invalidación como texto; el aviso con timeout; la revalidación (`version_local` → `misma`) como un mensaje sin cuerpo |
| **Fallo de un borde** | `cliente._llamar_borde`: `timeout` / `nodo_caido`, y el selector pasa al siguiente | `ray.wait(timeout)` y `RayActorError` | Socket que no abre, `connect`/`recv` que vence; el cliente reintenta en otro borde igual que hoy |
| **Fallo del origen / partición** | `borde._hablar_con_origen` + `_sin_origen` (regla `STALE_LIMIT`); `particion(True)` simula el corte | `ray.wait(timeout)` y `RayActorError` | Lo mismo con sockets; la partición se provoca con red (matar el proceso, cerrar el puerto, `iptables`) en vez de un interruptor |
| **Reintentos / duplicados** | Ninguno: cada pedido es una llamada; `pedido_id` lo crea el cliente | Ray no reintenta llamadas de actor (y no queremos que lo haga) | Decir qué se reintenta y cómo se reconoce un `pedido_id` repetido (F2-S14) |
| **Observabilidad** | `registrar`: una línea por operación, `logs/<nodo>.log`, `pedido_id` de punta a punta | Reenvía el `stdout` de cada worker al proceso que arrancó (por eso se ve `(Borde pid=…)` en consola) | Nada en el formato; cada programa escribe su propio archivo y su consola |

## Lo que Ray decide por nosotros y conviene no olvidar

- **Entrega y orden.** Una llamada a un actor llega una vez y los mensajes a un mismo actor se procesan en orden. En TCP en claro eso hay que construirlo o renunciar a ello.
- **Un actor atiende una llamada a la vez.** Por eso `_copias` no necesita cerrojos. Con sockets y varios clientes hará falta decidir si el borde es de un hilo o protege su estado.
- **Serialización.** Los dicts con `bytes` viajan solos. En la fase 2 el formato es nuestro, en texto, y los bytes del archivo necesitan longitud o delimitador.
- **Detección de muerte.** `RayActorError` llega sin esperar al timeout. Con sockets, un proceso muerto puede parecer un timeout: `nodo_caido` y `timeout` se distinguirán por el error del socket, no por Ray.
- **Descubrimiento.** El handle es un puntero global. En la fase 2 es una dirección en la configuración, y el origen no puede «encontrar» un borde que no esté en la lista.
- **Lo que Ray no hace y ya es nuestro:** TTL, LRU, `STALE_LIMIT`, la regla de la copia invalidada, el selector, el formato del historial. Nada de eso cambia en la fase 2.

## Cómo se comprobó

Cada fila de «fallo» tiene un escenario que la provoca y deja evidencia en `logs/`: `python3 -m fase1.escenarios selector` (borde muerto), `origen_caido` (origen muerto), `obsoleto` (partición borde→origen con las dos ramas de `STALE_LIMIT`), `invalidada` (aviso recibido + partición), `perdida` (aviso que no se aplica). Ver `docs/experimento-fase1.md`.
