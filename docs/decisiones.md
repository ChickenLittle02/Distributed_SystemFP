# Decisiones

Cada entrada la escribe quien implementa. La otra persona la revisa y, si no puede explicarla con sus palabras, la pieza sigue abierta.

### 2026-11-16 — STALE_LIMIT provisional de 1 minuto

- Decisión: `STALE_LIMIT = 60` segundos (1 minuto) mientras se desarrolla y se prueba el prototipo.
- Alternativas consideradas: 10 minutos, que es el ejemplo del README; dejar el número sin fijar hasta el experimento de partición.
- Por qué esta: con 10 minutos hay que esperar demasiado para ver, en una corrida local, una copia servida dentro del límite y otra rechazada por encima. Un minuto basta para distinguir las dos ramas.
- Qué no resuelve: no es el valor de la entrega ni de la defensa. Es provisional para poder ejecutar el programa sin esa espera. El número definitivo se vuelve a decidir al cerrar la regla de obsoleto y el experimento de partición.
- Dónde está en el código: todavía no hay código. Cuando existan el origen y el borde, el valor sale de la configuración y la regla lo lee de ahí.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — Fase 1 en Python con Ray

- Decisión: el prototipo de la fase 1 se escribe en Python y usa Ray para correr el origen, los bordes y el cliente en procesos separados.
- Alternativas consideradas: escribir ya el transporte TCP en el lenguaje de la fase 2; usar otro runtime de actores.
- Por qué esta: la fase 1 tiene que ejecutarse de verdad en varios procesos y dejar escrito qué aporta Ray (el arranque de esos procesos y la llamada de uno a otro). La caché, las versiones, la invalidación y la regla de obsoleto se escriben en este repositorio. El diseño sin Ray es la fase 2.
- Qué no resuelve: Ray no decide el hit, el miss, la expulsión, la invalidación ni `STALE_LIMIT`. Esas reglas no se delegan en una biblioteca de caché. `enviar` y `recibir` sobre TCP quedan para la fase 2.
- Dónde está en el código: todavía no hay código. El primer uso es el arranque del actor origen.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — El cliente pide por nombre y no elige el borde

- Decisión: el cliente es un proceso distinto del origen y de los bordes. Pide un recurso por su nombre y un `pedido_id` que él crea. No envía un borde preferido. La selección escoge la fuente y el historial la anota como `fuente`.
- Alternativas consideradas: que el cliente nombre el borde en el pedido, como si `fuente=borde-1` fuera un dato de entrada.
- Por qué esta: en una caché normal quien pide el archivo nombra la URL; otro componente elige el nodo de borde. El ejemplo del README anota la fuente en la línea `solicitud`, que es el borde ya elegido.
- Qué no resuelve: no fija el orden ni el criterio fino de la selección. Si el primer borde no puede servir y el origen no contesta, la regla de `rechaza` ya dice que se prueba el otro borde. La política concreta la implementa Samy.
- Dónde está en el código: `docs/contrato.md`. Todavía no hay programa cliente.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — La respuesta incluye el contenido del archivo

- Decisión: además de `version` y `resultado`, la respuesta al cliente lleva `contenido`, los bytes del archivo. `hit`, `miss` y `sirve_obsoleta` traen esos bytes. `rechaza` no trae contenido. El historial sigue sin guardar el archivo.
- Alternativas consideradas: devolver solo la versión y el resultado, y dejar el archivo fuera de esta fase.
- Por qué esta: el sistema reparte un archivo. La versión y el resultado dicen qué pasó; el contenido es lo que el cliente vino a buscar. El borde tiene que guardar el archivo, no solo el nombre y la versión.
- Qué no resuelve: no enumera los fallos. Esos casos están en las entradas siguientes y en `docs/contrato.md`. `file_doesnt_exist` tampoco trae contenido.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — `rechaza` solo cuando ninguna fuente entrega el archivo

- Decisión: si el primer borde no puede servir el recurso y el origen no contesta, la selección prueba el otro borde. Una copia fresca en ese otro borde es `hit`. El origen contestando con el archivo es `miss`. Una copia no invalidada dentro de `STALE_LIMIT`, con el origen en silencio, es `sirve_obsoleta`. `rechaza` queda para cuando los dos bordes y el origen no pueden entregar el archivo.
- Alternativas consideradas: rechazar en cuanto el primer borde no tiene una copia usable, sin preguntar al otro.
- Por qué esta: en una caché normal un nodo caído o vacío no es el final del pedido. Otro borde puede tener el archivo. El cliente ve el fallo cuando ya no queda fuente.
- Qué no resuelve: no fija el orden entre los bordes ni la política cuando hay más de dos. La fase 1 corre con dos bordes. La política concreta de selección la implementa Samy.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — Una copia invalidada no se sirve si el origen no contesta

- Decisión: si el origen invalidó una copia y el borde no logra hablar con el origen para bajar la versión nueva, esa copia no se responde. `STALE_LIMIT` no la habilita. El cliente la recibe solo si otra fuente entrega un archivo que sí se puede usar. Si el origen contesta, el borde baja la versión nueva y el resultado es `miss`.
- Alternativas consideradas: tratar la copia invalidada como una copia vencida y servirla dentro de `STALE_LIMIT`.
- Por qué esta: en una caché normal la invalidación es una orden de no servir esa versión. El límite de obsolescencia cubre una copia vencida o una revalidación que no pudo hacerse, no una versión que el origen mandó quitar.
- Qué no resuelve: no describe cómo se simula el aviso perdido. Ese caso sigue en el borde que no recibió la invalidación: su copia no está invalidada y sigue la regla de frescura.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — El origen dice que el archivo no existe

- Decisión: si el origen contesta y el recurso no está, el resultado del cliente es `file_doesnt_exist` («file doesn't exist»). No hay versión ni contenido. El borde borra esa copia en ese momento; la regla está en la entrada de borrado.
- Alternativas consideradas: usar `rechaza` para este caso y mantener solo los cuatro resultados del README.
- Por qué esta: `rechaza` en este proyecto es «había algo que decidir y ninguna fuente pudo entregarlo». Aquí el origen sí contestó y dijo que el archivo no existe. El token va sin espacios para poder escribirlo en la línea de historial: `resultado=file_doesnt_exist`.
- Qué no resuelve: no se usa este resultado cuando el origen está en silencio. En ese caso siguen `sirve_obsoleta` y `rechaza`.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — TTL provisional de 30 segundos

- Decisión: una copia está fresca durante `TTL = 30` segundos desde que se guarda o desde que el origen confirma la misma versión. Después queda obsoleta. `STALE_LIMIT` sigue midiendo solo el tiempo que lleva obsoleta.
- Alternativas consideradas: un TTL de varios minutos, como en una caché pública; no fijar el número hasta el experimento.
- Por qué esta: 30 segundos dejan ver una copia fresca, el paso a obsoleta y las dos ramas de `STALE_LIMIT` (60 segundos) sin alargar la corrida. Es provisional, igual que el límite.
- Qué no resuelve: no es el valor de la entrega. Se vuelve a mirar al cerrar el experimento de partición.
- Dónde está en el código: `docs/contrato.md`. Cuando exista el borde, el valor sale de la configuración.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — Misma versión en la revalidación es `hit`

- Decisión: si el borde pregunta al origen y el origen confirma la misma versión, el resultado del cliente es `hit`. La copia permanece y el TTL vuelve a empezar. `miss` queda para cuando el origen entrega otro contenido.
- Alternativas consideradas: anotar `miss` cada vez que el borde tuvo que preguntar al origen, aunque el archivo no cambiara.
- Por qué esta: en una caché normal esa respuesta confirma la copia que ya estaba. El cliente recibe el archivo del borde. El historial del borde puede llevar además la línea `revalida`.
- Qué no resuelve: no cambia `sirve_obsoleta` ni `rechaza`, que siguen siendo los casos en los que el origen no contesta.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — Cuándo el borde borra una copia

- Decisión: el borde borra la copia al momento en tres casos. El origen, al pedirla el borde, responde que ya no está. Llega la invalidación de esa copia. La edad obsoleta pasó `STALE_LIMIT` y el origen responde que esa copia es obsoleta; si además entrega una versión nueva, el borde guarda esa y el cliente ve `miss`. Si el origen sigue en silencio, la copia no se borra. Solo puede salir por expulsión LRU cuando el borde se llena.
- Alternativas consideradas: borrarla 1 o 2 minutos después de saber que el origen ya no la tiene; borrarla en cuanto pasa el TTL; borrarla también cuando pasó `STALE_LIMIT` y el origen sigue en silencio.
- Por qué esta: la copia se quita cuando el borde ya sabe que no debe guardarla. El silencio del origen no es esa noticia: durante `STALE_LIMIT` esa copia es la que se sirve, y pasada esa edad el proyecto aún la conserva hasta que LRU necesite el sitio o el origen hable.
- Qué no resuelve: no elige qué copia saca LRU ni la capacidad del borde. Eso lo implementa Samy.
- Dónde está en el código: `docs/contrato.md`.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — Archivos del origen en carpeta local

- Decisión: el origen lee los archivos de la carpeta local `contenido/`. Cada archivo que aparece ahí empieza en versión `1`. Cuando el contenido de ese archivo cambia, la versión sube en `1`. Si el archivo se borra de la carpeta, el origen responde `file_doesnt_exist`.
- Alternativas consideradas: generar el contenido en memoria; numerar versiones a mano en un archivo aparte; subir la versión en saltos mayores.
- Por qué esta: se puede editar o borrar un archivo del disco y provocar miss, revalidación, invalidación y `file_doesnt_exist` sin inventar un almacén. Empezar en 1 y subir de 1 en 1 deja las versiones visibles en el historial.
- Qué no resuelve: cómo se detecta el cambio quedó en la entrada del hash.
- Dónde está en el código: `contenido/` y `fase1/origen.py` (`responder`, `_version_y_bytes`).
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — Hash del contenido para subir la versión

- Decisión: la única señal para subir la versión de un archivo en el origen es el hash de su contenido (SHA-256 de los bytes). El origen guarda la última huella vista junto con la versión. Si al leer el archivo la huella es distinta, el contenido cambió y la versión sube en `1`. La fecha de modificación del disco no se usa.
- Alternativas consideradas: usar solo la fecha de modificación (`mtime`); usar fecha y, si cambió, confirmar con hash.
- Por qué esta: la versión tiene que reflejar el contenido que se reparte. El hash solo sube cuando los bytes cambian de verdad. La fecha sola puede subir la versión con un `touch` sin cambio, o fallar al copiar un archivo con fecha antigua. Con pocos archivos chicos en `contenido/`, hashear en cada lectura es aceptable.
- Qué no resuelve: no cifra ni firma el archivo; solo detecta cambio.
- Dónde está en el código: `fase1/origen.py`, estado `_versiones` (versión + hash) y `_version_y_bytes`.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-16 — Origen como actor Ray

- Decisión: el origen de la fase 1 es un actor Ray (`@ray.remote`) en `fase1/origen.py`. Se arranca en local con `fase1/arrancar_origen.py`. Confirma que vive con `listo` y reparte archivos con `responder`.
- Alternativas consideradas: un proceso Python sin Ray; un script que solo importa Ray sin crear actor.
- Por qué esta: la fase 1 tiene que correr varios procesos de verdad. El actor es el proceso origen que el borde llamará.
- Qué no resuelve: todavía no invalida bordes (F1-R06) ni tiene la API fina de revalidación (F1-R08). La línea `listo` sigue siendo solo prueba de arranque.
- Dónde está en el código: `fase1/origen.py`, `fase1/arrancar_origen.py`.
- Implementa: Rubén
- Revisa: Samy (pendiente)

### 2026-11-17 — Borde y cliente como actores Ray; el selector, junto al cliente

- Decisión: el borde y el cliente son actores Ray (`@ray.remote`), uno por proceso, igual que el origen. El cliente recibe los handles de los bordes al crearse. La selección de fuente no es un nodo: será un módulo que vive junto al cliente (F1-S07), como dice `docs/contrato.md` («la selección, que vive junto al cliente, escoge la fuente»).
- Alternativas consideradas: cliente como script del lado del usuario sin actor; selector como un actor aparte al que el cliente le pregunta.
- Por qué esta: la fase 1 tiene que correr en varios procesos de verdad, y el cliente es «un proceso distinto del origen y de los bordes» (contrato). Un selector como nodo aparte sería un componente inventado solo para la fase 1 y un punto más de fallo que el README no pide.
- Qué no resuelve: hoy el cliente pide siempre al primer borde de la lista y espera sin límite. El paso a otro borde y el tiempo de espera son F1-S07 y F1-S09.
- Dónde está en el código: `fase1/borde.py`, `fase1/cliente.py`, `fase1/arrancar_sistema.py`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-17 — La configuración en un solo archivo, con sobreescritura por entorno

- Decisión: TTL, `STALE_LIMIT`, capacidad, política de expulsión, tiempo de espera, `cifrado` y el orden de los bordes viven en `fase1/config.py` (`Config`). Los cuatro números se pueden cambiar con variables de entorno `P20_*` para una corrida corta de prueba, sin tocar el código.
- Alternativas consideradas: constantes repartidas en cada archivo; argumentos de línea de comandos en cada script de arranque.
- Por qué esta: la guía (parte 6) pide que «esos valores vivan juntos, para poder cambiarlos sin buscarlos por todo el código», y las notas del profesor del Lab 0 piden que la configuración esté a la vista y se pase como parámetro, no escondida en el código. El entorno es la forma más corta de hacerlo sin cambiar la firma de los actores.
- Qué no resuelve: los valores siguen siendo provisionales (decisiones del 16 nov). La lista de bordes es estática: es el arranque estático que el tablero da por válido si queda justificado, y queda justificado aquí: en la fase 1 el descubrimiento lo hace Ray con los handles, y en la fase 2 la lista pasará a direcciones en la configuración.
- Dónde está en el código: `fase1/config.py`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-18 — La copia del borde vive en memoria, con versión, bytes y hora de guardado

- Decisión: el borde guarda cada copia como `Copia(version, contenido, guardada_en)` en un diccionario en la memoria del actor (`_copias`). Un pedido con copia es `hit` y no toca el origen. Un pedido sin copia anota `miss causa=no_esta`, luego `pide_origen`, baja el archivo, anota `guarda` y responde `miss`. Si el origen contesta `file_doesnt_exist`, el borde borra la copia de ese nombre, como dice el contrato. La línea `miss` lleva `causa` para que, cuando lleguen TTL e invalidación, el historial diga por qué no sirvió la copia (`no_esta`, `expirada`, `invalidada`).
- Alternativas consideradas: guardar las copias en disco (`logs/` o una carpeta `cache/` por borde) para que sobrevivan al reinicio del actor; guardar solo nombre y versión y volver a bajar el contenido en cada hit.
- Por qué esta: la fase 1 solo tiene que mostrar los comportamientos de caché, y la guía (parte 6, paso 3) describe el borde como «guarda lo que baja y lo entrega si lo tiene». Guardar los bytes es lo que hace que el hit no hable con el origen; sin ellos no habría hit de verdad. Una caché solo en memoria es la descripción honesta que pide el tablero para la ficha de reinicio (F3-S03): si el borde muere, arranca vacío y el primer pedido es `miss`.
- Qué no resuelve: la copia no tiene expiración ni estado fresca/obsoleta (F1-S05), no hay tope de capacidad ni expulsión (F1-S06), el borde no revalida (F1-S08) ni aplica `STALE_LIMIT` (F1-S09) y no sobrevive al reinicio del actor. `guardada_en` queda puesto para que el TTL cuente desde ahí.
- Dónde está en el código: `fase1/borde.py` (`Copia`, `_copias`, `pedir`, `_guardar`, `estado`). La corrida de `fase1/arrancar_sistema.py` muestra miss, hit y `file_doesnt_exist` seguidos.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-19 — TTL en el borde: `expira_en`, y qué pasa con una copia obsoleta

- Decisión: cada `Copia` lleva `expira_en = guardada_en + TTL`. Antes de esa hora está fresca y se sirve como `hit` sin hablar con el origen. Después está obsoleta: el borde anota `miss causa=expirada` (con la versión local, la hora en que expiró y los segundos que lleva obsoleta) y `pide_origen … version=N`, y pregunta al origen. Si el origen confirma la misma versión, la copia se queda, el TTL vuelve a contar desde ahora (`_renovar`), se anota `revalida … renovo=si` y el cliente ve `hit`. Si el origen trae otra versión, se anota `revalida … renovo=no bajo_otra=si`, se guarda la nueva y el cliente ve `miss`. La copia obsoleta nunca se borra por sí sola: solo la reemplaza el origen, la quita `file_doesnt_exist`, la invalidación o la expulsión LRU (decisión del 16 nov, «Cuándo el borde borra una copia»).
- Alternativas consideradas: borrar la copia al expirar y tratarla como `no_esta` (más simple, pero deja sin copia para `sirve_obsoleta` y contradice el contrato); responder `miss` siempre que hubo que preguntar al origen aunque la versión fuera la misma (contradice la entrada «Misma versión en la revalidación es `hit`»); un hilo que expire copias por su cuenta (una decisión más que tomar en la fase 2 sin ganancia en la fase 1).
- Por qué esta: el README (§5) pide los estados fresca → obsoleta → actualizada y que el historial lleve la edad y la expiración como datos; el contrato dice que la misma versión confirmada es `hit` y que `STALE_LIMIT` mide el tiempo obsoleta, así que la copia tiene que seguir guardada con su `expira_en` para que F1-S09 pueda calcular esa edad. La expiración se evalúa al pedir, no con un reloj aparte: es la forma más corta y deja la decisión a la vista en `pedir`.
- Qué no resuelve: hoy el borde revalida bajando el archivo entero y comparando la versión, porque `responder` no acepta una versión local. El mensaje de revalidación propio (misma versión sin bytes) es F1-S08 del lado borde y F1-R08 del lado origen. Tampoco hay tiempo de espera: si el origen no contesta, el pedido se queda esperando (F1-S09). El valor del TTL sigue siendo el provisional de 30 s (decisión del 16 nov).
- Dónde está en el código: `fase1/borde.py` (`Copia.expira_en`, `Copia.fresca`, `pedir`, `_con_respuesta_del_origen`, `_renovar`, `estado`). Escenario `ttl` en `fase1/escenarios.py`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-19 — Expulsión LRU con un `OrderedDict`, capacidad 2, visible en el log

- Decisión: `_copias` es un `OrderedDict` en orden de uso: la primera copia es la menos usada recientemente. Un `hit` y un guardado o renovación mueven la copia al final. Cuando llega un recurso nuevo y ya hay `capacidad` copias, sale la primera y se anota `expulsion recurso=<sale> version=… politica=LRU entra=<entra>` antes de `guarda`. Reemplazar una copia que ya estaba (otra versión del mismo recurso) no cuenta como entrada nueva y no expulsa. `capacidad = 2` en la configuración, a propósito pequeña para ver la expulsión en una corrida de tres archivos.
- Alternativas consideradas: FIFO (más simple, pero el README lo deja como segunda política y el tablero la pospone a F2-R04 «solo si el núcleo ya está verde»); una lista aparte con las horas de último uso (lo mismo con más código); contar la capacidad en bytes en vez de en copias.
- Por qué esta: el tablero pide «expulsión LRU con capacidad pequeña, visible en el log» y el README (§4) deja la política como decisión del proyecto; LRU es la que una caché de contenido usa normalmente, y el `OrderedDict` de la biblioteca estándar la expresa sin estructura propia. Contar copias y no bytes es suficiente con archivos chicos y hace predecible el escenario.
- Qué no resuelve: no hay segunda política para comparar (si entra, en la fase 2). Una copia obsoleta o, cuando exista, invalidada también puede ser expulsada: LRU no mira el estado, solo el uso. El origen no se entera de la expulsión; el siguiente pedido es `miss causa=no_esta`.
- Dónde está en el código: `fase1/borde.py` (`_copias`, `move_to_end` en `pedir` y `_renovar`, `_guardar`). `capacidad` y `expulsion` en `fase1/config.py`. Escenario `lru` en `fase1/escenarios.py`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-19 — Política de selección: orden fijo de bordes, el que no responde va al final un rato

- Decisión: el selector (`fase1/selector.py`) vive en el proceso del cliente y da, para cada pedido, la lista de bordes en el orden de `Config.bordes` (el primero es el «más cercano»). El cliente anota `solicitud … fuente=<borde>` por cada borde que prueba y lo llama con tiempo de espera `timeout_segundos` (2 s). «No responde» es una de dos cosas, cada una con su línea: `timeout` (la llamada no volvió a tiempo) o `nodo_caido` (el actor del borde murió y Ray devuelve `RayActorError`). Un borde que no respondió se deja al final de la lista durante `evitar_borde_segundos` (10 s) y luego recupera su lugar; nunca se descarta. Si un borde contesta `rechaza`, el cliente prueba el siguiente (contrato, «Cuándo el cliente ve `rechaza`»). La primera respuesta que entrega algo, o `file_doesnt_exist`, es la final. Si ningún borde entrega, el cliente anota `respuesta resultado=rechaza fuente=ninguna`. El cliente nunca le pide al origen: el origen no es una fuente del selector; es el borde quien baja de ahí.
- Alternativas consideradas: que el cliente hable con el origen como última fuente (el README §8 lo permite: «si se utiliza otro borde o el origen»); elegir el borde por el que tenga el recurso o la copia más fresca (haría falta preguntar el estado a todos los bordes antes de cada pedido, o que los bordes se hablen entre sí); descartar para siempre un borde caído; repartir los pedidos entre los bordes por turnos.
- Por qué esta: el README pide que la selección sea «una política explícita y configurable, no una decisión implícita», y la decisión del 16 nov deja la política concreta a Samy. Una lista de preferencia en la configuración es la política más corta que se puede leer y cambiar, y es coherente con «el borde preferido que responda» de `fase1/config.py`. Dejar al final al que no respondió, en vez de descartarlo, es lo que permite que un borde que vuelve se use otra vez sin que nadie lo reinscriba. Que el cliente no hable con el origen mantiene al origen detrás de los bordes, que es la forma de una CDN, y deja la regla de obsoleto en un solo sitio (el borde). Preguntar el estado a todos los bordes sería una decisión de diseño distribuida más (membresía, consulta) que la fase 1 no necesita.
- Qué no resuelve: con el orden fijo, si `borde-1` tiene una copia obsoleta dentro de `STALE_LIMIT` y el origen está en silencio, se sirve esa copia aunque `borde-2` tenga una fresca: el cliente no lo sabe y los bordes no se hablan. Es una consecuencia aceptada de la política; queda escrita para el experimento y para la fase 2. `timeout` no se prueba en `escenarios.py` porque haría falta un borde lento (ficha F3-R03). La partición entre un borde y el origen no pasa por el selector: es el borde quien la detecta (F1-S09, F1-R09).
- Dónde está en el código: `fase1/selector.py` (`Selector`), `fase1/cliente.py` (`pedir`, `_llamar_borde`), `fase1/config.py` (`bordes`, `timeout_segundos`, `evitar_borde_segundos`). Escenario `selector` en `fase1/escenarios.py`.
- Implementa: Samy
- Revisa: Rubén (pendiente)

### 2026-11-19 — La invalidación sale del origen hacia los bordes anotados

- Decisión: el origen no descubre bordes. El arranque se los pasa con `anotar_bordes` (la misma lista estática de `Config.bordes`). `invalidar(pedido_id, recurso)` lee el disco, deja la versión de referencia al día y llama a `invalidar` de cada borde. La línea del origen lleva el recurso, la versión nueva y solo los bordes que contestaron (`bordes=borde-1,borde-2`). El borde, al recibir, borra esa copia y anota `invalidacion_recibida`. El cliente no participa. El pedido siguiente es un miss normal (`causa=no_esta`) y baja la versión nueva.
- Alternativas consideradas: subir la versión solo dentro de `responder`, para que el borde se entere cuando pregunte, sin un aviso empujado; que el cliente reenvíe la invalidación; avisar solo a los bordes que alguna vez pidieron ese recurso; marcar la copia como invalidada y dejarla guardada, en vez de borrarla.
- Por qué esta: el README dibuja la invalidación como flechas del origen a cada borde, y el historial pide en la línea del origen el recurso, la versión nueva y los bordes avisados. El origen no sabe quién guardó la copia (tampoco se entera de una expulsión), así que avisa a todos los que el arranque le anotó. Borrar al recibir es el contrato del 16 nov («Llega la invalidación de esa copia»). Dejar el aviso fuera de `responder` permite invalidar sin esperar a que alguien pida.
- Qué no resuelve: un borde que no contesta no entra en la lista, pero la línea `invalidacion_perdida` es F1-R07. Como la copia se borra al llegar el aviso, el historial no usa `miss causa=invalidada`. El aviso no tiene timeout. El origen no invalida solo por ver un cambio de hash en `responder`: hace falta llamar a `invalidar`.
- Dónde está en el código: `fase1/origen.py` (`anotar_bordes`, `invalidar`), `fase1/borde.py` (`invalidar`), el arranque en `fase1/arrancar_sistema.py` y `fase1/escenarios.py`. Escenario `python3 -m fase1.escenarios invalidar`.
- Implementa: Rubén
- Revisa: Samy (pendiente)
