# Diagrama de la fase 1 (borrador, F1-S02)

Componentes de la aplicación y qué parte de Ray usa cada uno. Lo que es del
proyecto está en `fase1/`; lo que pone Ray está marcado. Este borrador se
completa cuando el borde tenga caché (F1-S04 en adelante) y se cierra con
`docs/mapa-ray.md` (F1-S11).

## Los procesos

```text
                 proceso Ray                      proceso Ray
              ┌────────────────┐               ┌────────────────┐
              │    ORIGEN      │               │    CLIENTE     │
              │ fase1/origen.py│               │ fase1/cliente.py│
              │ contenido/     │               │ pedido_id       │
              │ versiones+hash │               │ orden de bordes │
              └───────▲────────┘               └───────┬────────┘
                      │ responder(pedido_id, recurso)  │ pedir(pedido_id, recurso)
                      │ (llamada remota de Ray)        │ (llamada remota de Ray)
        ┌─────────────┴──────────────┐                 │
        │                            │                 │
┌───────┴────────┐          ┌────────┴───────┐         │
│    BORDE-1     │          │    BORDE-2     │◄────────┘
│ fase1/borde.py │          │ fase1/borde.py │   (hoy: siempre borde-1;
│ copias (vacío) │          │ copias (vacío) │    el selector es F1-S07)
└────────────────┘          └────────────────┘
   proceso Ray                 proceso Ray

              fase1/registro.py  →  logs/<nodo>.log   (todos los nodos)
              fase1/config.py    →  TTL, STALE_LIMIT, capacidad, timeout,
                                    orden de bordes, cifrado=false
```

Un script del lado del usuario (`fase1/arrancar_sistema.py`) crea los cuatro
actores y lanza el pedido. Ese script no es un nodo del sistema.

## Qué parte de Ray usa cada componente

| Componente | Lo que es del proyecto | Lo que pone Ray hoy |
| --- | --- | --- |
| Origen | versión de referencia por hash, lectura de `contenido/`, `responder` | `@ray.remote`: el proceso donde vive; `responder.remote(...)`: que el borde lo llame desde otro proceso; el estado en memoria (`_versiones`) dura lo que dura el actor |
| Borde | (hoy) reenviar al origen; (desde F1-S04) copias, TTL, LRU, invalidación, revalidación, `STALE_LIMIT` | `@ray.remote`: proceso propio; `origen.responder.remote` + `ray.get`: la llamada al origen y la espera de la respuesta; (desde F1-S09) `ray.wait(timeout)` para decir «no responde» |
| Cliente | `pedido_id`, orden de preferencia de bordes, `solicitud`/`respuesta` | `@ray.remote`: proceso propio; `borde.pedir.remote` + `ray.get`: la llamada al borde |
| Registro | formato de la línea, un archivo por nodo | nada: escribe en disco local del proceso |
| Config | los números y la frase de la política | nada |
| Arranque | crear los nodos y el pedido de prueba | `ray.init()` levanta el runtime local; `Actor.remote(...)` arranca cada proceso; `ray.shutdown()` los apaga |

## Lo que Ray decide por nosotros (a vigilar para la fase 2)

- **Dónde corre cada nodo**: Ray elige el proceso (worker) y lo arranca. En la fase 2 cada
  nodo será un programa que se arranca a mano con su dirección y puerto.
- **Cómo viaja el mensaje**: `responder.remote` serializa los argumentos y el resultado
  (incluidos los bytes del archivo) y los mueve entre procesos. En la fase 2 eso es
  `enviar`/`recibir` sobre TCP con un formato de texto.
- **Qué pasa si el origen muere**: la llamada lanza `RayActorError`. En la fase 2 eso es un
  socket que no abre o un `recv` que vence.
- **Quién sabe dónde está el origen**: el handle del actor que recibe el borde al crearse.
  En la fase 2 es la dirección en la configuración (arranque estático).
- **Reintentos**: Ray no reintenta llamadas de actor por defecto; el proyecto tampoco quiere
  que lo haga, porque el reintento es decisión de la regla de obsoleto.

## Qué no cubre este borrador todavía

- La selección de fuente y el paso a otro borde (F1-S07).
- La invalidación desde el origen hacia los bordes (F1-R06) y el aviso que no llega (F1-R07).
- La partición: cómo se corta el camino borde→origen dejando el camino cliente→borde (F1-R09).
