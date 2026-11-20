# Decisiones

Cada entrada la escribe quien implementa. La otra persona la revisa y, si no puede explicarla con sus palabras, la pieza sigue abierta.

### 2026-11-16 — STALE_LIMIT provisional de 1 minuto

- Decisión: `STALE_LIMIT = 60` segundos (1 minuto) mientras se desarrolla y se prueba el prototipo.
- Alternativas consideradas: 10 minutos, que es el ejemplo del README; dejar el número sin fijar hasta el experimento de partición.
- Por qué esta: con 10 minutos hay que esperar demasiado para ver, en una corrida local, una copia servida dentro del límite y otra rechazada por encima. Un minuto basta para distinguir las dos ramas.
- Qué no resuelve: no es el valor de la entrega ni de la defensa. Es provisional para poder ejecutar el programa sin esa espera. El número definitivo se vuelve a decidir al cerrar la regla de obsoleto y el experimento de partición.
- Dónde está en el código: todavía no hay código. Cuando existan el origen y el borde, el valor sale de la configuración y la regla lo lee de ahí.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: el valor ya está en el código, `fase1/config.py` (`stale_limit_segundos`, cambiable con `P20_STALE_LIMIT`). Con TTL 30 s, una copia sigue siendo servible hasta 90 s después de guardada si el origen calla (30 fresca + 60 obsoleta). El tiempo es la única cota que el borde puede medir solo: no puede saber cuántas versiones lleva de atraso justo cuando el origen no contesta.

### 2026-11-16 — Fase 1 en Python con Ray

- Decisión: el prototipo de la fase 1 se escribe en Python y usa Ray para correr el origen, los bordes y el cliente en procesos separados.
- Alternativas consideradas: escribir ya el transporte TCP en el lenguaje de la fase 2; usar otro runtime de actores.
- Por qué esta: la fase 1 tiene que ejecutarse de verdad en varios procesos y dejar escrito qué aporta Ray (el arranque de esos procesos y la llamada de uno a otro). La caché, las versiones, la invalidación y la regla de obsoleto se escriben en este repositorio. El diseño sin Ray es la fase 2.
- Qué no resuelve: Ray no decide el hit, el miss, la expulsión, la invalidación ni `STALE_LIMIT`. Esas reglas no se delegan en una biblioteca de caché. `enviar` y `recibir` sobre TCP quedan para la fase 2.
- Dónde está en el código: todavía no hay código. El primer uso es el arranque del actor origen.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: el código lo cumple; los únicos usos de Ray son `@ray.remote`, `.remote()`, `ray.get`, `ray.wait` y `ray.kill`, en los actores, los arranques y `fase1/escenarios.py`. La lista de qué pone Ray va en `docs/mapa-ray.md` (F1-S11).

### 2026-11-16 — El cliente pide por nombre y no elige el borde

- Decisión: el cliente es un proceso distinto del origen y de los bordes. Pide un recurso por su nombre y un `pedido_id` que él crea. No envía un borde preferido. La selección escoge la fuente y el historial la anota como `fuente`.
- Alternativas consideradas: que el cliente nombre el borde en el pedido, como si `fuente=borde-1` fuera un dato de entrada.
- Por qué esta: en una caché normal quien pide el archivo nombra la URL; otro componente elige el nodo de borde. El ejemplo del README anota la fuente en la línea `solicitud`, que es el borde ya elegido.
- Qué no resuelve: no fija el orden ni el criterio fino de la selección. Si el primer borde no puede servir y el origen no contesta, la regla de `rechaza` ya dice que se prueba el otro borde. La política concreta la implementa Samy.
- Dónde está en el código: `docs/contrato.md`. Todavía no hay programa cliente.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: desde F1-S07 un `pedido_id` puede tener más de una línea `solicitud` (una por cada borde que el selector probó); la fuente que entregó queda en la línea `respuesta`. La política concreta de selección está en la entrada del 19 nov («Política de selección»).

### 2026-11-16 — La respuesta incluye el contenido del archivo

- Decisión: además de `version` y `resultado`, la respuesta al cliente lleva `contenido`, los bytes del archivo. `hit`, `miss` y `sirve_obsoleta` traen esos bytes. `rechaza` no trae contenido. El historial sigue sin guardar el archivo.
- Alternativas consideradas: devolver solo la versión y el resultado, y dejar el archivo fuera de esta fase.
- Por qué esta: el sistema reparte un archivo. La versión y el resultado dicen qué pasó; el contenido es lo que el cliente vino a buscar. El borde tiene que guardar el archivo, no solo el nombre y la versión.
- Qué no resuelve: no enumera los fallos. Esos casos están en las entradas siguientes y en `docs/contrato.md`. `file_doesnt_exist` tampoco trae contenido.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: el código lo cumple; `Borde._respuesta` devuelve `resultado`, `version` y `contenido`, y para `rechaza` y `file_doesnt_exist` devuelve `version=None` y `contenido=None`. Guardar los bytes en `Copia.contenido` es lo que hace que un `hit` no toque el origen y lo que da sentido a la expulsión por capacidad (F1-S06).

### 2026-11-16 — `rechaza` solo cuando ninguna fuente entrega el archivo

- Decisión: si el primer borde no puede servir el recurso y el origen no contesta, la selección prueba el otro borde. Una copia fresca en ese otro borde es `hit`. El origen contestando con el archivo es `miss`. Una copia no invalidada dentro de `STALE_LIMIT`, con el origen en silencio, es `sirve_obsoleta`. `rechaza` queda para cuando los dos bordes y el origen no pueden entregar el archivo.
- Alternativas consideradas: rechazar en cuanto el primer borde no tiene una copia usable, sin preguntar al otro.
- Por qué esta: en una caché normal un nodo caído o vacío no es el final del pedido. Otro borde puede tener el archivo. El cliente ve el fallo cuando ya no queda fuente.
- Qué no resuelve: no fija el orden entre los bordes ni la política cuando hay más de dos. La fase 1 corre con dos bordes. La política concreta de selección la implementa Samy.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: hay dos niveles de `rechaza`. El borde responde `rechaza` cuando él agotó sus fuentes (copia no usable y origen en silencio); el cliente lo traduce en «probar el siguiente borde» y solo anota `respuesta resultado=rechaza fuente=ninguna` cuando ningún borde entregó (`fase1/cliente.py`, F1-S07). Conviene que esta entrada o el contrato lo digan. El orden entre bordes que aquí queda abierto lo fija la entrada del 19 nov («Política de selección»): la lista `Config.bordes`. Consecuencia aceptada: si el primer borde sirve `sirve_obsoleta`, el cliente no pregunta al otro aunque tenga una copia fresca.

### 2026-11-16 — Una copia invalidada no se sirve si el origen no contesta

- Decisión: si el origen invalidó una copia y el borde no logra hablar con el origen para bajar la versión nueva, esa copia no se responde. `STALE_LIMIT` no la habilita. El cliente la recibe solo si otra fuente entrega un archivo que sí se puede usar. Si el origen contesta, el borde baja la versión nueva y el resultado es `miss`.
- Alternativas consideradas: tratar la copia invalidada como una copia vencida y servirla dentro de `STALE_LIMIT`.
- Por qué esta: en una caché normal la invalidación es una orden de no servir esa versión. El límite de obsolescencia cubre una copia vencida o una revalidación que no pudo hacerse, no una versión que el origen mandó quitar.
- Qué no resuelve: no describe cómo se simula el aviso perdido. Ese caso sigue en el borde que no recibió la invalidación: su copia no está invalidada y sigue la regla de frescura.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: de acuerdo con la regla; la diferencia es que obsoleta por TTL es «no sé si cambió» (cabe una cota de tiempo) e invalidada es «me dijeron que cambió» (no cabe). En el borde esto será la causa `invalidada` en la línea `miss` y la rama `rechaza causa=invalidada` de la regla de obsoleto; se implementa cuando exista F1-R06.
- Preguntas abiertas para Rubén (F1-R06, F1-R07), propuesta de Samy el 19 nov:
  1. Cómo llega el aviso al borde. **Respondida el mismo día por la entrada «La invalidación sale del origen hacia los bordes anotados»**: el arranque llama `origen.anotar_bordes(bordes)` y el origen llama `borde.invalidar(pedido_id, recurso, version)`. Por la noche Rubén cambió el borrado por la marca (entrada «El aviso recibido marca la copia, no la borra»), así que esta entrada vale tal cual: `miss causa=invalidada` y, con el origen en silencio, `rechaza causa=invalidada` (F1-S09).
  2. Cómo se simula el aviso perdido (el tablero pide dejarlo escrito). Sigue abierta (F1-R07). Propuesta: `origen.invalidar(pedido_id, recurso, saltar=[...])`, que avisa a todos los bordes anotados menos a los de `saltar` y anota `invalidar … bordes=… perdido=…`; el borde saltado conserva la copia vieja hasta expirar o revalidar. Es reproducible y no necesita tocar la red.

### 2026-11-16 — El origen dice que el archivo no existe

- Decisión: si el origen contesta y el recurso no está, el resultado del cliente es `file_doesnt_exist` («file doesn't exist»). No hay versión ni contenido. El borde borra esa copia en ese momento; la regla está en la entrada de borrado.
- Alternativas consideradas: usar `rechaza` para este caso y mantener solo los cuatro resultados del README.
- Por qué esta: `rechaza` en este proyecto es «había algo que decidir y ninguna fuente pudo entregarlo». Aquí el origen sí contestó y dijo que el archivo no existe. El token va sin espacios para poder escribirlo en la línea de historial: `resultado=file_doesnt_exist`.
- Qué no resuelve: no se usa este resultado cuando el origen está en silencio. En ese caso siguen `sirve_obsoleta` y `rechaza`.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: es un quinto resultado que el README no tiene; separa «nadie contesta» de «contestaron que no existe». Solo aparece cuando el origen habla; con el origen en silencio siguen `sirve_obsoleta` y `rechaza` aunque el archivo ya no esté en disco, porque el borde no puede saberlo. Implementado en `fase1/borde.py` desde F1-S04; desde el 19 nov el borde además anota `borra recurso=… version=… causa=file_doesnt_exist` cuando tenía copia, para que el historial del borde diga que la quitó.

### 2026-11-16 — TTL provisional de 30 segundos

- Decisión: una copia está fresca durante `TTL = 30` segundos desde que se guarda o desde que el origen confirma la misma versión. Después queda obsoleta. `STALE_LIMIT` sigue midiendo solo el tiempo que lleva obsoleta.
- Alternativas consideradas: un TTL de varios minutos, como en una caché pública; no fijar el número hasta el experimento.
- Por qué esta: 30 segundos dejan ver una copia fresca, el paso a obsoleta y las dos ramas de `STALE_LIMIT` (60 segundos) sin alargar la corrida. Es provisional, igual que el límite.
- Qué no resuelve: no es el valor de la entrega. Se vuelve a mirar al cerrar el experimento de partición.
- Dónde está en el código: `docs/contrato.md`. Cuando exista el borde, el valor sale de la configuración.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: ya está en el código, `fase1/config.py` (`ttl_segundos`, `P20_TTL`) y `fase1/borde.py` (`Copia.expira_en`; `_renovar` vuelve a contar desde la confirmación del origen, como dice esta entrada). Línea de tiempos de una copia: fresca 0–30 s; obsoleta y servible si el origen calla 30–90 s; después no se sirve. Un TTL por archivo decidido por el origen (como `max-age` en HTTP) sería más fiel a una CDN real; queda como posible mejora de la fase 2, no de esta.

### 2026-11-16 — Misma versión en la revalidación es `hit`

- Decisión: si el borde pregunta al origen y el origen confirma la misma versión, el resultado del cliente es `hit`. La copia permanece y el TTL vuelve a empezar. `miss` queda para cuando el origen entrega otro contenido.
- Alternativas consideradas: anotar `miss` cada vez que el borde tuvo que preguntar al origen, aunque el archivo no cambiara.
- Por qué esta: en una caché normal esa respuesta confirma la copia que ya estaba. El cliente recibe el archivo del borde. El historial del borde puede llevar además la línea `revalida`.
- Qué no resuelve: no cambia `sirve_obsoleta` ni `rechaza`, que siguen siendo los casos en los que el origen no contesta.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: implementado en `fase1/borde.py` (`_con_respuesta_del_origen`: `revalida … renovo=si` y luego `hit estado=fresca`; se ve en `fase1.escenarios ttl`). El caso `revalida … renovo=no bajo_otra=si` seguido de `guarda` es el estado «actualizada» del README §5: no es un estado guardado, es la transición. Desde F1-R08, si la versión coincide, `responder` contesta `misma=si` y `contenido=None`: el archivo no vuelve a bajar.
- Pregunta abierta para Rubén (F1-R08), propuesta de Samy el 19 nov: `responder(pedido_id, recurso, version_local=None)`. Resuelta el mismo día: se adoptó esa firma. Ver «Revalidación del origen sin bytes si la versión coincide».

### 2026-11-16 — Cuándo el borde borra una copia

- Decisión: el borde borra la copia al momento en tres casos. El origen, al pedirla el borde, responde que ya no está. Llega la invalidación de esa copia. La edad obsoleta pasó `STALE_LIMIT` y el origen responde que esa copia es obsoleta; si además entrega una versión nueva, el borde guarda esa y el cliente ve `miss`. Si el origen sigue en silencio, la copia no se borra. Solo puede salir por expulsión LRU cuando el borde se llena.
- Alternativas consideradas: borrarla 1 o 2 minutos después de saber que el origen ya no la tiene; borrarla en cuanto pasa el TTL; borrarla también cuando pasó `STALE_LIMIT` y el origen sigue en silencio.
- Por qué esta: la copia se quita cuando el borde ya sabe que no debe guardarla. El silencio del origen no es esa noticia: durante `STALE_LIMIT` esa copia es la que se sirve, y pasada esa edad el proyecto aún la conserva hasta que LRU necesite el sitio o el origen hable.
- Qué no resuelve: no elige qué copia saca LRU ni la capacidad del borde. Eso lo implementa Samy.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: de acuerdo con la regla de fondo (se borra cuando el borde sabe que no debe guardarla; el silencio no es saber). Retoque sugerido: el tercer caso no existe como caso aparte con la API actual. Si el origen contesta, o confirma la misma versión (`hit`), o entrega otra (se reemplaza, `miss`), o dice que no existe (`file_doesnt_exist`); no hay una respuesta «es obsoleta» sin archivo, y da igual si la copia pasó `STALE_LIMIT`. Simplificar a «el origen entrega otra versión: se reemplaza». Consecuencia en el borde (F1-S06): una copia obsoleta o superada ocupa sitio igual que una fresca y puede ser expulsada por LRU, que no mira el estado. Borrar al pasar el TTL habría dejado sin copia para `sirve_obsoleta`.

### 2026-11-16 — Archivos del origen en carpeta local

- Decisión: el origen lee los archivos de la carpeta local `contenido/`. Cada archivo que aparece ahí empieza en versión `1`. Cuando el contenido de ese archivo cambia, la versión sube en `1`. Si el archivo se borra de la carpeta, el origen responde `file_doesnt_exist`.
- Alternativas consideradas: generar el contenido en memoria; numerar versiones a mano en un archivo aparte; subir la versión en saltos mayores.
- Por qué esta: se puede editar o borrar un archivo del disco y provocar miss, revalidación, invalidación y `file_doesnt_exist` sin inventar un almacén. Empezar en 1 y subir de 1 en 1 deja las versiones visibles en el historial.
- Qué no resuelve: cómo se detecta el cambio quedó en la entrada del hash.
- Dónde está en el código: `contenido/` y `fase1/origen.py` (`responder`, `_version_y_bytes`).
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: de acuerdo; es lo que hace el experimento reproducible (se edita o borra un archivo y el historial muestra la versión). El 19 nov Samy agregó `contenido/apunte-2.txt` y `apunte-3.txt` para que el escenario LRU llene un borde de capacidad 2.
- Pregunta abierta para Rubén (F1-R06), propuesta de Samy el 19 nov: el origen solo se entera de un cambio cuando alguien pide el archivo (`responder` hashea al leer). Para invalidar hace falta detectar el cambio antes de que nadie pida. Propuesta: un método `origen.invalidar` que se llama a mano en el experimento: relee el archivo, sube la versión si el hash cambió, avisa a los bordes y anota `invalidar`. Es más simple y más reproducible que un barrido periódico de la carpeta. **Respondida el mismo día**: `origen.invalidar(pedido_id, recurso)` hace exactamente eso (entrada del 19 nov de Rubén).

### 2026-11-16 — Hash del contenido para subir la versión

- Decisión: la única señal para subir la versión de un archivo en el origen es el hash de su contenido (SHA-256 de los bytes). El origen guarda la última huella vista junto con la versión. Si al leer el archivo la huella es distinta, el contenido cambió y la versión sube en `1`. La fecha de modificación del disco no se usa.
- Alternativas consideradas: usar solo la fecha de modificación (`mtime`); usar fecha y, si cambió, confirmar con hash.
- Por qué esta: la versión tiene que reflejar el contenido que se reparte. El hash solo sube cuando los bytes cambian de verdad. La fecha sola puede subir la versión con un `touch` sin cambio, o fallar al copiar un archivo con fecha antigua. Con pocos archivos chicos en `contenido/`, hashear en cada lectura es aceptable.
- Qué no resuelve: no cifra ni firma el archivo; solo detecta cambio.
- Dónde está en el código: `fase1/origen.py`, estado `_versiones` (versión + hash) y `_version_y_bytes`.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: de acuerdo; el hash detecta cambio, no integridad ni autenticidad (eso es TLS, el plus). Para la fase 2, no para esta: `_versiones` vive en la memoria del actor; si el origen se reinicia, todo vuelve a versión 1 y un borde con versión 3 verá «otra versión» y bajará una con número menor. En la fase 1 el origen no se reinicia en la corrida y se acepta; en la fase 2 el origen es dueño de la versión de referencia (F2-R09) y tendrá que persistir versión y hash. Por eso el borde compara con igualdad (`copia.version == version_origen`), no con «mayor que»: el origen manda y los números son etiquetas.

### 2026-11-16 — Origen como actor Ray

- Decisión: el origen de la fase 1 es un actor Ray (`@ray.remote`) en `fase1/origen.py`. Se arranca en local con `fase1/arrancar_origen.py`. Confirma que vive con `listo` y reparte archivos con `responder`.
- Alternativas consideradas: un proceso Python sin Ray; un script que solo importa Ray sin crear actor.
- Por qué esta: la fase 1 tiene que correr varios procesos de verdad. El actor es el proceso origen que el borde llamará.
- Qué no resuelve: todavía no invalida bordes (F1-R06) ni tiene la API fina de revalidación (F1-R08). La línea `listo` sigue siendo solo prueba de arranque.
- Dónde está en el código: `fase1/origen.py`, `fase1/arrancar_origen.py`.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: de acuerdo; es el espejo de la entrada del 17 nov (borde y cliente como actores): cuatro nodos en cuatro procesos. La línea `listo` con `pedido=arranque` no está en la tabla del README; es prueba de arranque y deja en el log la configuración con la que arrancó cada nodo, útil como evidencia en las fichas.

### 2026-11-17 — Borde y cliente como actores Ray; el selector, junto al cliente

- Decisión: el borde y el cliente son actores Ray (`@ray.remote`), uno por proceso, igual que el origen. El cliente recibe los handles de los bordes al crearse. La selección de fuente no es un nodo: será un módulo que vive junto al cliente (F1-S07), como dice `docs/contrato.md` («la selección, que vive junto al cliente, escoge la fuente»).
- Alternativas consideradas: cliente como script del lado del usuario sin actor; selector como un actor aparte al que el cliente le pregunta.
- Por qué esta: la fase 1 tiene que correr en varios procesos de verdad, y el cliente es «un proceso distinto del origen y de los bordes» (contrato). Un selector como nodo aparte sería un componente inventado solo para la fase 1 y un punto más de fallo que el README no pide.
- Qué no resuelve: esta decisión no fija el orden entre bordes ni el tiempo de espera. El selector y `ray.wait` quedaron en F1-S07. El selector sigue dentro del proceso del cliente, no como un actor aparte.
- Dónde está en el código: `fase1/borde.py`, `fase1/cliente.py`, `fase1/arrancar_sistema.py`. El selector, desde F1-S07, está en `fase1/selector.py`.
- Implementa: Samy
- Revisa: Rubén (19 nov). Observaciones de la revisión: de acuerdo; el selector no es un actor, vive en el proceso del cliente. Se quitó la frase que decía que el cliente pide siempre al primer borde y espera sin límite: desde F1-S07 usa `ray.wait` y pasa al siguiente. La explicación está en `docs/explicaciones.md`.

### 2026-11-17 — La configuración en un solo archivo, con sobreescritura por entorno

- Decisión: TTL, `STALE_LIMIT`, capacidad, política de expulsión, tiempo de espera, `cifrado` y el orden de los bordes viven en `fase1/config.py` (`Config`). Los cuatro números se pueden cambiar con variables de entorno `P20_*` para una corrida corta de prueba, sin tocar el código.
- Alternativas consideradas: constantes repartidas en cada archivo; argumentos de línea de comandos en cada script de arranque.
- Por qué esta: la guía (parte 6) pide que «esos valores vivan juntos, para poder cambiarlos sin buscarlos por todo el código», y las notas del profesor del Lab 0 piden que la configuración esté a la vista y se pase como parámetro, no escondida en el código. El entorno es la forma más corta de hacerlo sin cambiar la firma de los actores.
- Qué no resuelve: los valores siguen siendo provisionales (decisiones del 16 nov). La lista de bordes es estática: es el arranque estático que el tablero da por válido si queda justificado, y queda justificado aquí: en la fase 1 el descubrimiento lo hace Ray con los handles, y en la fase 2 la lista pasará a direcciones en la configuración.
- Dónde está en el código: `fase1/config.py`.
- Implementa: Samy
- Revisa: Rubén (19 nov). Observaciones de la revisión: de acuerdo; TTL, `STALE_LIMIT`, capacidad, timeout y el orden de los bordes están en `Config`, y `desde_entorno` los cambia con `P20_*`.

### 2026-11-18 — La copia del borde vive en memoria, con versión, bytes y hora de guardado

- Decisión: el borde guarda cada copia como `Copia(version, contenido, guardada_en)` en un diccionario en la memoria del actor (`_copias`). Un pedido con copia es `hit` y no toca el origen. Un pedido sin copia anota `miss causa=no_esta`, luego `pide_origen`, baja el archivo, anota `guarda` y responde `miss`. Si el origen contesta `file_doesnt_exist`, el borde borra la copia de ese nombre, como dice el contrato. La línea `miss` lleva `causa` para que, cuando lleguen TTL e invalidación, el historial diga por qué no sirvió la copia (`no_esta`, `expirada`, `invalidada`).
- Alternativas consideradas: guardar las copias en disco (`logs/` o una carpeta `cache/` por borde) para que sobrevivan al reinicio del actor; guardar solo nombre y versión y volver a bajar el contenido en cada hit.
- Por qué esta: la fase 1 solo tiene que mostrar los comportamientos de caché, y la guía (parte 6, paso 3) describe el borde como «guarda lo que baja y lo entrega si lo tiene». Guardar los bytes es lo que hace que el hit no hable con el origen; sin ellos no habría hit de verdad. Una caché solo en memoria es la descripción honesta que pide el tablero para la ficha de reinicio (F3-S03): si el borde muere, arranca vacío y el primer pedido es `miss`.
- Qué no resuelve: la copia no sobrevive al reinicio del actor. La expiración, la expulsión LRU, la revalidación y `STALE_LIMIT` están en F1-S05, F1-S06, F1-S08 y F1-S09. `guardada_en` es el instante desde el que cuenta el TTL.
- Dónde está en el código: `fase1/borde.py` (`Copia`, `_copias`, `pedir`, `_guardar`, `estado`). La corrida de `fase1/arrancar_sistema.py` muestra miss, hit y `file_doesnt_exist` seguidos.
- Implementa: Samy
- Revisa: Rubén (19 nov). Observaciones de la revisión: de acuerdo; la corrida de esa noche dejó `725bee` en miss y `guarda`, `3855ec` en hit sin línea del origen, y `3e8e8c` en `file_doesnt_exist`. Se quitó la frase que decía que la copia no tenía expiración, LRU, revalidación ni `STALE_LIMIT`: esas cuatro piezas ya están. Lo que sigue sin resolver es el reinicio del actor. Hit, miss, timeout y `STALE_LIMIT` están en `docs/explicaciones.md`.

### 2026-11-19 — TTL en el borde: `expira_en`, y qué pasa con una copia obsoleta

- Decisión: cada `Copia` lleva `expira_en = guardada_en + TTL`. Antes de esa hora está fresca y se sirve como `hit` sin hablar con el origen. Después está obsoleta: el borde anota `miss causa=expirada` (con la versión local, la hora en que expiró y los segundos que lleva obsoleta) y `pide_origen … version=N`, y pregunta al origen. Si el origen confirma la misma versión, la copia se queda, el TTL vuelve a contar desde ahora (`_renovar`), se anota `revalida … renovo=si` y el cliente ve `hit`. Si el origen trae otra versión, se anota `revalida … renovo=no bajo_otra=si`, se guarda la nueva y el cliente ve `miss`. La copia obsoleta nunca se borra por sí sola: solo la reemplaza el origen, la quita `file_doesnt_exist`, la invalidación o la expulsión LRU (decisión del 16 nov, «Cuándo el borde borra una copia»).
- Alternativas consideradas: borrar la copia al expirar y tratarla como `no_esta` (más simple, pero deja sin copia para `sirve_obsoleta` y contradice el contrato); responder `miss` siempre que hubo que preguntar al origen aunque la versión fuera la misma (contradice la entrada «Misma versión en la revalidación es `hit`»); un hilo que expire copias por su cuenta (una decisión más que tomar en la fase 2 sin ganancia en la fase 1).
- Por qué esta: el README (§5) pide los estados fresca → obsoleta → actualizada y que el historial lleve la edad y la expiración como datos; el contrato dice que la misma versión confirmada es `hit` y que `STALE_LIMIT` mide el tiempo obsoleta, así que la copia tiene que seguir guardada con su `expira_en` para que F1-S09 pueda calcular esa edad. La expiración se evalúa al pedir, no con un reloj aparte: es la forma más corta y deja la decisión a la vista en `pedir`.
- Qué no resuelve: el TTL de 30 s sigue siendo el provisional de la decisión del 16 nov. Si la versión coincide, el origen no manda los bytes (F1-R08 y F1-S08). Si no contesta, el borde aplica el timeout y `STALE_LIMIT` (F1-S09).
- Dónde está en el código: `fase1/borde.py` (`Copia.expira_en`, `Copia.fresca`, `pedir`, `_con_respuesta_del_origen`, `_renovar`, `estado`). Escenario `ttl` en `fase1/escenarios.py`.
- Implementa: Samy
- Revisa: Rubén (19 nov). Observaciones de la revisión: de acuerdo. Corrida `P20_TTL=3`: `026f92` miss y `guarda`, `d5ebb2` hit fresca, estado `obsoleta` al pasar el TTL, `43aea3` con `responde misma=si` sin bytes, `revalida renovo=si` y hit. Se quitó la frase que decía que la revalidación baja el archivo entero y que no hay timeout.

### 2026-11-19 — Expulsión LRU con un `OrderedDict`, capacidad 2, visible en el log

- Decisión: `_copias` es un `OrderedDict` en orden de uso: la primera copia es la menos usada recientemente. Un `hit` y un guardado o renovación mueven la copia al final. Cuando llega un recurso nuevo y ya hay `capacidad` copias, sale la primera y se anota `expulsion recurso=<sale> version=… politica=LRU entra=<entra>` antes de `guarda`. Reemplazar una copia que ya estaba (otra versión del mismo recurso) no cuenta como entrada nueva y no expulsa. `capacidad = 2` en la configuración, a propósito pequeña para ver la expulsión en una corrida de tres archivos.
- Alternativas consideradas: FIFO (más simple, pero el README lo deja como segunda política y el tablero la pospone a F2-R04 «solo si el núcleo ya está verde»); una lista aparte con las horas de último uso (lo mismo con más código); contar la capacidad en bytes en vez de en copias.
- Por qué esta: el tablero pide «expulsión LRU con capacidad pequeña, visible en el log» y el README (§4) deja la política como decisión del proyecto; LRU es la que una caché de contenido usa normalmente, y el `OrderedDict` de la biblioteca estándar la expresa sin estructura propia. Contar copias y no bytes es suficiente con archivos chicos y hace predecible el escenario.
- Qué no resuelve: no hay segunda política para comparar (si entra, en la fase 2). Una copia obsoleta o invalidada también puede ser expulsada: LRU no mira el estado, solo el uso. El origen no se entera de la expulsión; el siguiente pedido es `miss causa=no_esta`.
- Dónde está en el código: `fase1/borde.py` (`_copias`, `move_to_end` en `pedir` y `_renovar`, `_guardar`). `capacidad` y `expulsion` en `fase1/config.py`. Escenario `lru` en `fase1/escenarios.py`.
- Implementa: Samy
- Revisa: Rubén (20 nov). Observaciones de la revisión: de acuerdo. Corrida de esa noche: tras el hit de `apunte.txt` (`e118e5`), `apunte-3.txt` (`b0433f`) expulsa `apunte-2.txt` con `politica=LRU`, y al volver a pedirlo (`8b6d05`) es `miss causa=no_esta` y expulsa `apunte.txt`. Se quitó «cuando exista»: la copia invalidada ya existe y LRU también puede expulsarla.

### 2026-11-19 — Política de selección: orden fijo de bordes, el que no responde va al final un rato

- Decisión: el selector (`fase1/selector.py`) vive en el proceso del cliente y da, para cada pedido, la lista de bordes en el orden de `Config.bordes` (el primero es el «más cercano»). El cliente anota `solicitud … fuente=<borde>` por cada borde que prueba y lo llama con tiempo de espera `timeout_segundos` (2 s). «No responde» es una de dos cosas, cada una con su línea: `timeout` (la llamada no volvió a tiempo) o `nodo_caido` (el actor del borde murió y Ray devuelve `RayActorError`). Un borde que no respondió se deja al final de la lista durante `evitar_borde_segundos` (10 s) y luego recupera su lugar; nunca se descarta. Si un borde contesta `rechaza`, el cliente prueba el siguiente (contrato, «Cuándo el cliente ve `rechaza`»). La primera respuesta que entrega algo, o `file_doesnt_exist`, es la final. Si ningún borde entrega, el cliente anota `respuesta resultado=rechaza fuente=ninguna`. El cliente nunca le pide al origen: el origen no es una fuente del selector; es el borde quien baja de ahí.
- Alternativas consideradas: que el cliente hable con el origen como última fuente (el README §8 lo permite: «si se utiliza otro borde o el origen»); elegir el borde por el que tenga el recurso o la copia más fresca (haría falta preguntar el estado a todos los bordes antes de cada pedido, o que los bordes se hablen entre sí); descartar para siempre un borde caído; repartir los pedidos entre los bordes por turnos.
- Por qué esta: el README pide que la selección sea «una política explícita y configurable, no una decisión implícita», y la decisión del 16 nov deja la política concreta a Samy. Una lista de preferencia en la configuración es la política más corta que se puede leer y cambiar, y es coherente con «el borde preferido que responda» de `fase1/config.py`. Dejar al final al que no respondió, en vez de descartarlo, es lo que permite que un borde que vuelve se use otra vez sin que nadie lo reinscriba. Que el cliente no hable con el origen mantiene al origen detrás de los bordes, que es la forma de una CDN, y deja la regla de obsoleto en un solo sitio (el borde). Preguntar el estado a todos los bordes sería una decisión de diseño distribuida más (membresía, consulta) que la fase 1 no necesita.
- Qué no resuelve: con el orden fijo, si `borde-1` tiene una copia obsoleta dentro de `STALE_LIMIT` y el origen está en silencio, se sirve esa copia aunque `borde-2` tenga una fresca: el cliente no lo sabe y los bordes no se hablan. Es una consecuencia aceptada de la política; queda escrita para el experimento y para la fase 2. `timeout` no se prueba en `escenarios.py` porque haría falta un borde lento (ficha F3-R03). La partición entre un borde y el origen no pasa por el selector: es el borde quien la detecta (F1-S09, F1-R09).
- Dónde está en el código: `fase1/selector.py` (`Selector`), `fase1/cliente.py` (`pedir`, `_llamar_borde`), `fase1/config.py` (`bordes`, `timeout_segundos`, `evitar_borde_segundos`). Escenario `selector` en `fase1/escenarios.py`.
- Implementa: Samy
- Revisa: Rubén (20 nov). Observaciones de la revisión: de acuerdo. Corrida `selector`: `6701c3` miss por `borde-1`; `7520f1` anota `nodo_caido destino=borde-1` y una segunda `solicitud` a `borde-2`; `d39273` no intenta `borde-1` y es hit en `borde-2`. El paso tras un `rechaza` se vio en la partición (`010bd0`, `supera_limite`). Sigue abierto el borde lento (F3-R03) y que una obsoleta de `borde-1` no hace preguntar a `borde-2`.

### 2026-11-19 — La invalidación sale del origen hacia los bordes anotados

- Decisión: el origen no descubre bordes. El arranque se los pasa con `anotar_bordes` (la misma lista estática de `Config.bordes`). `invalidar(pedido_id, recurso)` lee el disco, deja la versión de referencia al día y llama a `invalidar` de cada borde. La línea del origen lleva el recurso, la versión nueva y solo los bordes que contestaron (`bordes=borde-1,borde-2`). El borde, al recibir, borra esa copia y anota `invalidacion_recibida`. El cliente no participa. El pedido siguiente es un miss normal (`causa=no_esta`) y baja la versión nueva.
- Alternativas consideradas: subir la versión solo dentro de `responder`, para que el borde se entere cuando pregunte, sin un aviso empujado; que el cliente reenvíe la invalidación; avisar solo a los bordes que alguna vez pidieron ese recurso; marcar la copia como invalidada y dejarla guardada, en vez de borrarla.
- Por qué esta: el README dibuja la invalidación como flechas del origen a cada borde, y el historial pide en la línea del origen el recurso, la versión nueva y los bordes avisados. El origen no sabe quién guardó la copia (tampoco se entera de una expulsión), así que avisa a todos los que el arranque le anotó. Borrar al recibir es el contrato del 16 nov («Llega la invalidación de esa copia»). Dejar el aviso fuera de `responder` permite invalidar sin esperar a que alguien pida.
- Qué no resuelve: un borde que no contesta no entra en la lista, pero la línea `invalidacion_perdida` es F1-R07. Como la copia se borra al llegar el aviso, el historial no usa `miss causa=invalidada`. El aviso no tiene timeout. El origen no invalida solo por ver un cambio de hash en `responder`: hace falta llamar a `invalidar`.
- Dónde está en el código: `fase1/origen.py` (`anotar_bordes`, `invalidar`), `fase1/borde.py` (`invalidar`), el arranque en `fase1/arrancar_sistema.py` y `fase1/escenarios.py`. Escenario `python3 -m fase1.escenarios invalidar`.
- Implementa: Rubén
- Revisa: Samy (20 nov). Observaciones de la revisión: de acuerdo; es el único mensaje origen → bordes y es empujado (llega antes de que alguien pida), y el origen avisa a todos los anotados porque no sabe quién guarda copia. Responde la pregunta abierta de la decisión «Archivos del origen en carpeta local»: el cambio se detecta llamando a `invalidar` a mano. Tres cosas: (1) el aviso no tiene timeout (`ray.get` por borde): un borde muerto se salta, uno colgado bloquea al origen; vale para la fase 1 y en la fase 2 el aviso lleva timeout (F2-S06). (2) Invalidar sin cambio en disco también marca la copia y el siguiente pedido la vuelve a bajar con el mismo número; el experimento cambia el archivo antes. (3) «Qué no resuelve» todavía dice que el historial no usa `miss causa=invalidada`; desde la marca sí lo usa: actualizar esa frase.

### 2026-11-19 — Cómo se simula una invalidación que un borde no aplica

- Decisión: `perder_avisos(True)` en un borde hace que `invalidar` no marque la copia y anote `invalidacion_perdida` con el recurso y la versión que se quedó. El método devuelve `None` y el origen no pone a ese borde en `bordes=`. La copia sigue la regla de frescura: si el TTL no venció, el siguiente pedido a ese borde es `hit` de la versión vieja. El otro borde, si aplicó el aviso, deja la copia marcada `invalidada`.
- Alternativas consideradas: no llamar a ese borde desde el origen (entonces el borde no puede escribir la línea, y el README la asigna al borde); matar el actor (eso es `nodo_caido`: el cliente tampoco puede pedirle, y no queda la copia servible); marcar la copia `invalidada` sin borrarla en el borde que sí recibió el aviso.
- Por qué esta: el tablero pide el caso en que un borde no aplica la invalidación y que eso quede anotado. En Ray, si el actor vive, la llamada llega. El interruptor es la simulación: el aviso entra y no se aplica. No es un borde caído. La decisión del 16 nov ya decía que la copia que no recibió la invalidación sigue la regla de frescura.
- Qué no resuelve: el borde sabe que soltó el aviso porque el interruptor es local. En la fase 2 un mensaje perdido no llega, y el borde no escribiría la línea por sí solo. Aquí la escribe para que el historial de la fase 1 tenga la evidencia. Un actor ya muerto sigue sin línea `invalidacion_perdida`.
- Dónde está en el código: `fase1/borde.py` (`perder_avisos`, la rama de `invalidar`), `fase1/origen.py` (no cuenta un `None` en `bordes`). Escenario `python3 -m fase1.escenarios perdida`.
- Implementa: Rubén
- Revisa: Samy (20 nov). Observaciones de la revisión: de acuerdo; en Ray la llamada llega si el actor vive, así que el interruptor local es la única simulación honesta, y es mejor que la propuesta de Samy de un `saltar=[…]` en el origen porque el README asigna la línea `invalidacion_perdida` al borde. Para la ficha F3-S04: el borde «sabe» que perdió el aviso solo por el interruptor; con un mensaje perdido de verdad (fase 2) esa línea no existe y la evidencia es la ausencia del borde en `bordes=` del origen. Tras un aviso perdido el sistema converge solo: el borde sirve la versión vieja hasta que su TTL vence, revalida, y el origen le da la nueva. TTL e invalidación se necesitan mutuamente.

### 2026-11-19 — El aviso recibido marca la copia, no la borra

- Decisión: cuando el borde recibe la invalidación, no borra el archivo. Deja la copia marcada como no válida (`Copia.invalidada`) y no la devuelve aunque se la pidan. El pedido anota `miss causa=invalidada` y pregunta al origen. Si el origen entrega el archivo, el cliente ve `miss` y esa copia nueva reemplaza a la invalidada. Si dice que no está, ahí sí se borra (`borra`). `STALE_LIMIT` no alcanza para servirla. El aviso que no se aplica (F1-R07) no cambia: esa copia sigue válida y se puede devolver.
- Alternativas consideradas: borrarla al recibir, como decía el contrato del 16 nov; devolverla igual si todavía estaba fresca.
- Por qué esta: si se borra, el pedido siguiente parece un `miss causa=no_esta` y no se distingue de un archivo que nunca estuvo. La copia tiene que seguir para poder negarla.
- Qué no resuelve: si el origen no contesta, el pedido se queda esperando. El tiempo de espera y el `rechaza` de ese caso llegan con F1-S09.
- Implementa: Rubén
- Revisa: Samy (19 nov). Observaciones de la revisión: de acuerdo; Samy había aplicado la misma marca en el borde esa tarde y se quedó con la versión de Rubén más dos cosas: la línea `invalidacion_recibida` lleva `version_local`, `version` y `habia_copia=si|no` para distinguir un borde que tenía copia de uno que no, y con el origen en silencio la copia invalidada da `rechaza causa=invalidada` (F1-S09, misma fecha). Adoptado también su criterio de que una copia invalidada nunca se renueva como `hit`: el borde no manda `version_local` en ese caso (decisión «Revalidación del lado borde»).

### 2026-11-19 — Revalidación del origen sin bytes si la versión coincide

- Decisión: `responder(pedido_id, recurso, version_local=None)`. Si `version_local` es igual a la versión del disco, el origen responde `misma=si` y no manda bytes. Si no es igual, manda el archivo y anota `misma=no`. Si `version_local` no viene, la llamada sigue siendo una bajada normal, con bytes. Si el archivo no está, `file_doesnt_exist`, aunque haya venido `version_local`. La comparación es por igualdad.
- Alternativas consideradas: un método aparte `revalidar` que solo diga si es la misma versión, y dejar el archivo siempre en `responder`; comparar con «mayor que» en vez de igualdad.
- Por qué esta: es la propuesta de Samy del 19 nov, y es lo que hace una caché HTTP con `If-None-Match`: `304 Not Modified` sin cuerpo si el validador coincide, y `200` con el archivo si cambió. Una sola llamada le basta al borde. Igualdad, y no «mayor que», porque el número es una etiqueta: si el origen reinicia y vuelve a 1, esa es la versión de referencia.
- Qué no resuelve: el borde todavía baja el archivo entero para revalidar. Pasar `copia.version` y tratar `misma` es F1-S08.
- Dónde está en el código: `fase1/origen.py`, método `responder`. Escenario `python3 -m fase1.escenarios revalidar`.
- Implementa: Rubén
- Revisa: Samy (20 nov). Observaciones de la revisión: de acuerdo; es `If-None-Match` / `304` con una sola llamada, y el borde la usa desde F1-S08 (manda `version_local` solo si la copia expiró; una invalidada se reemplaza, no se confirma). Dos notas para la fase 2: `responder` hashea el archivo en cada llamada, también al revalidar, lo que hace que la versión suba sola si alguien editó sin llamar a `invalidar`; el origen HTTP debería tener la versión calculada en el `PUT` y no releer en cada `GET`. Y el origen reiniciado vuelve a versión 1 y diría `misma=si` a una copia con versión 1 de otro contenido (ver la revisión de «Hash del contenido»). El circuito en el historial, con el mismo `pedido_id`: `pide_origen … version=N` (borde), `responde … misma=si` (origen), `revalida renovo=si` (borde).

### 2026-11-19 — Qué es «el origen no responde» y la regla de obsoleto en el borde

- Decisión: el borde llama al origen con `ray.wait(timeout=timeout_segundos)` (2 s en la configuración). «No responde» es una de tres cosas, cada una con su línea en el historial: la llamada no volvió a tiempo (`timeout destino=origen`), el actor del origen murió (`nodo_caido destino=origen`, por `RayActorError`), o la partición simulada está activa (`timeout destino=origen causa=particion`). En los tres casos el borde anota `origen_no_responde recurso=… edad_segundos=… stale_limit=…` y aplica la regla: sin copia → `rechaza causa=no_esta`; copia invalidada → `rechaza causa=invalidada`; copia obsoleta con `edad_segundos <= STALE_LIMIT` → `sirve_obsoleta`; si la supera → `rechaza causa=supera_limite`. La edad es el tiempo desde `expira_en`, no desde que se guardó. La copia que supera el límite no se borra. El borde no reintenta la llamada: si el origen vuelve, el siguiente pedido lo nota solo.
- Alternativas consideradas: esperar sin límite (lo que hacía el código hasta hoy: el pedido se bloquea y el cliente también); reintentar una o dos veces antes de dar por perdido al origen; un timeout distinto para el cliente→borde y el borde→origen; medir la edad desde que se guardó la copia.
- Por qué esta: el README (§9, §10) pide una condición explícita, y el tablero pide dejar escrito «qué se considera el origen no responde». Un solo número (`timeout_segundos`) para las dos llamadas es lo más corto de explicar y de cambiar. Sin reintento, porque el reintento sería una segunda espera de 2 s y la decisión de qué hacer con la copia ya la toma la regla; el README dice que la edad y el límite se escriben como datos de la línea, y así quedan. Medir desde `expira_en` es lo que fija el contrato («`STALE_LIMIT` mide cuánto tiempo lleva obsoleta»).
- Qué no resuelve: la partición es un interruptor local (`particion(True)`), no un corte de red: Ray entregaría la llamada si la hiciéramos. Es la forma reproducible de provocar el experimento en la fase 1; en la fase 2 se corta con la red. `timeout` de verdad (origen lento, no muerto ni partido) no tiene escenario: haría falta un origen que tarde, y eso es la ficha F3-R03. El valor de `STALE_LIMIT` sigue siendo el provisional de 60 s; el experimento corre con `P20_STALE_LIMIT=4` para no esperar.
- Dónde está en el código: `fase1/borde.py` (`_hablar_con_origen`, `_sin_origen`, `particion`; `rechaza causa=invalidada` usa la marca `Copia.invalidada` de la entrada de Rubén «El aviso recibido marca la copia»), `fase1/config.py` (`timeout_segundos`, `stale_limit_segundos`). Escenarios `obsoleto`, `invalidada` y `origen_caido` en `fase1/escenarios.py`. Ficha en `docs/experimento-fase1.md`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-19 — Revalidación del lado borde: manda `version_local` solo si la copia expiró

- Decisión: cuando la copia solo expiró (no está invalidada), el borde llama a `responder(pedido_id, recurso, version_local=copia.version)` (F1-R08). Si el origen contesta `misma=True`, no viajan bytes: la copia se renueva (`_renovar`), se anota `revalida … renovo=si` y el cliente ve `hit`. Si trae otra versión, `revalida … renovo=no bajo_otra=si`, `guarda`, `miss`. Cuando la copia está invalidada, o no hay copia, el borde no manda versión y pide el archivo entero: una copia invalidada nunca se renueva como `hit`, lo que mande el origen la reemplaza (si es el mismo número de versión, `revalida renovo=no` sin `bajo_otra`). La comparación es por igualdad.
- Alternativas consideradas: mandar `version_local` también con la copia invalidada y quitar la marca si el origen confirma la misma versión (lo hacía el borde de Samy por la tarde; se descartó al adoptar la regla de Rubén: lo que el origen mandó quitar no se confirma, se reemplaza); un método aparte `revalidar` en el origen.
- Por qué esta: es la propuesta de Samy para R08 y la firma que Rubén implementó el mismo día; es lo que hace HTTP con `If-None-Match` / `304`. No mandar la versión de una copia invalidada hace imposible que un `misma=True` reviva una copia que el origen quiso retirar, y deja una sola regla: invalidada → se baja de nuevo.
- Qué no resuelve: un origen que reinicie y vuelva a la versión 1 confirmará `misma=True` a una copia con versión 1 aunque el contenido fuera otro; es la limitación de la etiqueta en memoria (revisión de la decisión «Hash del contenido», para la fase 2).
- Dónde está en el código: `fase1/borde.py` (`pedir`, paso 3; `_hablar_con_origen`; `_con_respuesta_del_origen`, ramas b y c). Escenario `ttl` en `fase1/escenarios.py`; `revalidar` prueba el lado origen.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-20 — HTTP en los dos canales; publicar solo en el origen

- Decisión: en la fase 2 los dos canales son HTTP, con la biblioteca del lenguaje. El lector abre `GET /<recurso>` en el borde. El borde, si no tiene copia usable, hace `GET /<recurso>` al origen; para revalidar ese `GET` lleva la versión local y, si coincide, la respuesta no trae cuerpo. Quien publica habla solo con el origen: `PUT /<recurso>` crea o reemplaza, `DELETE /<recurso>` borra. El borde rechaza `PUT` y `DELETE`. Tras el cambio, el origen sube la versión e invalida a los bordes. La función de caché no ve el HTTP. No hay proxy ni caché externa.
- Alternativas consideradas: dejar el canal borde↔origen en el texto de `enviar` / `recibir`; aceptar `PUT` y `DELETE` también en el borde.
- Por qué esta: es la forma de una CDN. El lector y quien publica se prueban en el navegador. La vía de escritura no pasa por la caché, así que un cliente no sustituye la versión de referencia. La metodología permite una biblioteca normal de HTTP, y el aporte sigue en la caché.
- Qué no resuelve: no hay cuentas ni contraseñas; puede publicar quien alcance la dirección del origen. El `pedido_id` del lector, si no viene, lo crea el borde. El cifrado previsto sigue siendo el canal borde↔origen. Los navegadores permanecen en claro. El código de la fase 1 no cambia.
- Dónde está en el código: todavía no. Queda en el schedule: F2-S02, F2-S04, F2-S06, F2-S07, F2-R03 y F2-J10.
- Implementa: Samy (HTTP del origen, `PUT` y `DELETE`) y Rubén (el `GET` del borde hacia el lector y hacia el origen)
- Revisa: los dos, cuando el código exista

## Fase 2 — tabla nativa (F2-S03, borrador de Samy; Rubén completa sus filas)

Por cada mecanismo: qué hacía Ray en la fase 1, qué opciones nativas había, cuál se eligió y qué se pierde. Las filas del borde (TTL, LRU, invalidación en el borde, `STALE_LIMIT`) las completa Rubén en F2-R08.

| Mecanismo | Qué hacía Ray (fase 1) | Opciones nativas | Elegida | Qué se pierde | Dónde |
| --- | --- | --- | --- | --- | --- |
| Ejecución de cada nodo | `@ray.remote` + `Clase.remote()`: un worker por actor, arrancado y supervisado por Ray | un binario por rol arrancado a mano; `docker run` por nodo (F2-R15); un supervisor | un programa por rol (`cmd/origen`, `cmd/cliente`, `cmd/publicar`; `cmd/borde` de Rubén), arrancado a mano o con `docker run` | nadie reinicia un nodo que muere; nadie sabe que murió hasta que se le llama | `fase2/cmd/*` |
| Transporte | `metodo.remote(...)` + `ray.get`: serialización y entrega entre procesos | TCP propio con *framing* de texto (`enviar`/`recibir` del README); HTTP de `net/http`; gRPC | **HTTP/1.1 de la biblioteca estándar**: recurso en la ruta, versión y `pedido_id` en cabeceras, archivo en el cuerpo; un solo paquete (`transporte`) abre conexiones | hay que fijar a mano estados, cabeceras y qué significa cada código; HTTP mete cabeceras que no son nuestras | `fase2/transporte`, `fase2/protocolo` |
| Serialización | dict + bytes viajaban solos | JSON; texto plano; cuerpo binario + cabeceras | cuerpo binario = archivo; metadatos en cabeceras de texto | nada: es más simple que Ray | `fase2/protocolo` |
| Quién sabe dónde está quién | el *handle* del actor | descubrimiento (multicast, registro central); lista estática; DNS | **lista estática en `fase2/config.json`** (origen + bordes con nombre y dirección), leída por todos | añadir un borde es editar el archivo y reiniciar; un borde fuera de la lista no existe para nadie | `fase2/config` |
| Esperar con límite | `ray.wait(timeout)` | `context.WithTimeout`; `http.Client.Timeout`; `SetDeadline` en el socket | `context.WithTimeout` por llamada, con `timeout_segundos` de la configuración, en el `transporte` | nada; el plazo es explícito | `fase2/transporte` |
| Detectar nodo caído | `RayActorError` sin esperar al plazo | error de `connect` (conexión rechazada) vs plazo vencido; *health checks* | el `transporte` clasifica: `context.DeadlineExceeded` → `timeout`; cualquier otro error de red → `nodo_caido`. Sin *health checks*: se decide en cada llamada | un proceso colgado se ve como `timeout`, no como caído; no hay noticia hasta que alguien llama | `fase2/transporte` |
| Un mensaje a la vez por actor | el actor serializaba las llamadas; sin cerrojos | un hilo por nodo; cerrojo sobre el estado; canal | el servidor HTTP de Go atiende cada pedido en su gorrutina; el estado del origen (`versiones`) va bajo `sync.Mutex`; el borde decide lo suyo (Rubén) | hay que acordarse del cerrojo en cada estado compartido | `fase2/origen` |
| Versión de referencia | `_versiones` en memoria del actor: reinicio → versión 1 | archivo JSON; SQLite; nombre de archivo con versión | **`contenido/.versiones.json`** (versión + hash por recurso), escrito en cada cambio; hash SHA-256 sigue siendo la única señal | un `PUT` concurrente con el mismo recurso serializa en el cerrojo; el archivo se reescribe entero | `fase2/origen` (`versionDe`, `persistir`) |
| Publicar | editar `contenido/` a mano y llamar `invalidar` | lo mismo; `PUT`/`DELETE` HTTP en el origen; un panel | **`PUT /<recurso>` y `DELETE /<recurso>` solo en el origen**; el borde responde `405` | no hay cuentas: publica quien alcance el origen | `fase2/origen`, `fase2/cmd/publicar` |
| Invalidación origen → bordes | `borde.invalidar.remote` con `ray.get` sin timeout; `anotar_bordes` | `POST` a cada borde con timeout; cola/*pub-sub*; que el borde pregunte | **`POST /_invalidar/<recurso>`** a cada borde de la lista, con el plazo del transporte; `200` = aplicó, `202` = no aplicó, otra cosa = no contestó | un borde colgado cuesta un plazo entero por aviso; sin reintento: converge por TTL | `fase2/origen` (`Invalidar`) |
| Revalidación | `responder(…, version_local)` → `misma` | `If-None-Match`/`304`; endpoint aparte | **`X-Version-Local` → `304` sin cuerpo, `X-Misma: si`** | nada | `fase2/origen` |
| Selección de fuente | igual que ahora (no era de Ray) | lo mismo; DNS por red (F2-S19) | el mismo selector (orden fijo, el que no respondió va al final) en el proceso del cliente | nada | `fase2/cliente/selector.go` |
| Historial | `registrar` en Python; Ray reenviaba el stdout de los workers | lo mismo en Go | `fase2/registro.Registrar`, mismo formato, un archivo por nodo y consola | cada programa tiene su propia consola: para verlo todo junto se mira `logs/` | `fase2/registro` |
| Caché del borde: TTL, LRU, estados, `STALE_LIMIT` | no era de Ray | lo mismo en Go | (Rubén, F2-R03–R06) | | `fase2/borde` |
| Reintentos | Ray no reintentaba; nadie quería que lo hiciera | reintento en el transporte; reintento por nodo | ninguno en el transporte; el cliente cambia de borde con el mismo `pedido_id`; el resto no reintenta | ver `docs/diseno-nativo.md` §3 | |

### 2026-11-20 — HTTP concreto: cabeceras, códigos y el paquete `transporte` como único socket

- Decisión: el protocolo de `docs/diseno-nativo.md` §1. Recurso en la ruta, `X-Pedido-Id`, `X-Version`, `X-Version-Local`, `X-Misma`, `X-Resultado`, `X-Bordes-Avisados`, archivo en el cuerpo. `304` para «misma versión», `404` + `X-Resultado: file_doesnt_exist`, `503` + `rechaza` en el borde, `405` a `PUT`/`DELETE` en el borde, `202` del borde = aviso recibido y no aplicado. Los dos programas de Samy y el borde de Rubén hablan por `fase2/transporte.Enviar(destino, método, ruta, cabeceras, cuerpo)`, que pone el plazo con `context.WithTimeout` y clasifica el fallo en `timeout` o `nodo_caido`. Es la pieza que F2-R02 llamaba `enviar`/`recibir`, sobre HTTP en vez de TCP a mano.
- Alternativas consideradas: TCP propio con mensajes de texto delimitados (lo que el README describe); JSON en el cuerpo con los metadatos; un endpoint aparte `/revalidar`; códigos propios en vez de los de HTTP.
- Por qué esta: la metodología del curso permite «librerías normales para HTTP/gRPC, serialización…» y lo que exige es que el mecanismo (timeouts, reintentos, identidad de pedido, semántica de fallo) sea nuestro y explícito; Rubén eligió HTTP el 20 nov para que el lector y quien publica se prueben con un navegador. Usar los códigos de HTTP con su significado (`304`, `404`, `405`, `503`) evita inventar un segundo vocabulario, y poner los tokens del contrato en `X-Resultado` mantiene las mismas palabras en el log y en la respuesta. Un solo paquete que abre conexiones es lo que permite que TLS, si entra, no toque la lógica.
- Qué no resuelve: HTTP no es el `enviar`/`recibir` del README ni de F2-R02; el README y esa tarea hay que alinearlos (pendiente de Rubén). No hay autenticación: lo dice `diseno-nativo.md` §4. Un `timeout` real de un borde lento sigue sin escenario (ficha F3-R03).
- Dónde está en el código: `fase2/protocolo/protocolo.go`, `fase2/transporte/transporte.go`; lo usan `fase2/origen` (avisos), `fase2/cliente` (GET) y `fase2/cmd/publicar` (PUT/DELETE).
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-20 — Configuración estática en `fase2/config.json`, los mismos números que la fase 1

- Decisión: un archivo JSON con la dirección del origen, la lista de bordes (nombre + `host:puerto`, en orden de preferencia), TTL, `STALE_LIMIT`, capacidad, política, timeout, `evitar_borde_segundos`, `cifrado=false`, y las carpetas `contenido` y `logs`. Todos los programas lo leen con `-config`; `P20_*` sobreescribe los números como en la fase 1. No hay descubrimiento ni registro central: es el arranque estático que el tablero da por válido si se justifica.
- Alternativas consideradas: banderas de línea de comandos por programa; variables de entorno para todo; un nodo de registro al que cada borde se anuncia; DNS.
- Por qué esta: un archivo que los cuatro programas comparten es la forma más corta de que «la lista de miembros sea la misma en todos» sin un protocolo de membresía, que no es el aporte de este proyecto. Es lo que una CDN pequeña hace: el operador sabe sus nodos. Las direcciones por defecto (`127.0.0.1:8000/8001/8002`) sirven para la corrida local; con Docker (F2-R15) cambian a los nombres de los contenedores.
- Qué no resuelve: añadir o quitar un borde exige editar el archivo y reiniciar a quien lo use; un borde que no está en la lista no recibe avisos. No hay valores por nodo (todos los bordes comparten TTL y capacidad).
- Dónde está en el código: `fase2/config/config.go`, `fase2/config.json`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-20 — El origen persiste versión y hash; borrar no reinicia la versión

- Decisión: `contenido/.versiones.json` guarda, por recurso, la versión y el hash SHA-256 del último contenido visto. Se escribe cada vez que una versión cambia. Al arrancar, el origen lo lee: un reinicio no vuelve a la versión 1. `DELETE` borra el archivo pero conserva la entrada: si el recurso vuelve con otro contenido, la versión sigue subiendo (1 → 2 → borrado → 3). El hash sigue siendo la única señal de cambio, y se calcula también en cada `GET`, así que editar el archivo a mano sigue subiendo la versión como en la fase 1.
- Alternativas consideradas: dejar las versiones en memoria (fase 1); versión en el nombre del archivo; SQLite; reiniciar la versión al borrar.
- Por qué esta: la revisión de la decisión «Hash del contenido» (19 nov) dejó dicho que un origen que reinicia y vuelve a 1 confirmaría `misma=si` a una copia de otro contenido. Con la versión persistida eso no pasa. Conservar la entrada tras borrar evita que un recurso borrado y vuelto a publicar reciba un número que un borde ya tuvo. Un JSON pequeño basta: el origen es uno y las escrituras van bajo cerrojo.
- Qué no resuelve: el archivo se reescribe entero en cada cambio; con muchos recursos habría que cambiarlo. Si alguien borra `.versiones.json` a mano, la numeración vuelve a 1. Hashear en cada `GET` cuesta con archivos grandes; el origen HTTP podría fiarse del hash guardado y rehashear solo en `PUT`, pero entonces editar a mano no subiría la versión: se prefirió conservar ese comportamiento de la fase 1.
- Dónde está en el código: `fase2/origen/origen.go` (`versionDe`, `persistir`, `Nuevo`). Prueba `TestVersionSobreviveAlReinicio`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-20 — El aviso de invalidación lleva plazo y no se reintenta

- Decisión: tras un `PUT` o un `DELETE`, el origen manda `POST /_invalidar/<recurso>` a cada borde de la configuración, uno tras otro, cada uno con el plazo del transporte. El borde que contesta `200` entra en `bordes=`; el que contesta `202` (recibió y no aplicó) o cualquier otro código no entra; el que no contesta deja `timeout` o `nodo_caido destino=<borde>` en el historial del origen y tampoco entra. No hay reintento: el borde que se quedó fuera se pone al día cuando su TTL venza y revalide. La respuesta del `PUT` al publicador lleva `X-Bordes-Avisados` para que quien publica vea a quién llegó.
- Alternativas consideradas: avisos en paralelo (una gorrutina por borde); reintentar N veces; una cola persistente de avisos pendientes; que el borde pregunte periódicamente al origen.
- Por qué esta: en la fase 1 el aviso no tenía plazo y un borde colgado bloqueaba al origen (revisión de R06); el plazo lo arregla. Secuencial y sin reintento porque con dos bordes el coste es un plazo por borde caído y el sistema ya converge por TTL (`diseno-nativo.md` §4); una cola de reintentos sería estado durable nuevo que habría que diseñar y defender, y no es el aporte de este proyecto. El publicador ve la lista y puede repetir el `PUT` (idempotente) si quiere insistir.
- Qué no resuelve: con muchos bordes caídos el `PUT` tarda `timeout × caídos`; un aviso perdido de verdad solo se nota por la ausencia en `bordes=`. Un borde que arranca después del aviso no lo recibe, y no le hace falta: arranca vacío.
- Dónde está en el código: `fase2/origen/origen.go` (`Invalidar`). Pruebas `TestPublicarInvalidaALosBordes`, `TestAvisoPerdidoYBordeQueNoEsta`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-20 — `registrar` en Go: misma línea, un archivo por nodo, pares en orden

- Decisión: `fase2/registro.Registrar(nodo, pedidoID, operacion, datos...)` escribe «`HH:MM:SS.mmm nodo pedido=… operacion clave=valor …`» en consola y en `<logs>/<nodo>.log`, con un cerrojo para que las gorrutinas del servidor HTTP no mezclen líneas. Los pares van como una lista ordenada (`registro.D("recurso", r)`) porque en Go un mapa no conserva el orden y el historial se lee mejor con las claves siempre en el mismo sitio.
- Alternativas consideradas: el paquete `log` de Go (mete su propio prefijo); JSON por línea; un mapa para los datos.
- Por qué esta: el README fija el formato y la fase 1 ya lo escribe así; `grep "pedido=…" logs/*.log` tiene que funcionar igual con logs de Python y de Go mezclados. La fase 3 compara los dos sistemas leyendo los mismos historiales.
- Qué no resuelve: cada programa escribe su consola; para ver todo junto se mira `logs/`. El navegador del lector no escribe nada: su pedido lo anota el borde.
- Dónde está en el código: `fase2/registro/registro.go`. Lo usan todos los programas de `fase2/`.
- Implementa: Samy
- Revisa: Rubén (pendiente)
