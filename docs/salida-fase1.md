# Salida de la fase 1 (F1-R10)

Las cinco respuestas de la compuerta. El prototipo es el que está en `fase1/`.
La corrida que sostiene la quinta respuesta es la de F1-R09:

```text
P20_TTL=3 P20_STALE_LIMIT=4 python3 -m fase1.escenarios obsoleto
```

La ficha con la predicción y la evidencia citada está en `docs/experimento-fase1.md`.
Qué pone Ray y qué no, en `docs/mapa-ray.md`.

## Qué problema resuelve

Una caché de borde acerca el archivo al cliente y descarga al origen. El
problema aparece cuando esa copia y el origen dejan de verse: el borde puede
seguir atendiendo al cliente con una versión vieja, y un aviso de invalidación
puede no llegar.

El prototipo resuelve eso con una política explícita, no con una decisión
escondida en la biblioteca. El origen es dueño de la versión de referencia
(hash del archivo en `contenido/`). Cada borde guarda su copia, con TTL, y
decide hit, miss, revalidación o contenido obsoleto. Si un borde no contesta,
el cliente prueba el otro. Si el origen no contesta, el borde sirve la copia
solo mientras lleve obsoleta como mucho `STALE_LIMIT`, y la rechaza si lo
supera. Una copia que el origen invalidó no se sirve nunca, aunque esté dentro
de ese límite.

## Qué comportamiento tiene que sobrevivir al rediseño

La fase 2 quita Ray. Estas reglas se quedan, con el mismo contrato y el mismo
historial:

- Hit de una copia fresca, sin hablar con el origen.
- Miss si no está, bajada desde el origen y `guarda`.
- Versión por hash en el origen y expiración por TTL en el borde.
- Expulsión LRU cuando el borde se llena, visible en el log.
- Invalidación que marca la copia y no la borra. No se devuelve aunque la pidan.
- Un borde que no aplica el aviso lo anota (`invalidacion_perdida`) y el origen
  no lo cuenta entre los avisados.
- Revalidación: si la copia expiró y el origen confirma la misma versión, no
  viajan bytes y el resultado es hit. Si la versión cambió, se guarda la nueva.
- Si un borde no responde, el selector usa el otro. El `rechaza` de un borde no
  es el final: el final lo anota el cliente cuando ninguno entregó.
- Origen inalcanzable: `sirve_obsoleta` si la edad obsoleta es menor o igual que
  `STALE_LIMIT`, `rechaza` si la supera. La copia rechazada sigue guardada.
- `registrar` desde la primera operación. `cifrado = false`.

No tiene que sobrevivir el mecanismo: ni el actor, ni el handle, ni
`particion(True)`. En la fase 2 el corte es de red y el mensaje viaja por TCP.

## Qué hace el código

El código de `fase1/` es la caché. Nada de hit, miss, TTL, LRU, invalidación,
revalidación ni `STALE_LIMIT` está delegado.

- `origen.py` lee `contenido/`, sube la versión si cambia el hash, responde el
  archivo o `file_doesnt_exist`, y con `version_local` contesta `misma=si` sin
  bytes. `invalidar` avisa a los bordes de `anotar_bordes` y anota quiénes
  aplicaron el aviso.
- `borde.py` guarda las copias en memoria (`Copia`: versión, bytes, expiración,
  marca `invalidada`). `pedir` elige la rama. `particion` simula el corte con
  el origen. La expulsión es LRU con capacidad 2.
- `selector.py` ordena los bordes de `Config`. No es un nodo: vive en el
  proceso del cliente. El que no respondió va al final durante
  `evitar_borde_segundos`.
- `cliente.py` crea el `pedido_id`, anota `solicitud` y `respuesta`, y pasa al
  siguiente borde si hay `timeout`, `nodo_caido` o `rechaza`. No habla con el
  origen.
- `registro.py` escribe la línea en consola y en `logs/<nodo>.log`.
- `config.py` junta TTL (30 s), `STALE_LIMIT` (60 s, provisional), capacidad,
  timeout y `cifrado = false`. Una corrida corta los cambia con `P20_*`.
- `escenarios.py` provoca cada comportamiento. El del experimento es `obsoleto`.

## Qué hace Ray

Ray solo pone procesos y transporte. Arranca un worker por actor
(`ray.init`, `@ray.remote`, `Clase.remote`), lleva la llamada de un proceso a
otro (`metodo.remote`, `ray.get`) y deja esperar con límite (`ray.wait`). Si
el actor murió, la llamada lanza `RayActorError` y el código anota
`nodo_caido`. El handle es la dirección: el borde sabe dónde está el origen
porque recibió esa referencia al crearse.

Ray entrega cada llamada una vez y atiende un mensaje por actor a la vez. Por
eso la caché no usa cerrojos. No reintenta. No decide qué copia servir.

Eso se reemplaza en la fase 2 por un programa por nodo, direcciones en la
configuración y `enviar` / `recibir` sobre TCP en claro. La lista de llamadas
está en `docs/mapa-ray.md`.

## Qué semántica de fallo se observó

La corrida de F1-R09 (19 nov, `TTL = 3 s`, `STALE_LIMIT = 4 s`) cortó
`borde-1` → origen con `particion(True)` después de guardar `apunte.txt`. El
cliente siguió llegando a `borde-1`. `borde-2` siguió viendo al origen. En
`logs/` quedó esto:

| Pedido | Observado |
| --- | --- |
| `e7d7c3` | `miss causa=no_esta`, bajada, `guarda` versión 1. Después, `particion … estado=cortada` |
| `1e94ca` | `hit estado=fresca`. El origen no tiene línea de este pedido: el corte no se nota mientras la copia está fresca |
| `2fee3f` | Edad obsoleta 1 s, dentro de 4. `timeout destino=origen causa=particion`, `origen_no_responde`, `sirve_obsoleta`. El cliente recibe la versión 1 |
| `010bd0` | Edad 6 s. `borde-1` anota `rechaza causa=supera_limite` y no borra la copia (`estado=obsoleta`). El cliente pide a `borde-2`, que hace `miss` contra el origen. Resultado: `miss fuente=borde-2` |
| `a74b66` | Tras `particion … estado=reparada`, el origen contesta `misma=si` sin bytes. `revalida renovo=si` y `hit estado=fresca` |

«El origen no responde» en esta corrida es el interruptor, no un paquete
perdido: la línea `timeout causa=particion` sale al momento, sin esperar los
2 s. La copia que se rechaza sigue en el borde. Al volver el origen, se
confirma la misma versión y no se vuelve a bajar.

La ficha añade una segunda semántica, ya corrida: una copia invalidada durante
la partición da `rechaza causa=invalidada` aunque la edad obsoleta sea 0.
`STALE_LIMIT` no la habilita.

Queda fuera de lo observado: el `timeout` de un origen lento pero vivo (ficha
F3-R03), el valor definitivo de `STALE_LIMIT` (sigue en 60 s) y un corte de
red de verdad. El interruptor es la simulación reproducible de esta fase.
