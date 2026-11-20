# Diagrama de la fase 1 (borrador, F1-S02)

Componentes de la aplicación y qué parte de Ray usa cada uno. Lo que es del
proyecto está en `fase1/`; lo que pone Ray está marcado. Este borrador se
completa cuando el borde tenga caché (F1-S04 en adelante) y se cierra con
`docs/mapa-ray.md` (F1-S11). Desde el 18 nov (F1-S04) el borde ya guarda copias
en su memoria. El pedido sigue siendo cliente → borde → origen, y en un `hit`
el camino se corta en el borde. Desde F1-R06 la invalidación va al revés:
origen → cada borde, sin pasar por el cliente.

## Los procesos

```text
                 proceso Ray                      proceso Ray
              ┌────────────────┐               ┌────────────────┐
              │    ORIGEN      │               │    CLIENTE     │
              │ fase1/origen.py│               │ fase1/cliente.py│
              │ contenido/     │               │ pedido_id       │
              │ versiones+hash │               │ orden de bordes │
              └───────▲────────┘               └───────┬────────┘
                      │ responder: borde → origen      │ pedir(pedido_id, recurso)
                      │ invalidar: origen → cada borde │ (llamada remota de Ray)
                      │                                │
        ┌─────────────┴──────────────┐                 │
        │                            │                 │
┌───────┴────────┐          ┌────────┴───────┐         │
│    BORDE-1     │          │    BORDE-2     │◄────────┘
│ fase1/borde.py │          │ fase1/borde.py │   (orden del selector,
│ copias en mem. │          │ copias en mem. │    fase1/selector.py:
│ TTL + LRU      │          │ TTL + LRU      │    borde-1, luego borde-2)
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
| Origen | versión de referencia por hash, lectura de `contenido/`, `responder`, `invalidar` hacia los bordes que el arranque le anotó (F1-R06) | `@ray.remote`: el proceso donde vive; `responder.remote` y `invalidar.remote`: llamadas entre procesos; el estado en memoria (`_versiones`, la lista de bordes) dura lo que dura el actor |
| Borde | copias en memoria con TTL (`expira_en`), `hit`/`miss` con causa, `guarda`, `revalida` por comparación de versión, expulsión LRU (F1-S04–S06); al recibir `invalidar`, borra esa copia; (pendiente) `STALE_LIMIT` | `@ray.remote`: proceso propio; `origen.responder.remote` + `ray.get`: la llamada al origen y la espera de la respuesta; (desde F1-S09) `ray.wait(timeout)` para decir «no responde» |
| Selector | orden de preferencia de bordes, memoria de cuál no respondió (F1-S07) | nada: es una clase dentro del proceso del cliente |
| Cliente | `pedido_id`, `solicitud`/`respuesta`, pasar al siguiente borde si uno no responde o rechaza (F1-S07) | `@ray.remote`: proceso propio; `borde.pedir.remote` + `ray.wait(timeout)`: la llamada al borde con tiempo de espera; `RayActorError` es cómo Ray dice que el borde murió |
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

- La partición: cómo se corta el camino borde→origen dejando el camino cliente→borde (F1-R09).

Un borde puede no aplicar la invalidación (`perder_avisos` en `fase1/borde.py`, F1-R07). La llamada de Ray llega, la copia vieja se queda y el borde anota `invalidacion_perdida`. El origen no lo incluye en `bordes=`.
