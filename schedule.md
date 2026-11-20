# Estado del proyecto

Proyecto **P20 — Caché de contenido en el borde y red de distribución**, tal como está descrito en el [README](README.md).

Este archivo es el tablero del proyecto. Cada casilla es una tarea concreta. Se marca cuando el trabajo está hecho, aunque sea antes o después del día del plan. La fecha que aparece al lado es solo la referencia del calendario.

Equipo: **Rubén** y **Samy**. Las dos personas implementan, documentan y revisan.

## Cómo se marca

- `[ ]` pendiente
- `[~]` en curso
- `[x]` hecho

Una tarea se marca hecha cuando se cumplen estas cosas:

1. El comportamiento o el documento ya está en el repositorio.
2. La otra persona lo revisó y puede explicarlo con sus palabras.
3. Si hubo una decisión de diseño, ya hay entrada en `docs/decisiones.md`.
4. Si la tarea tocó código (archivo nuevo, función nueva, o comportamiento nuevo en un archivo que ya existía), `docs/codigo.md` está actualizado ese mismo día: qué es, dónde está y qué hace. Si el código cambió y esa página no, la tarea sigue abierta.

La entrada de decisión la escribe quien implementa, con este formato:

```text
### YYYY-MM-DD — título corto
- Decisión:
- Alternativas consideradas:
- Por qué esta:
- Qué no resuelve:
- Dónde está en el código:
- Implementa:
- Revisa:
```

Para ver el estado: recorre una fase y cuenta casillas abiertas. Para ver a quién le falta: mira solo el bloque de esa persona. Lo hecho son las casillas `[x]`, en el mismo sitio.

## Reglas que cierran el trabajo

- Cada archivo de código empieza con un comentario de qué responsabilidad tiene y qué no hace.
- Cada función o tipo público lleva una línea: qué entra, qué sale, y qué hace si el otro nodo no contesta.
- El comentario explica el funcionamiento. La justificación vive en `docs/decisiones.md`.
- `docs/codigo.md` es el mapa del código: qué es cada pieza, dónde está y qué hace. Quien implementa actualiza esa página en la misma sentada en que crea o cambia código. No sustituye los comentarios del archivo ni a `docs/decisiones.md`.
- Al cerrar una tarea de código se revisan juntas tres cosas: el archivo (comentario de cabecera y de funciones públicas), la entrada en `docs/codigo.md`, y la decisión en `docs/decisiones.md` si hubo una.
- Se puede usar la biblioteca estándar del lenguaje para sockets, tiempo, serialización, pruebas y, cuando toque, TLS. Ray solo se usa en la fase 1.
- La contribución del proyecto es la caché, la selección de fuente, la frescura, la invalidación y la regla de contenido obsoleto. Eso se escribe en este repositorio.
- Hay que dejar escritas las decisiones que el README dejó abiertas: política concreta de selección, política de expulsión, valor de `STALE_LIMIT`, qué se considera “el origen no responde”, y cómo se simula una invalidación perdida.
- Una lista estática de direcciones en la configuración es válida si está justificada en `docs/decisiones.md`.
- En la fase 2 cada quien implementa el rol que el otro escribió en Ray. Los dos tienen que poder defender origen y borde.
- TLS empieza solo cuando la lista de la fase 2 y la lista de la fase 3 están verdes. Hasta entonces `cifrado = false`.

## Fechas de referencia

| Entrega | Lista en el repo | Fecha oficial |
| --- | --- | --- |
| Fase 1, Ray (15 %) | sábado 28 de noviembre de 2026 | martes 1 de diciembre de 2026 |
| Fase 2, diseño nativo (50 %) | viernes 25 de diciembre de 2026 | viernes 1 de enero de 2027 |
| Fase 3, campaña e informe (35 %) | miércoles 30 de diciembre de 2026 | viernes 1 de enero de 2027 |
| TLS, plus del README | viernes 1 de enero de 2027, solo si el 30 quedó verde | viernes 1 de enero de 2027 |
| Defensa individual | el material ya está cerrado el 1 de enero | domingo 3 o lunes 4 de enero de 2027 |

El issue de la conferencia lo redactan Rubén y Samy. El texto está en la tarea F1-J07.

---

## Fase 1 — Prototipo Ray

Lista interna: **28 de noviembre**. El 29 y el 30 solo corrigen defectos de esta lista. El 1 de diciembre se publica el issue.

Corrida objetivo: un origen, dos bordes y un cliente, en varios procesos.

### Rubén

- [~] **F1-R01** Arranque de Ray en local: un origen vacío corre. (plan 16–17 nov) `python3 -m fase1.arrancar_origen` crea el actor y deja `listo` en `logs/origen.log`. Documentado en `docs/codigo.md`. Falta la revisión de Samy.
- [~] **F1-R02** `docs/contrato.md`: operaciones visibles (pedir un recurso, recibir versión y resultado), sin nombres internos de Ray. Samy revisa. (plan 16–17 nov) El texto ya cubre `rechaza` y `file_doesnt_exist`. Falta la revisión de Samy.
- [~] **F1-R03** Esqueleto de `registrar` con el formato del README. Samy revisa. (plan 16–17 nov) Código en `fase1/registro.py`. Documentado en `docs/codigo.md`. Falta la revisión de Samy.
- [~] **F1-R04** Esqueleto del actor origen. Samy revisa. (plan 16–17 nov) Actor en `fase1/origen.py`. Documentado en `docs/codigo.md`. Falta la revisión de Samy.
- [~] **F1-R05** El origen guarda versiones, responde un recurso y anota `responde`. Samy revisa. (plan 18–20 nov) `responder` en `fase1/origen.py` lee `contenido/`, versiona por hash y anota. Documentado en `docs/codigo.md`. Falta la revisión de Samy.
- [~] **F1-R06** Invalidación desde el origen, con la lista de bordes avisados. Samy la aplica en el borde. (plan 21–22 nov) `invalidar` en `fase1/origen.py` avisa a los bordes de `anotar_bordes` y anota `bordes=borde-1,borde-2`. El borde borra la copia y anota `invalidacion_recibida`. Escenario `python3 -m fase1.escenarios invalidar`. Documentado en `docs/codigo.md` y `docs/decisiones.md`. Falta la revisión de Samy. El aviso que no llega sigue en F1-R07.
- [ ] **F1-R07** Caso en que un borde no recibe el aviso, anotado en el historial. Samy revisa. (plan 21–22 nov)
- [ ] **F1-R08** Revalidación del lado origen: misma versión o versión nueva. Samy revisa. (plan 23–24 nov)
- [ ] **F1-R09** Provoca la partición del experimento y deja la evidencia en `logs/`. Samy redacta la ficha. (plan 25–26 nov)
- [ ] **F1-R10** `docs/salida-fase1.md`: las cinco respuestas de la compuerta (qué problema resuelve, qué comportamiento tiene que sobrevivir al rediseño, qué hace el código, qué hace Ray, qué semántica de fallo se observó). Samy revisa. (plan 27 nov)
- [ ] **F1-R11** Revisa el diagrama y el mapa de Samy, y se los explica en voz alta. (plan 27 nov)

### Samy

- [~] **F1-S01** Arranque de Ray en local: un borde vacío corre. (plan 16–17 nov) `python3 -m fase1.arrancar_borde` crea origen y `borde-1`, deja `listo` en `logs/borde-1.log` y muestra el estado vacío. Documentado en `docs/codigo.md`. Falta la revisión de Rubén.
- [~] **F1-S02** Borrador de `docs/diagrama.md`: componentes de la aplicación y qué parte de Ray usa cada uno. Rubén revisa. (plan 16–17 nov) Borrador escrito: procesos, tabla componente/Ray y lo que Ray decide por nosotros. Falta la revisión de Rubén.
- [~] **F1-S03** Esqueleto del actor borde y del cliente. Rubén revisa. (plan 16–17 nov) `fase1/borde.py` (reenvía al origen, sin copias), `fase1/cliente.py` (pedido_id, solicitud, respuesta), `fase1/config.py` y `fase1/arrancar_sistema.py` (origen + 2 bordes + cliente, un pedido de prueba). Documentado en `docs/codigo.md` y `docs/decisiones.md`. Falta la revisión de Rubén.
- [~] **F1-S04** Borde: miss, bajada desde el origen, `guarda` y hit. Anota `miss`, `hit`, `pide_origen` y `guarda`. Rubén revisa. (plan 18–20 nov) `fase1/borde.py` guarda copias en memoria (`Copia`: versión, bytes, hora); `pedir` anota `miss causa=no_esta`, `pide_origen`, `guarda` y, en el segundo pedido, `hit` sin tocar el origen. `python3 -m fase1.arrancar_sistema` hace miss → hit → `file_doesnt_exist`. Documentado en `docs/codigo.md` y `docs/decisiones.md`. Falta la revisión de Rubén.
- [~] **F1-S05** TTL y estado fresca / obsoleta en el borde. Rubén revisa. (plan 21–22 nov; hecho el 19 nov) `Copia.expira_en`; `hit estado=fresca`, `miss causa=expirada`, `pide_origen version=N`, `revalida renovo=si|no`; `estado()` dice fresca/obsoleta. Escenario `python3 -m fase1.escenarios ttl` (con `P20_TTL=3`). Documentado en `docs/codigo.md` y `docs/decisiones.md`. Falta la revisión de Rubén.
- [~] **F1-S06** Expulsión LRU con capacidad pequeña, visible en el log. Rubén revisa. (plan 21–22 nov; hecho el 19 nov) `OrderedDict` en orden de uso, capacidad 2, línea `expulsion recurso=… politica=LRU entra=…`. `contenido/apunte-2.txt` y `apunte-3.txt` para llenar el borde. Escenario `fase1.escenarios lru`. Documentado. Falta la revisión de Rubén.
- [~] **F1-S07** Selección de fuente: si un borde no responde, el cliente usa el otro. Rubén revisa. (plan 21–22 nov; hecho el 19 nov) `fase1/selector.py` (orden fijo de `Config.bordes`, el que no respondió va al final `evitar_borde_segundos`) y `fase1/cliente.py` con `ray.wait(timeout)`: líneas `timeout` / `nodo_caido` y `solicitud` al siguiente borde; `rechaza` de un borde también pasa al siguiente. Escenario `fase1.escenarios selector` (mata `borde-1`). Documentado. Falta la revisión de Rubén.
- [ ] **F1-S08** Revalidación del lado borde. Rubén revisa. (plan 23–24 nov) Desde el 19 nov el borde ya compara la versión con la del origen y anota `revalida` (S05), pero bajando el archivo entero; esta tarea es el mensaje de revalidación sin bytes, contra F1-R08.
- [ ] **F1-S09** Regla de obsoleto cuando el origen no responde: `sirve_obsoleta` dentro de `STALE_LIMIT` y `rechaza` fuera. Rubén define el número con ella y revisa. (plan 23–24 nov)
- [ ] **F1-S10** `docs/experimento-fase1.md`: escenario, predicción y qué se observó en la partición (una copia dentro del límite y otra fuera). Rubén revisa. (plan 25–26 nov)
- [ ] **F1-S11** `docs/mapa-ray.md`: para cada requisito, qué lo resuelve hoy Ray y qué habría que hacer explícito después. Cubre ejecución remota, estado, fallo y observabilidad. Rubén revisa. (plan 25–26 nov)
- [ ] **F1-S12** Revisa el contrato, el registro y las decisiones de Rubén, y se los explica en voz alta. (plan 27 nov)

### Los dos

- [~] **F1-J01** Primera entrada de `docs/decisiones.md`: lenguaje Python + Ray, y el valor inicial de `STALE_LIMIT`. (plan 16–17 nov) Las dos entradas están escritas. Falta la revisión de Samy.
- [ ] **F1-J02** Un cliente pide un recurso desconocido y el segundo pedido es hit. El historial se filtra por `pedido_id`. (plan 18–20 nov) La corrida de `fase1/arrancar_sistema.py` ya lo hace (18 nov, ver `docs/codigo.md`); falta mirarlo juntos y filtrar `logs/*.log` por `pedido_id`.
- [ ] **F1-J03** `registrar` está activo desde la primera operación, con el formato del README. `cifrado = false`.
- [ ] **F1-J04** Cada archivo de código de esta fase tiene comentario de cabecera, cada función pública tiene su línea de funcionamiento, y `docs/codigo.md` describe todas las piezas de esta fase.
- [ ] **F1-J05** Los resultados del cliente existen: `hit`, `miss`, `sirve_obsoleta`, `rechaza`, `file_doesnt_exist`. (plan 23–24 nov)
- [ ] **F1-J06** Checklist juntos. Los diez comportamientos de abajo corren en una corrida repetible. Si algo falla, se anota aquí y se corrige el 29 o el 30. (plan 28 nov)
- [ ] **F1-J07** Texto del issue escrito en local, sin publicarlo. (plan 29–30 nov)
- [ ] **F1-J08** El repositorio se abre sin cuenta. Publican el issue en [matcom/distributed-systems-2026](https://github.com/matcom/distributed-systems-2026). (plan 1 dic)

Texto del issue, y nada más alrededor que haga falta para que se entienda:

```text
Tema
P20 — Caché de contenido en el borde y red de distribución

Integrantes
Rubén — <nombre completo>, grupo <número>
Samy — <nombre completo>, grupo <número>

Link público
https://github.com/ChickenLittle02/Distributed_SystemFP
```

### Los diez comportamientos (se marcan dentro de F1-J06)

- [ ] Hit de una copia fresca.
- [ ] Miss si no está, y bajada desde el origen.
- [ ] Versión y expiración por TTL.
- [ ] Expulsión LRU cuando el borde se llena.
- [ ] Invalidación que llega a los dos bordes.
- [ ] Un borde no aplica la invalidación, y eso queda anotado.
- [ ] Revalidación cuando la copia expiró y el origen responde.
- [ ] Un borde no responde y el selector usa el otro.
- [ ] Origen inalcanzable: se sirve la copia si su edad es menor o igual que `STALE_LIMIT`, y se rechaza si la supera.
- [ ] `registrar` desde la primera operación. `cifrado = false`.

### Cierre de la fase 1

La fase queda lista cuando F1-R01–R11, F1-S01–S12, F1-J01–J08 y los diez comportamientos están en `[x]`.

- Samy puede explicar el origen y el registro.
- Rubén puede explicar el borde, el selector y la regla de obsoleto.

---

## Fase 2 — Diseño nativo

Lista interna: **25 de diciembre**. Congelado de funcionalidad: **23 de diciembre**. El 24 y el 25 cierran la lista. Ray deja de ser dependencia de ejecución en este cierre.

El calendario asume **Go**. La elección, o la alternativa, se escribe en F2-R01. Si es otro lenguaje, la decisión dice por qué no esconde transporte, fallo, invalidación y obsoleto.

El mismo contrato de `docs/contrato.md`, en procesos separados, sin memoria compartida. El canal sigue en claro.

### Rubén

- [ ] **F2-R01** Decisión de lenguaje en `docs/decisiones.md`. (plan 2 dic)
- [ ] **F2-R02** Interfaz `enviar` / `recibir` y TCP en claro, con timeout. Comentario de cabecera del paquete: la lógica de caché no abre sockets. Samy lo usa desde origen y cliente, y revisa. (plan 2–4 dic)
- [ ] **F2-R03** Borde nativo: guardar, hit, miss, TTL y `guarda`. Sin expulsión todavía. Samy revisa. (plan 5–9 dic)
- [ ] **F2-R04** Expulsión LRU y estados fresca / obsoleta / invalidada en el borde. La expulsión se ve en el log. FIFO solo si el núcleo ya está verde; si no entra, se deja dicho en `docs/decisiones.md`. Samy revisa. (plan 10–12 dic)
- [ ] **F2-R05** El borde aplica la invalidación, incluido el caso en que el aviso no se aplica, y hace la revalidación. Samy revisa. (plan 13–16 dic)
- [ ] **F2-R06** Regla `STALE_LIMIT` en el borde: `origen_no_responde`, `sirve_obsoleta`, `rechaza`. Samy revisa. (plan 17–19 dic)
- [ ] **F2-R07** Pruebas del borde: hit, miss, expulsión, dentro y fuera de `STALE_LIMIT`. Corren solas. Samy revisa. (plan 20–22 dic)
- [ ] **F2-R08** Sus filas de `docs/decisiones.md`: por cada mecanismo suyo, qué hacía Ray, qué opciones nativas había, cuál se eligió y qué se pierde. Samy revisa. (plan 20–22 dic)
- [ ] **F2-R09** En `docs/diseno-nativo.md`, redacta y Samy revisa el 22: qué estado hay y quién es dueño (el origen es dueño de la versión de referencia; el borde es dueño solo de su copia).
- [ ] **F2-R10** En `docs/diseno-nativo.md`, redacta y Samy revisa: cuándo una lectura está completa, y por qué guardar en caché no es un acuse durable del origen.
- [ ] **F2-R11** En `docs/diseno-nativo.md`, redacta y Samy revisa: partición, `STALE_LIMIT`, y qué cambia cuando el origen vuelve.
- [ ] **F2-R12** En `docs/diseno-nativo.md`, redacta y Samy revisa: cómo se detecta un nodo que no responde (`timeout` o `nodo_caido`).
- [ ] **F2-R13** Recorre el código de Samy y señala comentarios o decisiones que faltan. (plan 23 dic)
- [ ] **F2-R14** Puede modificar una función del origen o del selector y explicar qué garantía toca. (cierre 25 dic)

### Samy

- [ ] **F2-S01** `registrar` en el lenguaje nativo, mismo formato del README (`logs/*.log` y la misma línea en consola). Rubén revisa. (plan 2–4 dic)
- [ ] **F2-S02** Formato de mensaje como texto: recurso, versión, `pedido_id`, invalidación. Rubén revisa. (plan 2–4 dic)
- [ ] **F2-S03** Borrador de la tabla nativa en `docs/decisiones.md`, a partir de `docs/mapa-ray.md`. Rubén completa sus filas. (plan 2–4 dic)
- [ ] **F2-S04** Origen nativo: versiones y `responde`. Rubén revisa. (plan 5–9 dic)
- [ ] **F2-S05** Cliente mínimo que pide un recurso a un borde fijo. Rubén revisa. (plan 5–9 dic)
- [ ] **F2-S06** Invalidación que sale del origen. Rubén la aplica en el borde. (plan 10–12 dic)
- [ ] **F2-S07** Mensaje de revalidación: misma versión o versión nueva. Rubén revisa. (plan 10–12 dic)
- [ ] **F2-S08** Selector de fuente y cliente: borde caído, otro borde, origen. Anota `solicitud` y `respuesta`. Rubén revisa. (plan 13–16 dic)
- [ ] **F2-S09** Pruebas del origen: respuesta, invalidación perdida, borde que no está. Corren solas. Rubén revisa. (plan 17–19 dic)
- [ ] **F2-S10** `docs/diagrama.md` actualizado al diseño nativo. Rubén revisa. (plan 20–22 dic)
- [ ] **F2-S11** Sus filas de `docs/decisiones.md`. Rubén revisa. (plan 20–22 dic)
- [ ] **F2-S12** En `docs/diseno-nativo.md`, redacta y Rubén revisa el 22: protocolo, quién habla con quién y qué campos viajan.
- [ ] **F2-S13** En `docs/diseno-nativo.md`, redacta y Rubén revisa: identidad de recurso y `pedido_id`, arranque estático y lista de miembros.
- [ ] **F2-S14** En `docs/diseno-nativo.md`, redacta y Rubén revisa: qué se puede reintentar y cómo se reconoce un duplicado.
- [ ] **F2-S15** En `docs/diseno-nativo.md`, redacta y Rubén revisa: invalidación perdida, borde que vuelve, y modelo de confianza con el canal en claro.
- [ ] **F2-S16** Disclosure de uso de IA, en el formato de la metodología, si se usó un asistente. Rubén revisa que lo que él usó también esté declarado. (plan 20–22 dic)
- [ ] **F2-S17** Recorre el código de Rubén y señala comentarios o decisiones que faltan. (plan 23 dic)
- [ ] **F2-S18** Puede modificar una función del borde o de `STALE_LIMIT` y explicar qué garantía toca. (cierre 25 dic)

### Los dos

- [ ] **F2-J01** Un proceso le manda una línea a otro y los dos la anotan. `cifrado = false` está en la configuración. Direcciones en configuración, justificadas como arranque estático. (plan 2–4 dic)
- [ ] **F2-J02** Miss, bajada y hit, igual que en Ray, con origen, borde y cliente en procesos separados. (plan 5–9 dic)
- [ ] **F2-J03** Sesión del 12: se congela el texto de invalidar y de revalidar. La expulsión se ve en el log. (plan 12 dic)
- [ ] **F2-J04** Un borde apagado no impide resolver el pedido. Una invalidación perdida queda en el historial. (plan 13–16 dic)
- [ ] **F2-J05** Partición reproducida: servir dentro de `STALE_LIMIT` y rechazar fuera. (plan 17–19 dic)
- [ ] **F2-J06** Cada archivo nativo tiene comentario de cabecera y cada función pública tiene su línea de funcionamiento.
- [ ] **F2-J07** Congelado. Después del 23 de diciembre no entra ninguna pieza nueva. Un defecto que impida un escenario de la campaña sí se puede corregir después; una funcionalidad nueva, no. (plan 23 dic)
- [ ] **F2-J08** Checklist juntos. `docs/diseno-nativo.md` tiene las ocho respuestas revisadas por los dos. TLS sigue en `false`. (plan 24–25 dic)

### Cierre de la fase 2

La fase queda lista cuando F2-R01–R14, F2-S01–S18 y F2-J01–J08 están en `[x]`.

Queda fuera de este cierre: TLS, una segunda política de expulsión, cifrado propio y las fichas de la campaña.

---

## Fase 3 — Campaña, comparación e informe

Lista interna: **30 de diciembre**. Se mide el sistema en claro que quedó el 25. Si un escenario no corre por un defecto, se corrige y se anota en la ficha.

Los fallos se provocan con lo que el sistema ya sabe hacer: matar un proceso, no entregar una invalidación, bajar el timeout, llenar la caché, repetir un `pedido_id`. La predicción se escribe antes de correr el escenario. La evidencia son los logs.

Cada ficha vive en `docs/campana/` y lleva estos campos:

```text
escenario
carga
afirmación que se pone a prueba
predicción
configuración
cómo se dispara el fallo
evidencia recogida
qué se observó
conclusión
qué queda sin saber
```

La recuperación se describe como es. Si al reiniciar un borde la caché está vacía porque solo vivía en memoria, la ficha dice eso: el primer pedido después del reinicio es un miss.

### Rubén — cuatro fichas

- [ ] **F3-R01** Predicción escrita, antes de correr, del borde lento y de la caché llena. (plan 26 dic)
- [ ] **F3-R02** Ficha de línea base: miss, bajada y hit, con origen y dos bordes. Guion repetible. Samy revisa. (plan 26 dic)
- [ ] **F3-R03** Ficha de borde lento: el timeout lo trata como caído y el selector usa otra fuente. Evidencia en `logs/`. Samy revisa. (plan 27 dic)
- [ ] **F3-R04** Ficha de caché llena: la expulsión LRU acota la memoria y el log dice qué sale. Samy revisa. (plan 27 dic)
- [ ] **F3-R05** Ficha de partición y reconexión: dentro de `STALE_LIMIT` se sirve, fuera se rechaza, y al volver el origen la revalidación actualiza. Samy revisa. (plan 28 dic)

### Rubén — documentos

- [ ] **F3-R06** Filas de `docs/comparacion-ray-nativo.md`: fallo, timeout, recuperación y contenido obsoleto. Cada fila dice qué se midió o qué se contó, y qué no. Samy revisa. (plan 29 dic)
- [ ] **F3-R07** En `docs/garantias.md`: qué está garantizado sobre frescura, `STALE_LIMIT` y expulsión, y qué es solo un objetivo de disponibilidad. Cada afirmación dice qué evidencia la sostiene. Samy revisa. (plan 29 dic)
- [ ] **F3-R08** En `docs/informe.md`: cómo repetir en local sus cuatro fichas, con los comandos. Samy revisa. (plan 29 dic)
- [ ] **F3-R09** Ejecuta los cuatro escenarios de Samy sin leer antes la conclusión, dice qué espera ver y después compara con la ficha. (plan 30 dic)
- [ ] **F3-R10** Explica, sin abrir la ficha de Samy, qué pasa si se cae un borde, si se pierde una invalidación y si llega un `pedido_id` repetido. (cierre 30 dic)

### Samy — cuatro fichas

- [ ] **F3-S01** Predicción escrita, antes de correr, del borde caído. Anota cómo se mata el proceso. (plan 26 dic)
- [ ] **F3-S02** Ficha de borde caído: un borde no responde y el pedido se resuelve por otro. Evidencia en `logs/`. Rubén revisa. (plan 26 dic)
- [ ] **F3-S03** Ficha de borde que reinicia: qué conserva y qué pierde al volver, según el diseño real del 25. Rubén revisa. (plan 27 dic)
- [ ] **F3-S04** Ficha de invalidación perdida: el borde que no recibió el aviso sigue con la copia vieja hasta revalidar o expirar. Rubén revisa. (plan 27 dic)
- [ ] **F3-S05** Ficha de pedido repetido y dos clientes: el mismo `pedido_id` no corrompe la versión, y dos clientes pueden pedir a la vez. Rubén revisa. (plan 28 dic)

### Samy — documentos

- [ ] **F3-S06** Apertura de `docs/comparacion-ray-nativo.md` y filas de complejidad, mecanismos explícitos, dependencias, arranque y dificultad de depurar. Rubén revisa. (plan 29 dic)
- [ ] **F3-S07** En `docs/garantias.md`: qué está garantizado sobre selección, invalidación y duplicados, y qué no. Rubén revisa. (plan 29 dic)
- [ ] **F3-S08** En `docs/informe.md`: cómo repetir sus cuatro fichas, y el párrafo que enlaza contrato, diseño y campaña. Rubén revisa. (plan 29 dic)
- [ ] **F3-S09** Disclosure de IA dejado por escrito en el formato de la metodología. Rubén revisa el suyo. (plan 29 dic)
- [ ] **F3-S10** Lee las fichas de Rubén. (plan 28–29 dic)
- [ ] **F3-S11** Ejecuta los cuatro escenarios de Rubén sin leer antes la conclusión, dice qué espera ver y después compara con la ficha. (plan 30 dic)
- [ ] **F3-S12** Explica, sin abrir la ficha de Rubén, qué pasa con un borde lento, con la caché llena y con el origen partido dentro y fuera de `STALE_LIMIT`. (cierre 30 dic)

### Los dos

- [ ] **F3-J01** Las predicciones de las ocho fichas están escritas antes de observar el escenario. (plan 26 dic)
- [ ] **F3-J02** Las ocho fichas están en `docs/campana/`, con evidencia en `logs/`. Si una corrida falló por un defecto, el arreglo queda anotado en esa ficha. (plan 28 dic)
- [ ] **F3-J03** `docs/comparacion-ray-nativo.md`, `docs/garantias.md` y `docs/informe.md` leídos por los dos. El informe dice cómo correr la campaña en una máquina local. (plan 29–30 dic)
- [ ] **F3-J04** `cifrado` sigue en `false`. El código nuevo respecto al 25 de diciembre son solo correcciones anotadas en la ficha correspondiente.

### Cierre de la fase 3

La fase queda lista cuando F3-R01–R10, F3-S01–S12 y F3-J01–J04 están en `[x]`.

Si el 30 no cierra, el 31 se usa para cerrar esta fase y TLS no empieza.

---

## TLS — plus, solo si las fases 2 y 3 están verdes

Estas casillas se abren el día en que F2 y F3 ya están en `[x]`. Si el 30 de diciembre falta campaña, comparación o informe, el 31 y el 1 de enero se usan para terminar eso y estas tareas se quedan pendientes. `cifrado` se entrega en `false`.

La lógica de caché no se entera. Solo cambian `enviar` y `recibir`. El cliente sigue hablando con el borde en claro. El canal cifrado es el de la bajada, la revalidación y la invalidación. El historial y las copias guardadas siguen en claro. El cifrado es el de la biblioteca del lenguaje.

### Rubén

- [ ] **TLS-R01** Con `cifrado = true`, `enviar` y `recibir` envuelven el mismo TCP con la biblioteca TLS del lenguaje. El comentario de cabecera dice que son el único sitio que conoce el cifrado. Samy revisa. (plan 31 dic, si la fase 3 cerró)
- [ ] **TLS-R02** Un fallo de handshake se trata como `origen_no_responde`: queda en el historial y el borde aplica la regla de obsoleto. Samy revisa. (plan 31 dic)
- [ ] **TLS-R03** Entrada en `docs/decisiones.md`: biblioteca usada, qué verifica el borde y por qué un handshake fallido equivale a origen inalcanzable. Samy revisa.
- [ ] **TLS-R04** Revisa las cuatro pruebas que repite Samy. Puede provocar un handshake fallido y decir qué línea queda en el historial. (plan 1 ene)
- [ ] **TLS-R05** Solo si TLS-R01–R04 y TLS-S01–S04 ya pasan y sobra el día: el origen rechaza un borde desconocido. Samy revisa. (plan 1 ene)

### Samy

- [ ] **TLS-S01** Autoridad local del proyecto y certificado del origen. Rubén revisa. (plan 31 dic, si la fase 3 cerró)
- [ ] **TLS-S02** Cada borde comprueba que habla con ese origen y rechaza a otro. Rubén revisa. (plan 31 dic)
- [ ] **TLS-S03** Con `cifrado = true` repite hit, invalidación perdida, revalidación y las dos ramas de `STALE_LIMIT`. El resultado y el formato del historial son los mismos que en claro. Rubén revisa. (plan 1 ene)
- [ ] **TLS-S04** Actualiza el párrafo de confianza en `docs/garantias.md`. Puede decir qué certificado se comprueba y qué no cubre el canal: el cliente, el historial y las copias. Rubén revisa. (plan 1 ene)
- [ ] **TLS-S05** Solo si los cuatro puntos de arriba ya pasan y sobra el día: emite el certificado de cada borde. Rubén revisa. (plan 1 ene)

### Los dos

- [ ] **TLS-J01** Decisión del día 31: o TLS ya habla entre origen y borde, o queda escrito que esta entrega va en claro y en qué paso se detuvo el intento.
- [ ] **TLS-J02** La entrega no deja `cifrado = true` a medias. O las cuatro pruebas pasan igual que en claro, o la configuración vuelve a `false` y el informe dice en qué paso se detuvo.

### Cierre de TLS

Entra en la entrega solo si TLS-R01–R04, TLS-S01–S04 y TLS-J01–J02 están en `[x]`. TLS-R05 y TLS-S05 son el quinto punto: certificados de borde. Si no da el tiempo, se quedan abiertas y no bloquean la entrega.

---

## Defensa

Material cerrado el 1 de enero. Estos días no se implementa.

- [ ] **DEF-R01** Rubén: ensayo hablado, sin commits. Si TLS entró, explica el handshake fallido. Si no entró, la defensa habla del sistema en claro. (plan 2 ene)
- [ ] **DEF-S01** Samy: ensayo hablado, sin commits. Misma regla sobre TLS. (plan 2 ene)
- [ ] **DEF-J01** Defensa individual, domingo 3 o lunes 4 de enero. Se razona sobre lo entregado el 1 de enero.
