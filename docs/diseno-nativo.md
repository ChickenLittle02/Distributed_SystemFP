# Diseño nativo (fase 2)

Las ocho respuestas que pide el tablero (F2-R09–R12 las redacta Rubén, F2-S12–S15 Samy), para el
sistema sin Ray: un programa por nodo, HTTP de la biblioteca estándar de Go como transporte, y las
mismas reglas de caché de la fase 1. El contrato visible sigue siendo `docs/contrato.md`. Lo que Ray
hacía por nosotros y aquí se hace a mano está en `docs/mapa-ray.md`; la tabla Ray → nativo, en
`docs/decisiones.md` («Tabla nativa»).

Código: `fase2/` (módulo Go). Paquetes `config`, `registro`, `protocolo`, `transporte`, `origen`,
`cliente`; programas `cmd/origen`, `cmd/cliente`, `cmd/publicar`. El borde nativo (`fase2/borde`,
`cmd/borde`) lo escribe Rubén contra el protocolo de abajo.

## 1. Protocolo: quién habla con quién y qué campos viajan (F2-S12, Samy)

Cuatro conversaciones, todas HTTP/1.1 en claro (`cifrado = false`). El recurso va en la ruta, la
versión y el `pedido_id` en cabeceras, el archivo en el cuerpo. Nada más viaja.

| Quién → quién | Mensaje | Cabeceras que van | Respuestas |
| --- | --- | --- | --- |
| lector (navegador o `cmd/cliente`) → borde | `GET /<recurso>` | `X-Pedido-Id` (opcional: si no viene, el borde lo crea) | `200` cuerpo = archivo, `X-Resultado: hit\|miss\|sirve_obsoleta`, `X-Version`, `X-Pedido-Id`; `404` `X-Resultado: file_doesnt_exist`; `503` `X-Resultado: rechaza`; `405` a `PUT`/`DELETE` |
| borde → origen | `GET /<recurso>` | `X-Pedido-Id` (el del lector), `X-Version-Local` solo si revalida | `200` cuerpo = archivo, `X-Version` (+ `X-Misma: no` si venía versión); `304` sin cuerpo, `X-Version`, `X-Misma: si`; `404` `X-Resultado: file_doesnt_exist` |
| publicador (`cmd/publicar`, `curl`) → origen | `PUT /<recurso>` cuerpo = archivo; `DELETE /<recurso>` | `X-Pedido-Id` | `200` `X-Version`, `X-Bordes-Avisados`; `404` en `DELETE` de algo que no estaba; `400` nombre no válido |
| origen → cada borde de la configuración | `POST /_invalidar/<recurso>` sin cuerpo | `X-Pedido-Id` (el del `PUT`/`DELETE`), `X-Version` nueva, o `X-Resultado: file_doesnt_exist` si se borró | `200` cuerpo = nombre del borde: aplicó el aviso; `202`: lo recibió y no lo aplicó (aviso perdido simulado, el borde anota `invalidacion_perdida`); otra cosa o nada: «no contestó» |

Reglas que fija el protocolo:

- **El cuerpo es el archivo tal cual** (`application/octet-stream`). No hay JSON ni *framing*
  propio: HTTP ya delimita el mensaje con `Content-Length`. Eso es lo que Ray serializaba solo.
- **Los nombres son los del historial.** `X-Resultado` lleva exactamente los tokens del contrato
  (`hit`, `miss`, `sirve_obsoleta`, `rechaza`, `file_doesnt_exist`). Quien lee un log y quien lee
  una respuesta ven las mismas palabras.
- **`304` es «misma versión»**, como `If-None-Match` / `Not Modified` en HTTP: la pregunta y la
  bajada son la misma llamada; solo cambia si viajan bytes. La versión se compara por igualdad.
- **El borde rechaza `PUT` y `DELETE`** (`405`). La escritura no pasa por la caché.
- **Un recurso es un nombre de archivo simple**: sin `/`, sin `..`, sin empezar por `.`. El origen
  responde `400` a cualquier otra cosa y nunca sirve `.versiones.json`.
- Los dos programas de Samy hablan por el paquete `transporte`: el único que abre conexiones.
  Con `cifrado = true` (el plus, fuera de esta fase) cambiaría solo ese paquete.

## 2. Identidad de recurso y `pedido_id`; arranque estático y lista de miembros (F2-S13, Samy)

**Identidad de recurso.** Un recurso es su nombre de archivo en la carpeta del origen
(`contenido/`). Dos nodos hablan del mismo recurso si usan el mismo nombre; no hay identificador
aparte. Lo que distingue dos versiones del mismo recurso es el número de versión del origen: sube en
1 cada vez que el hash SHA-256 del contenido cambia. El origen **persiste** versión y hash en
`contenido/.versiones.json`: si el origen reinicia, la versión no vuelve a 1 (en la fase 1 sí: el
actor la tenía en memoria). Borrar un recurso no borra su entrada: si vuelve con otro contenido, la
versión sigue subiendo.

**`pedido_id`.** Lo crea quien inicia el pedido: `cmd/cliente` (seis dígitos hexadecimales, como en
la fase 1) o, si el lector es un navegador sin `X-Pedido-Id`, el borde al recibirlo. Viaja en la
cabecera `X-Pedido-Id` en todas las llamadas que ese pedido provoca (lector → borde → origen) y vuelve
en la respuesta. Una publicación tiene el suyo (`cmd/publicar` lo crea) y el aviso de invalidación lo
lleva a cada borde: `grep "pedido=<id>" logs/*.log` sigue enseñando el recorrido completo, incluido el
aviso que un `PUT` disparó.

**Arranque estático.** No hay descubrimiento. `fase2/config.json` dice la dirección del origen y la
lista de bordes con nombre y `host:puerto`, en orden de preferencia. Cada programa lee ese archivo
al arrancar: el cliente para saber a quién pedir, el origen para saber a quién avisar, el borde para
saber dónde está el origen. Es la decisión que el tablero da por válida si está justificada: en una
CDN real la lista de nodos de borde la tiene el operador, no la descubren los nodos entre sí. Un borde
que no esté en la lista no recibe avisos y no recibe pedidos; añadirlo es editar el archivo y
reiniciar a quien lo use. Las variables `P20_*` acortan los tiempos en una prueba, igual que en la
fase 1.

**Lista de miembros.** Es esa lista, y es la misma en todos los nodos porque todos leen el mismo
archivo. Nadie la actualiza en caliente. «Vivo» o «caído» no es un estado de la lista: lo decide
cada llamada (sección 6 de Rubén y sección 4 abajo). El DNS mínimo (F2-S19, si entra) tendría su
propia copia de la lista por la misma razón.

## 3. Qué se puede reintentar y cómo se reconoce un duplicado (F2-S14, Samy)

**Qué reintenta quién.** El `transporte` no reintenta nunca; el reintento es decisión de quien
llama, y en este diseño solo lo hace el **cliente**, y solo cambiando de fuente: si un borde no
responde o rechaza, el mismo `pedido_id` se manda al siguiente borde del selector (una línea
`solicitud` por intento). El borde **no reintenta** contra el origen: si el origen no responde en el
plazo, aplica la regla de obsoleto, porque una segunda espera de 2 s no cambia la decisión y sí
duplica la latencia. El origen **no reintenta** un aviso de invalidación: el borde que no contestó
queda fuera de `bordes=`, y ese borde se pondrá al día por TTL (sección 4). El publicador tampoco:
si el `PUT` no obtiene respuesta, lo repite la persona que publica.

**Qué es seguro repetir.** Todas las operaciones del protocolo son idempotentes por construcción:

- `GET` no cambia nada en el origen (solo puede hacer subir la versión si alguien editó el archivo a
  mano, y eso lo haría igual el primer `GET`).
- `PUT` del mismo contenido deja la misma versión: la versión sube solo si el hash cambia. Repetir un
  `PUT` por un timeout no crea una versión fantasma. Sí dispara otro aviso, que los bordes aplican
  marcando una copia que ya estaba marcada: no pasa nada.
- `DELETE` repetido devuelve `404` la segunda vez y manda el mismo aviso.
- `POST /_invalidar` repetido marca una copia ya marcada.

**Cómo se reconoce un duplicado.** Por el `pedido_id`, en el historial, no en los nodos: el mismo
`pedido_id` en dos líneas `solicitud` del cliente es un reintento en otro borde; el mismo
`pedido_id` en `responde` del origen dos veces sería un `GET` repetido. Ningún nodo guarda los
`pedido_id` vistos para rechazar repetidos, porque ninguna operación necesita esa protección (todas
son idempotentes) y guardarlos sería estado que habría que acotar y limpiar. Lo que sí se garantiza
es que repetir no corrompe la versión: es la ficha F3-S05 («el mismo `pedido_id` no corrompe la
versión, y dos clientes pueden pedir a la vez»). En el origen las versiones se tocan bajo un cerrojo
(`sync.Mutex`) porque el servidor HTTP de Go atiende cada pedido en su propia gorrutina; en Ray ese
cerrojo lo ponía el actor.

## 4. Invalidación perdida, borde que vuelve, y confianza con el canal en claro (F2-S15, Samy)

**Invalidación perdida.** El aviso sale del origen una sola vez por `PUT`/`DELETE`, con el plazo
de la configuración. Puede perderse de tres formas, y cada una deja huella distinta:

- el borde no está (conexión rechazada): el origen anota `nodo_caido destino=<borde>`;
- el borde no contesta a tiempo: `timeout destino=<borde>`;
- el borde contesta `202`: lo recibió y no lo aplicó. Es la simulación del aviso perdido (F1-R07 en
  la fase 1); el borde anota `invalidacion_perdida`.

En los tres casos el borde queda fuera de `bordes=` en la línea `invalidar` del origen, y esa
ausencia es la evidencia que sobrevive a la fase 1: con un mensaje perdido de verdad el borde no
escribe nada. La copia vieja de ese borde sigue la regla de frescura: se sirve mientras su TTL no
venza; al vencer, el borde revalida con `X-Version-Local`, el origen contesta `200` con la versión
nueva, y la copia se reemplaza. El sistema converge solo por TTL; la invalidación solo lo adelanta.
Cota de la mentira: una copia vieja se sirve como `hit` como mucho `TTL` después de la publicación
nueva si el aviso no llegó.

**Borde que vuelve.** Un borde que reinicia arranca **vacío**: la caché vive en memoria (misma
decisión que en la fase 1, y es lo que dirá la ficha F3-S03). No necesita avisar a nadie: no está
en ningún registro que haya que actualizar; el cliente volverá a probarlo cuando pase
`evitar_borde_segundos`, y el origen le seguirá mandando avisos (que aplicará a copias que no tiene:
`habia_copia=no`). El primer pedido tras volver es `miss`. No hay «ponerse al día»: lo que se perdió
mientras estaba caído no importa porque no tiene copias que puedan estar viejas.

**Confianza con el canal en claro.** Todo viaja sin cifrar ni firmar, y el diseño lo asume:

- Cualquiera que alcance la dirección del origen puede publicar (`PUT`/`DELETE`). No hay cuentas.
  La vía de escritura está separada de la caché (el borde responde `405`), así que un lector no puede
  cambiar la versión de referencia por la puerta del borde; pero sí por la del origen si la alcanza.
- Un borde acepta `POST /_invalidar` de quien se lo mande. Un tercero podría marcar copias y forzar
  misses; no podría hacer servir contenido falso, porque el borde solo guarda lo que baja del origen
  que tiene en la configuración.
- Un tercero en la red podría suplantar al origen ante el borde y darle bytes falsos. Eso es
  exactamente lo que cubriría TLS entre borde y origen (el plus: el borde comprueba el certificado
  del origen); el canal lector ↔ borde seguiría en claro.
- El historial y las copias en disco tampoco están protegidos.

Lo que esta fase garantiza es lo que el contrato dice sobre frescura, versiones y `STALE_LIMIT`
**suponiendo que los mensajes llegan de quien dicen**. La frase de `docs/garantias.md` (fase 3) sale
de aquí.

## 5–8. Las respuestas de Rubén (F2-R09–R12)

Pendientes de redactar por Rubén:

5. Qué estado hay y quién es dueño (el origen de la versión de referencia; el borde solo de su copia).
6. Cuándo una lectura está completa, y por qué guardar en caché no es un acuse durable del origen.
7. Partición, `STALE_LIMIT`, y qué cambia cuando el origen vuelve.
8. Cómo se detecta un nodo que no responde (`timeout` o `nodo_caido`). Lo que ya está escrito del lado de Samy: el paquete `transporte` distingue el plazo vencido (`context.DeadlineExceeded`, `timeout`) de la conexión que no abre o se corta (`nodo_caido`); el origen y el cliente anotan esa palabra con `destino=`.
