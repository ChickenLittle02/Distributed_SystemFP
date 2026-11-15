# Plan de entregas

Proyecto **P20 — Caché de contenido en el borde y red de distribución**, tal como está descrito en el [README](README.md).

La metodología del curso tiene tres fases. El profesor fijó el Ray para el 1 de diciembre y el diseño final para el 1 de enero. La fase 3 se asume en ese mismo cierre: la campaña queda lista el 30 de diciembre y, si entra, TLS el 1 de enero. La defensa se prepara para el **domingo 3 o el lunes 4 de enero**.

| Entrega | Fecha oficial | Lista en el repo | Qué es |
| --- | --- | --- | --- |
| Versión con Ray | martes 1 de diciembre de 2026 | sábado 28 de noviembre de 2026 | Fase 1 (15 %) |
| Diseño nativo | viernes 1 de enero de 2027 | viernes 25 de diciembre de 2026 | Fase 2 (50 %) |
| Campaña, comparación e informe | viernes 1 de enero de 2027 | miércoles 30 de diciembre de 2026 | Fase 3 (35 %), salvo el acto de la defensa |
| TLS entre origen y bordes | viernes 1 de enero de 2027 | viernes 1 de enero de 2027, solo si el 30 de diciembre quedó verde | Plus del README. No bloquea la entrega |
| Defensa individual | domingo 3 o lunes 4 de enero de 2027 | el material ya está cerrado el 1 de enero | Se explica lo que ya está en el repo. No se implementa ese día |

La fase 3 no es solo hablar en la defensa. También pesa la campaña de fallos, el análisis de garantías, la comparación Ray/nativo y el informe. Eso queda verde el 30 de diciembre. El 31 de diciembre y el 1 de enero se usan para intentar TLS, y solo si esa campaña ya está cerrada. El 3 o el 4 de enero solo se defiende.

El issue de la conferencia lo redactan Rubén y Samy. Este archivo solo dice qué tiene que contener y cuándo.

Equipo: **Rubén** y **Samy**. Las dos personas implementan, documentan y revisan. Nadie queda solo en documentación o solo en código.

## Pautas de desarrollo

Estas reglas valen desde el 16 de noviembre. Una pieza no está terminada si le falta la decisión o el comentario.

### Toda decisión de implementación queda mencionada y justificada

Cada vez que se elige cómo hacer algo (formato de mensaje, política de expulsión, valor de `STALE_LIMIT`, qué pasa si un aviso no llega, lenguaje, biblioteca), se agrega una entrada en `docs/decisiones.md` antes de dar la pieza por hecha:

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

La entrada la escribe quien implementa. La otra persona la lee y, si no puede explicar la decisión con sus palabras, la pieza sigue abierta.

No hace falta decidir de antemano lo que el README ya dejó fuera (cifrado propio, historial cifrado, copias cifradas en disco). Sí hay que escribir las decisiones que el README dejó abiertas: política concreta de selección, política de expulsión, valor de `STALE_LIMIT`, qué se considera “el origen no responde”, y cómo se simula una invalidación perdida.

### Todo el código queda documentado, al menos por encima

- Cada archivo empieza con un comentario de qué responsabilidad tiene y qué no hace.
- Cada función o tipo público lleva una línea: qué entra, qué sale, y qué hace si el otro nodo no contesta.
- El comentario explica el funcionamiento. No sustituye a la entrada de `docs/decisiones.md`.

### Qué se puede usar

El profesor no acepta software que automatice o simplifique las decisiones de diseño distribuido. Ante una biblioteca o servicio que genere duda, se pregunta; si no hay respuesta, no se usa.

En este proyecto la contribución es la caché, la selección de fuente, la frescura, la invalidación y la regla de contenido obsoleto. Eso se escribe en el repositorio.

Se puede usar la biblioteca estándar del lenguaje para sockets, tiempo, serialización, pruebas y, a partir del 31 de diciembre, TLS. El cifrado no se escribe a mano: se usa la biblioteca del lenguaje. Ray se usa únicamente en la fase 1. TLS no empieza antes de que el sistema en claro y la campaña estén verdes.

No se usa un caché, proxy, cola, registro de miembros o almacén distribuido ya hecho para resolver hit, miss, expulsión, invalidación, membresía o la política de obsoleto. Una lista estática de direcciones en la configuración es una decisión válida: hay que justificarla en `docs/decisiones.md`.

### Reparto

El trabajo se parte por comportamiento observable, no por cantidad de archivos. Cada persona, al terminar su pieza, se la explica a la otra y la otra la revisa el mismo bloque.

En la fase 2 cada uno implementa el rol que el otro escribió en Ray. Así los dos han implementado origen y borde, que es lo que hay que poder defender.

| Comportamiento | Fase 1 (Ray), hasta el 28 nov | Fase 2 (nativo), hasta el 25 dic | Del 26 dic al 1 ene |
| --- | --- | --- | --- |
| Contrato observable y respuestas a la salida de la fase 1 | Rubén escribe, Samy revisa | Se reutiliza. Un cambio se justifica en `docs/decisiones.md` | Se cita tal cual. Un cambio se justifica |
| Diagrama de arquitectura | Samy escribe, Rubén revisa | Samy lo actualiza al diseño nativo, Rubén revisa | Se usa como figura del informe |
| `registrar` y formato del historial | Rubén | Samy lo lleva al lenguaje nativo, Rubén revisa | La evidencia de cada fallo sale de esos logs |
| Origen: versiones y respuesta | Rubén | Samy | Samy: ficha de reinicio y de invalidación |
| Invalidación, incluido un aviso que no llega | Rubén dispara, Samy la aplica en el borde | Samy la envía, Rubén la aplica en el borde | Samy escribe la ficha |
| Borde: hit, miss, TTL, guardar | Samy | Rubén | Rubén: ficha de línea base |
| Expulsión | Samy (LRU) | Rubén (LRU; FIFO solo si el núcleo ya está verde) | Rubén: ficha de llenado |
| Cliente y selección de fuente | Samy | Samy | Samy: ficha de borde caído y de pedido duplicado |
| Regla `STALE_LIMIT` | Samy la aplica, Rubén define el número con ella | Rubén | Rubén: ficha de partición y de reconexión |
| Transporte `enviar` / `recibir` | Lo aporta Ray. Se deja escrito qué hace Ray | Rubén (TCP en claro). Samy lo usa desde origen y cliente | Rubén: ficha de borde lento / timeout |
| Mapa de dependencias de Ray | Samy escribe, Rubén revisa | Samy lo convierte en la tabla nativa, Rubén completa sus filas | Samy abre la comparación. Rubén escribe las filas de fallo, timeout y obsoleto |
| Prueba de fallo escrita | Los dos. Rubén provoca el fallo, Samy redacta la evidencia | Los dos. Samy provoca los fallos de su parte, Rubén los de la suya | Cuatro fichas cada uno. El otro las reproduce el 30 de diciembre |
| TLS origen–borde | No se implementa | El transporte queda listo para envolver el mismo TCP, con `cifrado = false` | Si el 30 de diciembre está verde: Rubén envuelve `enviar` / `recibir`. Samy crea la autoridad local y repite las pruebas |

## Entrega del 1 de diciembre

Lista el **28 de noviembre**. El 29 y el 30 solo corrigen defectos de esa lista. El 1 de diciembre se publica el issue; no se abre funcionalidad nueva.

### Qué tiene que estar

Prototipo Ray que ejecute de verdad en varios procesos, con un origen, dos bordes y un cliente:

1. Hit de una copia fresca.
2. Miss si no está, y bajada desde el origen.
3. Versión y expiración por TTL.
4. Expulsión LRU cuando el borde se llena.
5. Invalidación que llega a los dos bordes, y un caso en que un borde no la aplica.
6. Revalidación cuando la copia expiró y el origen responde.
7. Un borde que no responde y el selector usa el otro.
8. Origen inalcanzable: se sirve la copia si su edad es menor o igual que `STALE_LIMIT`, y se rechaza si la supera.
9. `registrar` desde la primera operación, con el formato del README.
10. `cifrado = false`. TLS no se toca.

Artefactos de la fase 1:

- `docs/contrato.md`: operaciones visibles (pedir un recurso, recibir versión y resultado) sin nombres internos de Ray.
- `docs/diagrama.md`: componentes de la aplicación y qué parte de Ray usa cada uno.
- `docs/mapa-ray.md`: para cada requisito, qué lo resuelve hoy Ray y qué habría que hacer explícito después.
- `docs/experimento-fase1.md`: un experimento. El obligatorio es la partición con el origen y la regla de `STALE_LIMIT` (una copia dentro del límite y otra fuera).
- `docs/decisiones.md` al día, y comentarios de cabecera en el código de esta fase.
- Respuestas cortas, en `docs/salida-fase1.md`, a las cinco preguntas de la compuerta de salida: qué problema resuelve, qué comportamiento tiene que sobrevivir al rediseño, qué hace el código, qué hace Ray, y qué semántica de fallo se observó.

### Calendario

| Fechas | Rubén | Samy | Cierre del bloque |
| --- | --- | --- | --- |
| lun 16 – mar 17 nov | Arranque de Ray en local. `docs/contrato.md`. Esqueleto de `registrar` y del actor origen | Mismo arranque. Borrador de `docs/diagrama.md`. Esqueleto del actor borde y del cliente | Los dos corren un origen y un borde vacíos, y existe la primera entrada de decisión (lenguaje Python + Ray, y el valor inicial de `STALE_LIMIT`) |
| mié 18 – vie 20 nov | Origen guarda versiones y responde un recurso. Anota `responde` | Borde: miss, bajada, `guarda`, hit. Anota `miss`, `hit`, `pide_origen`, `guarda` | Un cliente pide un recurso desconocido y el segundo pedido es hit. Historial filtrable por `pedido_id` |
| sáb 21 – dom 22 nov | Invalidación desde el origen, con lista de bordes avisados. Caso en que un borde no recibe el aviso | TTL, estado fresca/obsoleta, y expulsión LRU con capacidad pequeña. Selección: si un borde no responde, el otro | Invalidación feliz, invalidación perdida anotada, y expulsión visible en el log |
| lun 23 – mar 24 nov | Revalidación del lado origen: misma versión o versión nueva | Revalidación del lado borde. Regla de obsoleto cuando el origen no responde | Los cuatro resultados del cliente existen: `hit`, `miss`, `sirve_obsoleta`, `rechaza` |
| mié 25 – jue 26 nov | Provoca la partición del experimento y recoge `logs/` | Redacta `docs/experimento-fase1.md` (escenario, predicción, qué se observó). Cierra `docs/mapa-ray.md` | El experimento se puede volver a correr y el mapa cubre ejecución remota, estado, fallo y observabilidad |
| vie 27 nov | `docs/salida-fase1.md` y revisión del diagrama y del mapa | Revisión del contrato, del registro y de las decisiones de Rubén | Cada quien explica en voz alta la pieza del otro |
| sáb 28 nov | Checklist de esta entrega, los dos juntos | Checklist de esta entrega, los dos juntos | Etiqueta interna: fase 1 lista. Si algo falla, se anota y se corrige el 29 o el 30 |
| dom 29 – lun 30 nov | Solo defectos del checklist | Solo defectos del checklist | Texto del issue escrito en local, sin publicarlo todavía |
| mar 1 dic | Publican el issue en [matcom/distributed-systems-2026](https://github.com/matcom/distributed-systems-2026) | Publican el issue | El enlace del repositorio es público |

### Texto del issue

Se publica el 1 de diciembre en el repositorio de las conferencias, con este contenido y nada más alrededor que haga falta para que se entienda:

```text
Tema
P20 — Caché de contenido en el borde y red de distribución

Integrantes
Rubén — <nombre completo>, grupo <número>
Samy — <nombre completo>, grupo <número>

Link público
https://github.com/ChickenLittle02/Distributed_SystemFP
```

Antes de publicarlo, comprobar que ese repositorio se abre sin cuenta.

### Lista del 28 de noviembre

- El prototipo cumple los diez puntos de arriba en una corrida repetible.
- `docs/contrato.md`, `docs/diagrama.md`, `docs/mapa-ray.md`, `docs/experimento-fase1.md`, `docs/salida-fase1.md` y `docs/decisiones.md` están en el repo.
- Cada archivo de código de la fase tiene comentario de cabecera, y cada función pública tiene su línea de funcionamiento.
- Samy puede explicar el origen y el registro. Rubén puede explicar el borde, el selector y la regla de obsoleto.

## Entrega del diseño nativo (lista el 25 de diciembre)

El diseño nativo queda listo el **25 de diciembre**. Del 26 al 30 la campaña mide ese sistema en claro. Un defecto que impida un escenario sí se puede corregir. Una funcionalidad nueva, no. TLS es la única pieza que puede agregarse después, y solo a partir del 31 si la campaña ya cerró.

Ray deja de ser dependencia de ejecución el 25 de diciembre. Puede citarse en la comparación; no puede volver dentro de otra biblioteca.

El calendario asume **Go** para los procesos nativos, que es el lenguaje que la metodología toma por defecto. El 2 de diciembre se escribe esa elección, o la alternativa, en `docs/decisiones.md`. Si la alternativa es otro lenguaje, hay que justificar por qué no esconde los mecanismos (transporte, fallo, invalidación, obsoleto). El reparto de fechas no cambia.

Hasta el 25 de diciembre el canal sigue en claro. TLS no se empieza en esta entrega aunque el 23 esté verde: primero va la campaña.

### Qué tiene que estar

El mismo contrato de `docs/contrato.md`, ejecutado por procesos separados, sin memoria compartida:

- Origen, al menos dos bordes y un cliente, cada uno en su proceso.
- Direcciones en configuración. Justificado como arranque estático.
- `enviar` / `recibir` sobre TCP en claro. La lógica de caché no abre sockets.
- Hit, miss, TTL, versiones, bajada del origen, expulsión LRU.
- Invalidación que llega y invalidación que no llega.
- Revalidación.
- Borde que no responde: el selector usa otro borde o el origen.
- Partición con el origen y la misma regla de `STALE_LIMIT` (servir dentro del límite, rechazar fuera).
- Historial con el mismo formato del README (`logs/*.log` y la misma línea en consola).
- Timeouts explícitos. Un nodo que no contesta se anota como `timeout` o `nodo_caido`.
- Pruebas que cubren el caso normal y los fallos de arriba, repetibles en local.
- `docs/decisiones.md` con una fila por mecanismo: qué hacía Ray, qué opciones nativas había, cuál se eligió y qué se pierde.
- `docs/diseno-nativo.md` responde, en corto, las preguntas del diseño: estado y dueño, cuándo una operación está completa, reintentos y duplicados, descubrimiento, fallo de un nodo, partición y qué cambia al reconectar, qué es garantía de corrección y qué es objetivo de disponibilidad, y qué evidencia queda en los logs.
- `docs/diagrama.md` actualizado al diseño nativo.
- Comentarios de cabecera y de funciones públicas en el código nativo.
- Disclosure de uso de IA en el formato de la metodología, si se usó un asistente.

Queda fuera de este cierre del 25: TLS, una segunda política de expulsión, cifrado propio, y las fichas de la campaña. La campaña empieza el 26 con el sistema ya cerrado.

### Calendario

El congelado de funcionalidad es el **miércoles 23 de diciembre**. El 24 y el 25 se usan para la lista de cierre, no para piezas nuevas. El 24 es víspera: si el 23 está verde, el 24 no se programa implementación.

| Fechas | Rubén | Samy | Cierre del bloque |
| --- | --- | --- | --- |
| mar 2 – jue 4 dic | Decisión de lenguaje. Interfaz `enviar` / `recibir` y TCP en claro, con timeout. Comentarios de ese paquete | Porta `registrar` al lenguaje nativo. Formato de mensaje (recurso, versión, `pedido_id`, invalidación) como texto. Borrador de la tabla en `docs/decisiones.md` | Un proceso le manda una línea a otro y los dos la anotan. `cifrado = false` está en la configuración |
| vie 5 – mar 9 dic | Borde nativo: guardar, hit, miss, TTL, `guarda`. Sin expulsión todavía | Origen nativo: versiones y `responde`. Cliente mínimo que pide un recurso a un borde fijo | Miss, bajada y hit, igual que en Ray, con procesos separados |
| mié 10 – vie 12 dic | Expulsión LRU y estados fresca / obsoleta / invalidada en el borde | Invalidación que sale del origen. Mensaje de revalidación (misma versión o versión nueva) | Sesión conjunta el viernes 12: se congela el texto de invalidar y de revalidar. Expulsión visible en el log |
| sáb 13 – mar 16 dic | El borde aplica invalidación, incluido el caso en que el aviso no se aplica, y hace la revalidación | Selector de fuente y cliente: borde caído, otro borde, origen. Anota `solicitud` y `respuesta` | Un borde apagado no impide resolver el pedido. Una invalidación perdida queda en el historial |
| mié 17 – vie 19 dic | Regla `STALE_LIMIT` en el borde: `origen_no_responde`, `sirve_obsoleta`, `rechaza` | Pruebas del origen: respuesta, invalidación perdida, borde que no está | Partición reproducida. Las pruebas de Samy corren solas |
| sáb 20 – mar 22 dic | Pruebas del borde: hit, miss, expulsión, dentro y fuera de `STALE_LIMIT`. Completa sus filas de `docs/decisiones.md` y sus respuestas en `docs/diseno-nativo.md` | Actualiza `docs/diagrama.md`. Completa sus filas y sus respuestas de diseño. Disclosure de IA | Batería local verde. El documento de diseño tiene las ocho respuestas, aunque sea en borrador |
| mié 23 dic | Congelado. Cada quien recorre el código del otro y señala comentarios o decisiones que faltan | Igual | No entra ninguna pieza nueva después de este día |
| jue 24 – vie 25 dic | Checklist de esta entrega | Checklist de esta entrega | Etiqueta interna: fase 2 lista. El 26 empieza la campaña sobre este código |

### Quién redacta cada respuesta de diseño

Las escribe una persona y las revisa la otra el 22 de diciembre.

| Pregunta en `docs/diseno-nativo.md` | Redacta | Revisa |
| --- | --- | --- |
| Qué estado hay y quién es dueño (origen dueño de la versión de referencia; el borde dueño solo de su copia) | Rubén | Samy |
| Cuándo una lectura está completa, y por qué guardar en caché no es un acuse durable del origen | Rubén | Samy |
| Partición, `STALE_LIMIT`, y qué cambia cuando el origen vuelve | Rubén | Samy |
| Cómo se detecta un nodo que no responde | Rubén | Samy |
| Protocolo: quién habla con quién y qué campos viajan | Samy | Rubén |
| Identidad de recurso y `pedido_id`. Arranque estático y lista de miembros | Samy | Rubén |
| Qué se puede reintentar y cómo se reconoce un duplicado | Samy | Rubén |
| Invalidación perdida, borde que vuelve, y modelo de confianza con el canal en claro | Samy | Rubén |

### Lista del 25 de diciembre

- Caso normal y los fallos del README (borde caído, invalidación que no llega, partición dentro y fuera de `STALE_LIMIT`) corren en local sin Ray.
- La lógica de caché no abre sockets. Solo usa `enviar` y `recibir`.
- `docs/decisiones.md` tiene una entrada por cada elección de esta fase, con alternativa y motivo.
- `docs/diseno-nativo.md` y el diagrama nativo están revisados por los dos.
- Cada archivo nativo tiene comentario de cabecera y cada función pública tiene su línea de funcionamiento.
- Rubén puede modificar una función del origen o del selector y explicar qué garantía toca.
- Samy puede modificar una función del borde o de `STALE_LIMIT` y explicar qué garantía toca.
- TLS sigue en `false`. Si alguien propone empezarlo antes de tener esta lista verde, no se empieza.

## Fase 3, lista el 30 de diciembre

La defensa es el **3 o el 4 de enero**. El 30 de diciembre el repositorio ya tiene la campaña corrida, la comparación, las garantías y el informe. Esos días se mide el sistema en claro que quedó el 25. TLS no se toca aquí.

Si un escenario no se puede correr porque hay un defecto, se corrige y se anota en la ficha. No se aprovecha ese arreglo para meter persistencia en disco, otra política de expulsión ni un fallo que el diseño no tenía.

Los fallos se provocan con lo que el sistema ya sabe hacer el 25: matar un proceso, no entregar una invalidación, bajar el timeout, llenar la caché, repetir un `pedido_id`. La predicción se escribe antes de correr el escenario. La evidencia son los logs, no una captura sola.

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

La recuperación se describe como es. Si al reiniciar un borde la caché está vacía porque solo vivía en memoria, la ficha dice eso: el primer pedido después del reinicio es un miss. No se inventa durabilidad el 26 de diciembre para que el escenario se vea más completo.

### Ocho fichas, cuatro cada uno

| Ficha | Qué demuestra | Escribe y corre | Revisa |
| --- | --- | --- | --- |
| Línea base | Miss, bajada, hit, con origen y dos bordes | Rubén | Samy |
| Borde lento | El timeout lo trata como caído y el selector usa otra fuente | Rubén | Samy |
| Caché llena | La expulsión LRU acota la memoria y el log dice qué sale | Rubén | Samy |
| Partición y reconexión | Dentro de `STALE_LIMIT` se sirve, fuera se rechaza, y al volver el origen la revalidación actualiza | Rubén | Samy |
| Borde caído | Un borde no responde y el pedido se resuelve por otro | Samy | Rubén |
| Borde reinicia | Qué conserva y qué pierde al volver, según el diseño real del 25 | Samy | Rubén |
| Invalidación perdida | El borde que no recibió el aviso sigue con la copia vieja hasta revalidar o expirar | Samy | Rubén |
| Pedido repetido y dos clientes | El mismo `pedido_id` no corrompe la versión, y dos clientes pueden pedir a la vez | Samy | Rubén |

### Documentos, también repartidos

| Documento | Rubén | Samy |
| --- | --- | --- |
| `docs/comparacion-ray-nativo.md` | Filas de fallo, timeout, recuperación y contenido obsoleto | Apertura y filas de complejidad, mecanismos explícitos, dependencias, arranque y dificultad de depurar |
| `docs/garantias.md` | Qué está garantizado sobre frescura, `STALE_LIMIT` y expulsión, y qué es solo un objetivo de disponibilidad | Qué está garantizado sobre selección, invalidación y duplicados, y qué no |
| `docs/informe.md` | Cómo repetir la campaña en local, con los comandos de sus cuatro fichas | Cómo repetir sus cuatro fichas, y el párrafo que enlaza contrato, diseño y campaña |
| Disclosure de IA | Revisa que lo que él usó esté declarado | Lo deja escrito en el formato de la metodología |

La comparación no tiene que concluir que lo nativo es más rápido. Puede concluir que es más chico porque no incluye planificación ni gestión general de objetos que este problema no necesita. Cada fila dice qué se midió o qué se contó, y qué no.

### Calendario

| Fechas | Rubén | Samy | Cierre del bloque |
| --- | --- | --- | --- |
| sáb 26 dic | Deja el guion de la línea base repetible, escribe la predicción del borde lento y de la caché llena, y deja armada la ficha de lo que ya corrió | Escribe la predicción del borde caído, lo corre y deja armada esa ficha. Anota cómo se mata el proceso | Dos escenarios con ficha empezada. Las predicciones de los demás están escritas antes de observarlos |
| dom 27 dic | Corre borde lento y caché llena, y completa esas dos fichas | Corre reinicio del borde e invalidación perdida, y completa esas dos fichas | Seis fichas con evidencia en `logs/` |
| lun 28 dic | Corre partición, las dos ramas de `STALE_LIMIT` y la reconexión. Cierra esa ficha | Corre el pedido repetido y dos clientes a la vez. Cierra esa ficha. Lee las fichas de Rubén | Las ocho fichas escritas. Si una corrida falló por un defecto, el arreglo queda ese día |
| mar 29 dic | Sus filas de la comparación y sus garantías. Comandos de sus fichas en el informe | Apertura de la comparación, sus filas, sus garantías y el párrafo que une los documentos. Lee lo de Rubén | `docs/comparacion-ray-nativo.md`, `docs/garantias.md` y `docs/informe.md` cerrados en borrador |
| mié 30 dic | Ejecuta los cuatro escenarios de Samy sin leer antes la conclusión, dice qué espera ver y después compara con la ficha | Hace lo mismo con los cuatro de Rubén | Etiqueta interna: fase 3 lista. Si este día no cierra, el 31 se usa para cerrarlo y TLS no empieza |

### Lista del 30 de diciembre

- Las ocho fichas están en `docs/campana/`, con predicción anterior a la corrida y evidencia en logs.
- Las dos ramas de `STALE_LIMIT`, el borde caído, la invalidación perdida y el reinicio se pueden repetir con el informe.
- La comparación y las garantías están leídas por los dos, y cada afirmación dice qué evidencia la sostiene.
- Rubén explica, sin abrir la ficha de Samy, qué pasa si se cae un borde, si se pierde una invalidación y si llega un `pedido_id` repetido.
- Samy explica, sin abrir la ficha de Rubén, qué pasa con un borde lento, con la caché llena y con el origen partido dentro y fuera de `STALE_LIMIT`.
- El informe dice cómo correr la campaña en una máquina local.
- `cifrado` sigue en `false`. El código nuevo respecto al 25 de diciembre son solo correcciones anotadas en la ficha correspondiente.

## TLS, intento del 31 de diciembre al 1 de enero

TLS es un plus. El objetivo es dejarlo listo para la entrega del **1 de enero**, y solo se intenta si lo anterior ya está terminado.

Empieza el 31 de diciembre únicamente si se cumplen las dos condiciones:

1. La lista del 25 de diciembre está verde: el sistema en claro ya hace selección, hit y miss, expulsión, expiración, versiones, invalidación que no llega, revalidación, fallo de un borde y las dos ramas de `STALE_LIMIT`.
2. La lista del 30 de diciembre está verde: las ocho fichas, la comparación, las garantías y el informe ya están en el repo.

Si el 30 de diciembre falta campaña, comparación o informe, el 31 y el 1 de enero se usan para terminar eso. TLS no empieza y `cifrado` se entrega en `false`. Si la fase 3 cierra antes del 30, TLS puede empezar ese mismo día, nunca antes del 25.

La lógica de caché no se entera. Solo cambian `enviar` y `recibir`. El cliente sigue hablando con el borde en claro. El canal cifrado es el de la bajada, la revalidación y la invalidación. No se cifra el historial ni las copias guardadas, y no se escribe un cifrado propio.

### Qué tiene que quedar, si se entra en la ventana

1. Con `cifrado = true`, `enviar` y `recibir` envuelven el mismo TCP con la biblioteca TLS del lenguaje.
2. Hay una autoridad local del proyecto. El origen tiene su certificado y cada borde comprueba que habla con ese origen.
3. Con `cifrado = true` se repiten hit, invalidación perdida, revalidación y las dos ramas de `STALE_LIMIT`. El resultado y el formato del historial son los mismos que en claro.
4. Un fallo de handshake se trata como `origen_no_responde`: el borde aplica la regla de obsoleto y lo anota.

Si esos cuatro puntos cierran el 31 y todavía queda el 1 de enero, cada borde presenta también su certificado y el origen solo acepta a los bordes conocidos. Si no da el tiempo, ese quinto punto no se hace.

### Reparto

| Pieza | Hace | Revisa |
| --- | --- | --- |
| Envolver `enviar` / `recibir` con la biblioteca TLS, sin cambiar el mensaje | Rubén | Samy |
| Fallo de handshake anotado como `origen_no_responde` | Rubén | Samy |
| Autoridad local, certificado del origen, y comprobación en el borde | Samy | Rubén |
| Repetir hit, invalidación perdida, revalidación y `STALE_LIMIT` con `cifrado = true` | Samy | Rubén |
| Entrada en `docs/decisiones.md` y comentario de qué hace el transporte cuando `cifrado` está activo | Quien escribe la pieza | La otra persona |
| Certificados de borde, solo si los cuatro puntos de arriba ya pasan | Samy los emite, Rubén hace que el origen rechace un borde desconocido | Los dos |

### Calendario

| Fechas | Rubén | Samy | Cierre del bloque |
| --- | --- | --- | --- |
| jue 31 dic | Si el 30 quedó verde: `cifrado = true` envuelve el TCP y un handshake fallido queda en el historial. Si el 30 no quedó verde: cierra lo que falte de la fase 3 y no abre TLS | Si el 30 quedó verde: autoridad local y certificado del origen. El borde rechaza a otro origen. Si no: cierra sus fichas o su parte del informe | O TLS ya habla origen y borde, o queda decidido que esta entrega va en claro |
| vie 1 ene | Revisa las cuatro pruebas que repite Samy. Si los cuatro puntos ya pasan y sobra el día, el origen solo acepta bordes conocidos | Repite hit, invalidación perdida, revalidación y `STALE_LIMIT` con `cifrado = true`. Actualiza el párrafo de confianza en `docs/garantias.md` | Checklist de abajo. Entrega del diseño nativo por el canal que indique el profesor |
| sáb 2 ene | Ensayo hablado, sin commits | Ensayo hablado, sin commits | Si TLS entró, cada quien explica el handshake fallido. Si no entró, no se menciona como capacidad |
| dom 3 o lun 4 ene | Defensa | Defensa | Se razona sobre lo entregado el 1 de enero |

### Lista del 1 de enero

Siempre, haya entrado TLS o no:

- La lista del 30 de diciembre sigue verde.
- La entrega no deja `cifrado = true` a medias. O las cuatro pruebas pasan igual que en claro, o la configuración vuelve a `false` y el informe dice en qué paso se detuvo el intento.

Si TLS entró:

- `enviar` y `recibir` son el único sitio que conoce el cifrado, y el comentario de cabecera lo dice.
- `docs/decisiones.md` justifica la biblioteca usada, qué verifica el borde y por qué un handshake fallido equivale a origen inalcanzable.
- Hit, invalidación perdida, revalidación y `STALE_LIMIT` dan el mismo resultado con `cifrado = true`.
- Rubén puede provocar un handshake fallido y decir qué línea queda en el historial. Samy puede decir qué certificado se comprueba y qué no cubre el canal (el cliente, el historial y las copias en disco).
