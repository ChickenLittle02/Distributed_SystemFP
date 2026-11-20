# Código del repositorio

Mapa de lo que hay escrito: qué es, dónde está y qué hace. Quien implementa una pieza actualiza esta página en la misma sentada. Si el código cambió y esta página no, la tarea sigue abierta.

Los comentarios dentro de cada archivo siguen siendo obligatorios. Esta página no los sustituye: es el índice para saber qué hay y dónde mirar.

## Cómo se mantiene

- Archivo nuevo: se agrega una entrada aquí el mismo día.
- Función o comportamiento nuevo en un archivo que ya existía: se actualiza la entrada de ese archivo.
- Pieza borrada o renombrada: se actualiza o se quita la entrada.
- La justificación de diseño sigue en `docs/decisiones.md`. El contrato visible sigue en `docs/contrato.md`.

## Árbol actual

```text
fase1/
  __init__.py           Paquete del prototipo Ray
  config.py             Números y listas de la corrida (TTL, STALE_LIMIT, bordes...)
  registro.py           Historial compartido (registrar)
  origen.py             Actor origen: versiones y responder
  borde.py              Actor borde: copias con TTL y LRU; hit, miss, revalida, guarda, expulsion, invalidada marcada, STALE_LIMIT
  selector.py           Selector de fuente: en qué orden el cliente prueba los bordes
  cliente.py            Actor cliente: pedido_id, solicitud y respuesta; pasa al otro borde si uno no responde
  arrancar_origen.py    Arranca Ray y prueba listo + responder
  arrancar_borde.py     Arranca Ray, origen y un borde vacío
  arrancar_sistema.py   Arranca origen, dos bordes y cliente; tres pedidos (miss, hit, file_doesnt_exist)
  escenarios.py         Escenarios ttl, lru, selector, invalidar, perdida, revalidar, obsoleto, invalidada, origen_caido
  checklist.py          Corrida repetible del checklist: los diez comportamientos comprobados en logs/ (F1-J06)
contenido/
  apunte.txt            Archivo de prueba que reparte el origen
  apunte-2.txt          Segundo archivo de prueba, para llenar el borde (F1-S06)
  apunte-3.txt          Tercero: al guardarlo sale el menos usado
logs/                   Historial en disco (no se versiona)
requirements.txt        Dependencias de la fase 1 (Ray)
docs/
  codigo.md             Este mapa
  contrato.md           Lo visible desde fuera (Rubén)
  decisiones.md         Decisiones de diseño, con revisión
  diagrama.md           Procesos y qué pone Ray (F1-S02)
  experimento-fase1.md  Ficha del experimento: partición y STALE_LIMIT (F1-S10)
  salida-fase1.md       Las cinco respuestas de la compuerta (F1-R10)
  mapa-ray.md           Qué resuelve Ray hoy y qué será explícito en la fase 2 (F1-S11)
```

## fase1/registro.py

- Qué es: el registro compartido del historial. Es la única función que escribe líneas de operación.
- Dónde: `fase1/registro.py`.
- Qué hace: `registrar(nodo, pedido_id, operacion, **datos)` arma una línea con hora, nodo, `pedido=…`, operación y los pares `clave=valor`, la imprime en consola y la agrega a `logs/<nodo>.log`. Crea `logs/` si no existe.
- Qué no hace: no decide hit, miss, invalidación ni `STALE_LIMIT`. No abre sockets. No guarda el contenido de los archivos repartidos.
- Quién lo usa: el origen (`listo`, `responder`, `invalidar`), el borde (`listo`, `miss`, `pide_origen`, `guarda`, `hit`, `invalidacion_recibida`, `invalidacion_perdida`) y el cliente (`listo`, `solicitud`, `respuesta`).
- Tarea: F1-R03.
- Implementa: Rubén. Revisa: Samy (19 nov).

### Función `registrar`

| | |
| --- | --- |
| Entra | `nodo` (nombre del proceso), `pedido_id`, `operacion`, y datos opcionales (`recurso`, `version`, `causa`, …) |
| Sale | La línea escrita, sin el salto final |
| Si el otro nodo no contesta | No aplica: esta función no habla con otros nodos; solo anota |

Formato de una línea (igual que el README):

```text
23:41:41.880 origen pedido=7d2 responde recurso=apunte.pdf version=1
```

## fase1/origen.py

- Qué es: el actor Ray del origen, dueño de la versión de referencia.
- Dónde: `fase1/origen.py`.
- Qué hace: lee `contenido/`, lleva por cada recurso `(version, hash SHA-256)` en `_versiones`, y con `responder(pedido_id, recurso, version_local=None)` entrega los bytes y la versión o `file_doesnt_exist`. Si `version_local` coincide con la versión del disco, no manda bytes: `misma=si`. Si no coincide, manda el archivo y anota `misma=no`. Sin `version_local` el pedido es una bajada normal. Anota `responde` en el historial. Si el hash cambió desde la última vez, la versión sube en 1; si es la primera vez, empieza en 1. Solo acepta nombres de archivo simples (sin rutas ni `..`). El arranque le pasa los bordes con `anotar_bordes`. `invalidar(pedido_id, recurso)` vuelve a leer el disco, deja la versión de referencia al día y llama a `invalidar` de cada borde anotado. La línea `invalidar` lleva el recurso, la versión nueva y `bordes=` con los que contestaron, en orden. Un borde muerto no entra en esa lista.
- Qué no hace: no es el borde (no hay hit/miss, TTL, `STALE_LIMIT` ni expulsión) y no borra las copias. La línea `invalidacion_perdida` la escribe el borde que no aplicó el aviso, no el origen. El aviso espera sin timeout. Un actor ya muerto no deja esa línea.
- Tareas: F1-R01, F1-R04, F1-R05, F1-R06, F1-R08.
- Implementa: Rubén. Revisa: Samy (19 nov, R01–R05; R06 y R08 pendientes).

### Método `listo`

| | |
| --- | --- |
| Entra | Nada |
| Sale | El nombre del nodo (`"origen"`) |
| Si el otro nodo no contesta | No aplica |

Operación de prueba del arranque (`pedido=arranque`, `listo`). No está en la tabla del README.

### Método `responder`

| | |
| --- | --- |
| Entra | `pedido_id`, `recurso` y, si el borde revalida, `version_local` (si no viene, se pide el archivo) |
| Sale | Dict: `existe`, `version`, `contenido`, `resultado` y, si vino `version_local`, `misma`. Si coincide: `misma=true` y sin bytes. Si no: los bytes. Si no está: `file_doesnt_exist`, sin bytes |
| Si el otro nodo no contesta | No aplica: solo lee el disco local |

Historial de una bajada:

```text
origen pedido=prueba-1 responde recurso=apunte.txt version=1
```

Historial si la versión local coincide (no viajan bytes):

```text
origen pedido=rev-2 responde recurso=apunte-rev.txt version=1 misma=si
```

Historial si no está:

```text
origen pedido=prueba-2 responde recurso=no-existe.txt resultado=file_doesnt_exist
```

### Método `anotar_bordes`

| | |
| --- | --- |
| Entra | Dict nombre del borde → handle del actor |
| Sale | Los nombres anotados, en ese orden |
| Si el otro nodo no contesta | No aplica: solo guarda los handles |

Sin esta lista, `invalidar` deja `bordes=ninguno`. El arranque de `arrancar_sistema.py` y de `escenarios.py` la llena con `borde-1` y `borde-2`.

### Método `invalidar`

| | |
| --- | --- |
| Entra | `pedido_id` y `recurso` |
| Sale | Dict: `recurso`, `version` (o `None`), `bordes` (nombres que contestaron) y `resultado` (`invalidar` o `file_doesnt_exist`) |
| Si el otro nodo no contesta | Ese borde no entra en `bordes`. Si sigue vivo y no aplica el aviso, él escribe `invalidacion_perdida`. Si el actor murió, no hay esa línea |

Historial cuando los dos bordes contestan y el archivo cambió:

```text
origen pedido=inv-1 invalidar recurso=apunte-inv.txt version=2 bordes=borde-1,borde-2
```

## fase1/arrancar_origen.py

- Qué es: script de arranque y prueba del origen.
- Dónde: `fase1/arrancar_origen.py`.
- Qué hace: `ray.init()`, crea `Origen.remote()`, llama a `listo()`, pide `apunte.txt` y un recurso que no existe, y apaga Ray.
- Qué no hace: no levanta bordes ni cliente.
- Cómo se corre, desde la raíz del repositorio:

```text
python3 -m fase1.arrancar_origen
```

- Tareas: F1-R01, F1-R04, F1-R05.
- Implementa: Rubén. Revisa: Samy (19 nov).

## contenido/

- Qué es: carpeta local de la que el origen lee los archivos a repartir.
- Dónde: `contenido/` en la raíz del repositorio.
- Qué hay hoy: `apunte.txt`, archivo de prueba. El origen lo sirve en versión 1 hasta que cambien sus bytes. Desde el 19 nov también `apunte-2.txt` y `apunte-3.txt`, para que el escenario LRU llene un borde de capacidad 2 (F1-S06).
- Regla: cada archivo empieza en versión 1; si el hash SHA-256 del contenido cambia, la versión sube en 1; si se borra, `responder` devuelve `file_doesnt_exist`.
- Tarea: F1-R05.

## logs/

- Qué es: historial en disco, un archivo por nodo (`origen.log`, …).
- Dónde: `logs/` en la raíz. No se versiona (está en `.gitignore`).
- Quién lo crea: `registrar`.

## requirements.txt

- Qué es: dependencias Python de la fase 1.
- Dónde: `requirements.txt` en la raíz.
- Qué hace hoy: declara `ray`. Instalar con `pip install -r requirements.txt`.

## fase1/config.py

- Qué es: la configuración de la corrida, en un solo sitio.
- Dónde: `fase1/config.py`, clase `Config`.
- Qué hace: guarda `ttl_segundos` (30), `stale_limit_segundos` (60), `capacidad` (2), `expulsion` (`LRU`), `timeout_segundos` (2), `evitar_borde_segundos` (10: cuánto deja el selector al final a un borde que no respondió), `cifrado` (`False`) y `bordes` (`["borde-1", "borde-2"]`, orden de preferencia). `Config.desde_entorno()` deja cambiar los cinco números con `P20_TTL`, `P20_STALE_LIMIT`, `P20_CAPACIDAD`, `P20_TIMEOUT` y `P20_EVITAR_BORDE` para acortar una prueba. Lleva la frase de la política de selección como comentario.
- Qué no hace: no decide nada; borde, selector y cliente leen de aquí.
- Tareas: F1-S03, F1-S07 (y la usan S05, S06, S09).
- Implementa: Samy. Revisa: Rubén (20 nov, S03 y S07).

## fase1/borde.py

- Qué es: el actor Ray del borde, la caché cercana al cliente. Es el «borde con caché» de la guía (parte 6, paso 3), con TTL, expulsión, invalidación y la regla de contenido obsoleto.
- Dónde: `fase1/borde.py`, clase `Borde` y dataclass `Copia`.
- Qué hace: lleva `_copias` (recurso → `Copia` con `version`, `contenido`, `guardada_en`, `expira_en` e `invalidada`) en un `OrderedDict` en la memoria del actor, en orden de uso (la primera es la menos usada recientemente). `pedir(pedido_id, recurso)`:
  - copia **usable** (fresca y no invalidada): anota `hit … estado=fresca`, la mueve al final y la entrega sin hablar con el origen;
  - si no, anota `miss` con su causa: `no_esta`, `expirada` (con versión, hora de expiración y segundos obsoleta) o `invalidada` (con versión), y `pide_origen` (con `version=N` si había copia);
  - llama al origen con `_hablar_con_origen`: `ray.wait(timeout=timeout_segundos)`. Si la copia solo expiró, manda `version_local=copia.version` (revalidación, F1-S08); si está invalidada o no hay copia, pide el archivo entero. Si no vuelve a tiempo anota `timeout destino=origen`; si el actor murió, `nodo_caido destino=origen`; si la partición simulada está activa, `timeout destino=origen causa=particion` sin llamar;
  - **el origen contestó** (`_con_respuesta_del_origen`): no existe → `borra` (si había copia) y `file_doesnt_exist`; copia expirada y `misma=True` (sin bytes) → `_renovar` (TTL de nuevo), `revalida … renovo=si`, `hit`; otra versión, o copia invalidada → `revalida … renovo=no` (con `bajo_otra=si` solo si el número cambió), `_guardar`, `miss`. Una copia invalidada nunca se renueva como `hit`: lo que mande el origen la reemplaza;
  - **el origen no contestó** (`_sin_origen`): anota `origen_no_responde recurso=… version=… edad_segundos=… stale_limit=…` (la edad es el tiempo desde `expira_en`). Sin copia → `rechaza causa=no_esta`; invalidada → `rechaza causa=invalidada`; `edad <= STALE_LIMIT` → `sirve_obsoleta`; si la supera → `rechaza causa=supera_limite`. La copia nunca se borra aquí.
  `invalidar(pedido_id, recurso, version)` marca la copia (`invalidada=True`, no la borra) y anota `invalidacion_recibida … version_local=… version=… habia_copia=si|no`; con `perder_avisos(True)` no la marca, anota `invalidacion_perdida` y devuelve `None` (F1-R07). `particion(True|False)` corta o repara el camino al origen y anota `particion con=origen estado=cortada|reparada`. `_guardar` aplica la **expulsión LRU**: si el recurso es nuevo y ya hay `capacidad` copias, saca la primera y anota `expulsion recurso=<sale> version=… politica=LRU entra=<entra>`; LRU no mira el estado. `estado()` devuelve recurso → `{version, estado (fresca/obsoleta/invalidada), expira, edad_obsoleta}` en orden LRU.
- Qué no hace: no reintenta la llamada al origen. La partición es un interruptor, no un corte de red. La caché vive solo en memoria: si el actor muere, arranca vacío. No decide a quién avisar (eso es el origen) ni elige entre bordes (eso es el selector).
- Tareas: F1-S01, F1-S03, F1-S04, F1-S05, F1-S06, F1-S08, F1-S09. `invalidar` aplica F1-R06 (marca, no borra; Rubén); `perder_avisos` e `invalidacion_perdida` son F1-R07 (Rubén).
- Implementa: Samy. Revisa: Rubén (pendiente).

### Método `listo`

| | |
| --- | --- |
| Entra | Nada |
| Sale | El nombre del nodo (`"borde-1"`) |
| Si el otro nodo no contesta | No aplica |

Deja `listo capacidad=2 politica=LRU ttl=30 stale_limit=60 timeout=2.0` en `logs/borde-1.log`.

### Método `pedir`

| | |
| --- | --- |
| Entra | `pedido_id` (del cliente) y `recurso` |
| Sale | Dict `resultado` (`hit`, `miss`, `sirve_obsoleta`, `rechaza` o `file_doesnt_exist`), `version`, `contenido`, con el formato de `docs/contrato.md`; `rechaza` y `file_doesnt_exist` sin versión ni bytes |
| Si el otro nodo no contesta | `timeout`, `nodo_caido` o `timeout causa=particion`, luego `origen_no_responde` y la regla: `sirve_obsoleta` o `rechaza` |

Un miss seguido de un hit del mismo recurso (dos `pedido_id`):

```text
19:12:17.170 borde-1 pedido=b5260c miss recurso=apunte.txt causa=no_esta
19:12:17.170 borde-1 pedido=b5260c pide_origen recurso=apunte.txt
19:12:17.176 borde-1 pedido=b5260c guarda recurso=apunte.txt version=1 bytes=50 expira=19:12:20
19:12:17.185 borde-1 pedido=093bc5 hit recurso=apunte.txt version=1 estado=fresca
```

El mismo recurso después de expirar el TTL, con el origen confirmando la misma versión sin mandar bytes (F1-S08 + F1-R08):

```text
21:47:59.316 borde-1 pedido=563d2d miss recurso=apunte.txt causa=expirada version=1 expiro=21:47:58 edad_segundos=1
21:47:59.316 borde-1 pedido=563d2d pide_origen recurso=apunte.txt version=1
21:47:59.318 origen  pedido=563d2d responde recurso=apunte.txt version=1 misma=si
21:47:59.319 borde-1 pedido=563d2d revalida recurso=apunte.txt version_local=1 version_origen=1 renovo=si expira=21:48:02
21:47:59.319 borde-1 pedido=563d2d hit recurso=apunte.txt version=1 estado=fresca
```

Un tercer recurso en un borde de capacidad 2, donde `apunte-2.txt` era la copia menos usada:

```text
19:12:24.104 borde-1 pedido=b5079d miss recurso=apunte-3.txt causa=no_esta
19:12:24.104 borde-1 pedido=b5079d pide_origen recurso=apunte-3.txt
19:12:24.112 borde-1 pedido=b5079d expulsion recurso=apunte-2.txt version=1 politica=LRU entra=apunte-3.txt
19:12:24.112 borde-1 pedido=b5079d guarda recurso=apunte-3.txt version=1 bytes=76 expira=19:12:27
```

Copia obsoleta 1 s con el origen partido (`STALE_LIMIT=4`), y la misma copia 6 s después:

```text
21:36:14.090 borde-1 pedido=11b12d miss recurso=apunte.txt causa=expirada version=1 expiro=21:36:13 edad_segundos=1
21:36:14.090 borde-1 pedido=11b12d pide_origen recurso=apunte.txt version=1
21:36:14.090 borde-1 pedido=11b12d timeout destino=origen causa=particion segundos=2.0
21:36:14.090 borde-1 pedido=11b12d origen_no_responde recurso=apunte.txt version=1 edad_segundos=1 stale_limit=4
21:36:14.090 borde-1 pedido=11b12d sirve_obsoleta recurso=apunte.txt version=1 edad_segundos=1 stale_limit=4
21:36:19.123 borde-1 pedido=90bd3e origen_no_responde recurso=apunte.txt version=1 edad_segundos=6 stale_limit=4
21:36:19.123 borde-1 pedido=90bd3e rechaza recurso=apunte.txt causa=supera_limite version=1 edad_segundos=6 stale_limit=4
```

`causa` en la línea `miss` dice por qué no se usó la copia: `no_esta`, `expirada` o `invalidada`. `causa` en `rechaza`: `no_esta`, `invalidada` o `supera_limite` (README, «Qué se anota»).

### Método `invalidar`

| | |
| --- | --- |
| Entra | `pedido_id`, `recurso` y `version` de referencia (`None` si el archivo ya no está) |
| Sale | El nombre del borde si aplicó el aviso, o `None` si no lo aplicó |
| Si el otro nodo no contesta | No aplica: esta llamada es el aviso que llega. Con `perder_avisos`, no marca la copia |

```text
21:36:21.878 borde-1 pedido=inv-3 invalidacion_recibida recurso=apunte-inv.txt version_local=1 version=2 habia_copia=si
21:36:21.901 borde-1 pedido=2edb00 miss recurso=apunte-inv.txt causa=invalidada version=1
21:36:21.901 borde-1 pedido=2edb00 rechaza recurso=apunte-inv.txt causa=invalidada version=1
borde-2 pedido=inv-2 invalidacion_perdida recurso=apunte-inv.txt version_local=1 version=2
```

### Método `perder_avisos`

| | |
| --- | --- |
| Entra | `True` para no aplicar los avisos, `False` para volver a aplicarlos |
| Sale | El valor que quedó guardado |
| Si el otro nodo no contesta | No aplica: no llama a nadie |

Es la simulación de F1-R07. Ray entrega la llamada si el actor vive; este interruptor hace que el borde no la aplique. La copia se queda sin marcar y, si sigue fresca, el siguiente pedido es `hit`.

### Método `particion`

| | |
| --- | --- |
| Entra | `True` para cortar el camino al origen, `False` para repararlo |
| Sale | El estado nuevo |
| Si el otro nodo no contesta | Con el corte activo, el borde no llama al origen y anota `timeout destino=origen causa=particion`; el cliente sigue llegando |

Es la simulación de la partición del README §9 (F1-S09, F1-R09). Deja `particion con=origen estado=cortada|reparada` con `pedido=particion`.

### Método `estado`

| | |
| --- | --- |
| Entra | Nada |
| Sale | Dict recurso → `{version, estado (fresca, obsoleta o invalidada), expira, edad_obsoleta}` en orden LRU (la primera es la próxima en salir). Vacío si no hay copias |
| Si el otro nodo no contesta | No aplica |

## fase1/selector.py

- Qué es: la política de selección de fuente. Una clase sin Ray que vive dentro del proceso del cliente, como dice el contrato («la selección, que vive junto al cliente»). No es un nodo.
- Dónde: `fase1/selector.py`, clase `Selector`.
- Qué hace: `orden()` devuelve los bordes en el orden de preferencia de `Config.bordes`, moviendo al final a los que no respondieron en los últimos `evitar_borde_segundos`. Nunca descarta un borde: si los demás fallan, también se le pregunta. `no_respondio(borde)` anota el momento; `respondio(borde)` le devuelve su lugar.
- Qué no hace: no decide hit, miss ni obsoleto (eso es del borde con su copia). No llama a nadie. El origen no está en su lista: el cliente nunca le habla al origen; es el borde quien baja de ahí.
- Tareas: F1-S07.
- Implementa: Samy. Revisa: Rubén (20 nov).

### Método `orden`

| | |
| --- | --- |
| Entra | Nada |
| Sale | Lista de nombres de borde para este pedido |
| Si el otro nodo no contesta | No aplica; solo ordena |

## fase1/cliente.py

- Qué es: el actor Ray del cliente, en su propio proceso.
- Dónde: `fase1/cliente.py`, clase `Cliente`.
- Qué hace: `pedir(recurso)` crea el `pedido_id` (6 hex) y recorre `selector.orden()`. Por cada borde anota `solicitud recurso=… fuente=<borde>` y lo llama con `ray.wait(timeout=timeout_segundos)`. Si la llamada no vuelve a tiempo anota `timeout destino=<borde>`; si el actor murió anota `nodo_caido destino=<borde>`; en los dos casos avisa al selector y sigue con el siguiente. Si el borde contesta `rechaza`, también prueba el siguiente (contrato). La primera respuesta que entrega (o `file_doesnt_exist`) es la final: anota `respuesta version=… resultado=… fuente=<borde>` y la devuelve con `fuente` y `pedido_id`. Si ningún borde entrega, anota `respuesta resultado=rechaza fuente=ninguna`.
- Qué no hace: no guarda caché, no numera versiones, no aplica `STALE_LIMIT`, no habla con el origen.
- Tareas: F1-S03, F1-S07.
- Implementa: Samy. Revisa: Rubén (20 nov).

### Método `pedir`

| | |
| --- | --- |
| Entra | `recurso`; `pedido_id` opcional (para repetir un pedido en las pruebas) |
| Sale | Dict `resultado`, `version`, `contenido`, `fuente` (`None` si rechaza), `pedido_id` |
| Si el otro nodo no contesta | `timeout` o `nodo_caido` en el historial y pasa al siguiente borde; si ninguno entrega, `rechaza` |

Un pedido con `borde-1` muerto (`ray.kill`), resuelto por `borde-2`; un `pedido_id` puede tener más de una línea `solicitud`:

```text
19:12:27.569 cliente pedido=431915 solicitud recurso=apunte.txt fuente=borde-1
19:12:27.574 cliente pedido=431915 nodo_caido destino=borde-1
19:12:27.574 cliente pedido=431915 solicitud recurso=apunte.txt fuente=borde-2
19:12:27.585 borde-2 pedido=431915 miss recurso=apunte.txt causa=no_esta
19:12:27.585 borde-2 pedido=431915 pide_origen recurso=apunte.txt
19:12:27.591 origen  pedido=431915 responde recurso=apunte.txt version=1
19:12:27.594 borde-2 pedido=431915 guarda recurso=apunte.txt version=1 bytes=50 expira=19:12:30
19:12:27.596 cliente pedido=431915 respuesta version=1 resultado=miss fuente=borde-2
```

## fase1/arrancar_borde.py

- Qué es: script de arranque de F1-S01.
- Qué hace: `ray.init()`, crea `Origen` y `Borde("borde-1")`, llama a `listo()` de los dos y muestra `estado()` vacío. Se corre con `python3 -m fase1.arrancar_borde`.
- Tareas: F1-S01. Implementa: Samy. Revisa: Rubén (19 nov). La explicación del arranque está en `docs/explicaciones.md`.

## fase1/arrancar_sistema.py

- Qué es: arranque del sistema completo de la fase 1.
- Qué hace: crea origen, `borde-1`, `borde-2` y `cliente` (cuatro procesos), le anota los dos bordes al origen (`anotar_bordes`), llama a `listo()` de cada uno y hace tres pedidos por el cliente: `apunte.txt` dos veces (el primero es `miss`, el segundo `hit`) y `no-existe.txt` (`file_doesnt_exist`). Al final imprime `estado()` del borde preferido. Se corre con `python3 -m fase1.arrancar_sistema`. El primer pedido deja estas líneas, con el mismo `pedido_id` en los tres nodos:

```text
09:16:31.899 cliente pedido=410d11 solicitud recurso=apunte.txt fuente=borde-1
09:16:31.904 borde-1 pedido=410d11 miss recurso=apunte.txt causa=no_esta
09:16:31.905 borde-1 pedido=410d11 pide_origen recurso=apunte.txt
09:16:31.909 origen  pedido=410d11 responde recurso=apunte.txt version=1
09:16:31.912 borde-1 pedido=410d11 guarda recurso=apunte.txt version=1 bytes=50 expira=09:17:01
09:16:31.914 cliente pedido=410d11 respuesta version=1 resultado=miss fuente=borde-1
```

El segundo pedido deja solo dos líneas en el borde y el cliente; el origen no interviene:

```text
09:16:31.918 cliente pedido=467a42 solicitud recurso=apunte.txt fuente=borde-1
09:16:31.920 borde-1 pedido=467a42 hit recurso=apunte.txt version=1 estado=fresca
09:16:31.923 cliente pedido=467a42 respuesta version=1 resultado=hit fuente=borde-1
```

- Qué no hace: no es la corrida del checklist (F1-J06). Solo hace miss, hit y `file_doesnt_exist`. TTL, expulsión, selector y la regla de obsoleto se ven en `fase1/escenarios.py`.
- Tareas: F1-S03, F1-S04. Implementa: Samy. Revisa: Rubén (19 nov).

## fase1/escenarios.py

- Qué es: nueve corridas cortas que provocan los comportamientos de F1-S05, S06, S07, S08, S09, F1-R06, R07 y R08 y los dejan en el historial. Entre todas cubren los diez comportamientos del checklist.
- Dónde: `fase1/escenarios.py`. Se corre con `python3 -m fase1.escenarios ttl|lru|selector|invalidar|perdida|revalidar|obsoleto|invalidada|origen_caido|todos`. Con `P20_TTL=3 P20_STALE_LIMIT=4` no se esperan los valores provisionales.
- Qué hace:
  - `ttl`: miss, hit fresca, espera `TTL + 1` s, y el tercer pedido anota `miss causa=expirada`, `pide_origen version=1`, el origen contesta `misma=si` sin bytes, `revalida renovo=si` y `hit`. Muestra `estado()` antes y después (fresca → obsoleta → fresca).
  - `lru`: `apunte.txt`, `apunte-2.txt` (borde lleno), `apunte.txt` otra vez (hit, pasa a más usada), `apunte-3.txt` (`expulsion` de `apunte-2.txt`), `apunte-2.txt` otra vez (`miss causa=no_esta`, sale `apunte.txt`).
  - `selector`: un miss por `borde-1`, `ray.kill` de `borde-1`, y el siguiente pedido anota `nodo_caido destino=borde-1` y lo resuelve `borde-2`; el tercero va directo a `borde-2` porque `borde-1` queda evitado `evitar_borde_segundos`.
  - `invalidar`: los dos bordes guardan `apunte-inv.txt`, el archivo cambia, `origen.invalidar` anota `version=2` y `bordes=borde-1,borde-2`, las dos copias quedan `invalidada` y el pedido siguiente anota `miss causa=invalidada` y baja la versión nueva. El archivo de prueba se borra al terminar.
  - `perdida`: igual, pero `borde-2` tiene `perder_avisos`. Anota `invalidacion_perdida`, no sale en `bordes=`, y un pedido directo sigue en `hit` de la versión 1. El cliente, por `borde-1`, baja la versión 2.
  - `revalidar` (Rubén, F1-R08): `responder` sin `version_local` baja el archivo; con la misma `version_local` anota `misma=si` y no manda bytes; si el archivo cambió, anota `misma=no` y manda la versión nueva.
  - `obsoleto`: `borde-1` guarda, se corta `borde-1→origen` (`particion`), hit mientras está fresca, `sirve_obsoleta` con la copia 1 s obsoleta, `rechaza causa=supera_limite` a los 6 s (el cliente pasa a `borde-2`), y al reparar `revalida renovo=si` + `hit`. Es el experimento de `docs/experimento-fase1.md`.
  - `invalidada`: aviso recibido en los dos bordes y después partición en los dos: `miss causa=invalidada`, `rechaza causa=invalidada`, el cliente rechaza; al reparar, miss de la versión 2.
  - `origen_caido`: `ray.kill` del origen; hit mientras la copia es fresca, y al expirar `nodo_caido destino=origen` + `sirve_obsoleta`.
- Qué no hace: no prueba un `timeout` de verdad (origen o borde lentos; ficha F3-R03). No es la corrida formal del checklist (F1-J06), aunque la cubre.
- Tareas: F1-S05, F1-S06, F1-S07, F1-S08, F1-S09 (Samy; revisa Rubén, pendiente), F1-R06 (`invalidar`), F1-R07 (`perdida`) y F1-R08 (`revalidar`; implementa Rubén, revisa Samy, pendiente).

## fase1/checklist.py

- Qué es: la corrida repetible del checklist de la fase 1 (F1-J06). Corre seguidos `arrancar_sistema` y los escenarios `ttl`, `lru`, `selector`, `invalidar`, `perdida`, `obsoleto` e `invalidada`, lee solo las líneas que esa corrida dejó en `logs/` y comprueba, con una expresión regular por línea esperada, los diez comportamientos del tablero y los cinco resultados del cliente (F1-J05).
- Dónde: `fase1/checklist.py`. Se corre con `python3 -m fase1.checklist` (tarda alrededor de un minuto). Pone `P20_TTL=3` y `P20_STALE_LIMIT=4` si no vienen en el entorno.
- Qué hace: anota una línea `checklist pedido=arranque config cifrado=false ttl=… stale_limit=…` (`logs/checklist.log`), guarda el tamaño de cada log al empezar, corre los pasos, y después imprime una tabla `[x]`/`[ ]` por comportamiento con las líneas que lo prueban (o `FALTA nodo: /patrón/`). Para «`registrar` desde la primera operación» exige que la primera línea nueva de cada nodo sea `listo`. Al final imprime el recorrido de un pedido filtrado por `pedido_id` en los cuatro logs (F1-J02). Termina con código 1 si falta algo.
- Qué no hace: no borra `logs/` ni decide nada del sistema; no prueba `timeout` real ni `origen_caido` (ese escenario existe aparte). No sustituye mirarlo juntos: es lo que se corre en esa sesión.
- Tareas: F1-J06 (y evidencia para F1-J02, F1-J03, F1-J05). Implementa: Samy. Revisa: Rubén (pendiente).

---

# Fase 2 — código nativo (Go)

Módulo `fase2/` (`go.mod`: `github.com/ChickenLittle02/Distributed_SystemFP/fase2`, Go 1.21+). Se corre desde la raíz del repositorio. Pruebas: `cd fase2 && go test ./...`.

```text
fase2/
  go.mod
  config.json             Direcciones y números de la corrida (arranque estático)
  config/config.go        Lee config.json y P20_*
  registro/registro.go    registrar en Go: misma línea, un archivo por nodo
  protocolo/protocolo.go  Cabeceras, resultados y rutas HTTP del proyecto
  transporte/transporte.go  Único sitio que abre conexiones: Enviar con plazo; timeout / nodo_caido
  origen/origen.go        Origen HTTP: GET (+ revalidación 304), PUT, DELETE, versiones persistidas, invalidar
  origen/origen_test.go   Pruebas del origen (F2-S09)
  cliente/selector.go     Selector: orden fijo, el que no respondió va al final
  cliente/cliente.go      Cliente: GET al borde que diga el selector; solicitud / respuesta
  cliente/cliente_test.go Pruebas del cliente y del selector
  cmd/origen/main.go      Programa origen
  cmd/cliente/main.go     Programa cliente (el «cliente automático» de F2-S05)
  cmd/publicar/main.go    Programa de publicación: put / delete contra el origen
  borde/, cmd/borde/      (Rubén, F2-R03–R07)
```

## fase2/config

- Qué es: la configuración de la corrida nativa. `Config` con `Origen`, `Bordes` (nombre + dirección, en orden de preferencia), `TTLSegundos`, `StaleLimitSegundos`, `Capacidad`, `Expulsion`, `TimeoutSegundos`, `EvitarBordeSegundos`, `Cifrado`, `Contenido`, `Logs`.
- Qué hace: `Cargar(ruta)` lee el JSON, aplica `P20_TTL`, `P20_STALE_LIMIT`, `P20_CAPACIDAD`, `P20_TIMEOUT`, `P20_EVITAR_BORDE`, y valida. `Timeout()`, `Esquema()` (`http`; `https` si `cifrado`), `DireccionDe(nombre)`.
- Qué no hace: no decide nada; no descubre nodos. Tareas: F2-J01 (direcciones en configuración). Implementa: Samy. Revisa: Rubén (pendiente).

## fase2/registro

- Qué es: `Registrar(nodo, pedidoID, operacion string, datos ...Dato) string`, con `D(clave, valor)` para los pares, en orden. Escribe en consola (`registro.Consola`, las pruebas la apagan) y en `<logs>/<nodo>.log` (`Configurar(carpeta)`), bajo cerrojo.
- Qué no hace: no decide nada, no abre sockets, no guarda bytes de archivos. Tarea: F2-S01. Implementa: Samy. Revisa: Rubén (pendiente).

## fase2/protocolo

- Qué es: las constantes del formato de mensaje (F2-S02): cabeceras `X-Pedido-Id`, `X-Version`, `X-Version-Local`, `X-Misma`, `X-Resultado`, `X-Fuente`, `X-Bordes-Avisados`, `X-Nodo`; tokens `hit`, `miss`, `sirve_obsoleta`, `rechaza`, `file_doesnt_exist`; `RutaInvalidar = /_invalidar/`. El comentario de cabecera del paquete es el resumen del protocolo; el detalle está en `docs/diseno-nativo.md` §1.
- Tarea: F2-S02. Implementa: Samy. Revisa: Rubén (pendiente).

## fase2/transporte

- Qué es: `Transporte` con `Nuevo(plazo, cifrado)` y `Enviar(destino, método, ruta, cabeceras, cuerpo) (*Respuesta, Fallo, error)`. `Respuesta` trae estado, cabeceras y cuerpo. `Fallo` es `SinFallo`, `Timeout` (`context.DeadlineExceeded`) o `NodoCaido` (cualquier otro error de red); `Fallo.String()` da el token del historial.
- Qué no hace: no reintenta; no interpreta códigos; con `cifrado=true` solo cambiaría el esquema (TLS no entra en esta fase). Es el sitio de F2-R02 (`enviar`/`recibir`), sobre HTTP.
- Implementa: Samy. Revisa: Rubén (pendiente).

### Función `Enviar`

| | |
| --- | --- |
| Entra | `destino` (host:puerto), método, ruta, cabeceras (las vacías no se mandan), cuerpo (nil si no hay) |
| Sale | `Respuesta`, o `Fallo` ≠ `SinFallo` y el error |
| Si el otro nodo no contesta | `Timeout` si venció el plazo; `NodoCaido` si la conexión no abrió o se cortó. No reintenta |

## fase2/origen

- Qué es: el origen nativo, dueño de la versión de referencia.
- Qué hace: `Nuevo(cfg)` crea la carpeta de contenido si falta y lee `contenido/.versiones.json`. `Responder(pedidoID, recurso, versionLocal *int)`: lee el archivo, calcula la versión por hash (sube si cambió, persiste), y devuelve `Existe=false`, o `Misma=true` sin bytes si la versión local coincide, o los bytes; anota `responde … version=N [misma=si|no]` o `responde … resultado=file_doesnt_exist`. `Publicar` escribe el archivo, anota `publica … version=N bytes=…` y llama a `Invalidar`. `Borrar` quita el archivo (conserva la entrada de versión), anota `borra … existia=si|no` y llama a `Invalidar`. `Invalidar` manda `POST /_invalidar/<recurso>` a cada borde con el plazo del transporte, anota `timeout`/`nodo_caido destino=<borde>` por los que no contestan y `invalidar … version=N|resultado=file_doesnt_exist bordes=<lista>|ninguno`. `Manejador()` es el `http.Handler`: `GET` → `200`/`304`/`404`, `PUT` → `200` con `X-Version` y `X-Bordes-Avisados`, `DELETE` → `200`/`404`, otros → `405`; nombres con `/`, `..` o que empiezan por `.` → `400`.
- Qué no hace: no es el borde; no toca copias; no abre el puerto (eso es `cmd/origen`). No reintenta avisos. No hay autenticación.
- Tareas: F2-S04, F2-S06, F2-S07. Implementa: Samy. Revisa: Rubén (pendiente).

### Método `Responder`

| | |
| --- | --- |
| Entra | `pedidoID`, `recurso`, `versionLocal` (nil = bajada normal) |
| Sale | `Respuesta{Existe, Misma, Version, Contenido}` |
| Si el otro nodo no contesta | No aplica: solo lee disco local |

Historial de una revalidación sin bytes y de una publicación con los dos bordes apagados (corrida del 20 nov):

```text
01:54:35.170 origen pedido=e2e-2 responde recurso=apunte.txt version=1 misma=si
01:54:35.560 origen pedido=5a76e7 publica recurso=e2e.txt version=1 bytes=18
01:54:35.560 origen pedido=5a76e7 nodo_caido destino=borde-1 segundos=2
01:54:35.560 origen pedido=5a76e7 nodo_caido destino=borde-2 segundos=2
01:54:35.561 origen pedido=5a76e7 invalidar recurso=e2e.txt version=1 bordes=ninguno
```

### Método `Invalidar`

| | |
| --- | --- |
| Entra | `pedidoID` (el del `PUT`/`DELETE`) y `recurso` |
| Sale | `Aviso{Recurso, Version, Existe, Avisados}` |
| Si el otro nodo no contesta | `timeout` o `nodo_caido destino=<borde>`; ese borde no entra en `bordes=`; se sigue con el siguiente |

### Pruebas (`origen_test.go`, F2-S09)

`TestResponderYRevalidarSinBytes` (200 → 304 → 200 con versión nueva → 404), `TestPublicarInvalidaALosBordes` (PUT igual no sube, PUT distinto sube, aviso con versión, DELETE con `file_doesnt_exist`, tras borrar y volver la versión sigue), `TestAvisoPerdidoYBordeQueNoEsta` (un borde contesta 202, otro no existe: `bordes=borde-1`, `nodo_caido destino=borde-3`, sin bloquear), `TestVersionSobreviveAlReinicio`, `TestNombresPeligrosos`.

## fase2/cliente

- Qué es: el selector (`selector.go`) y el cliente (`cliente.go`).
- Qué hace: `NuevoSelector(bordes, evitar)` con `Orden()`, `NoRespondio(nombre)`, `Respondio(nombre)`: la misma política de la fase 1. `Nuevo(nombre, cfg)` crea el cliente; `Pedir(recurso, pedidoID)` recorre `Orden()`, anota `solicitud … fuente=<borde>`, manda `GET /<recurso>` con `X-Pedido-Id`, anota `timeout`/`nodo_caido destino=<borde>` y pasa al siguiente; si el borde responde `rechaza`, también pasa al siguiente; la primera respuesta que entrega (o `file_doesnt_exist`) es la final: `respuesta [version=N] resultado=… fuente=<borde>`. Si ninguno entrega, `respuesta resultado=rechaza fuente=ninguna`. `NuevoPedidoID()` da 6 hex.
- Qué no hace: no guarda caché, no habla con el origen, no numera versiones.
- Tareas: F2-S05 (cliente automático), F2-S08. Implementa: Samy. Revisa: Rubén (pendiente).

### Método `Pedir`

| | |
| --- | --- |
| Entra | `recurso`, `pedidoID` ("" para crearlo) |
| Sale | `Respuesta{PedidoID, Resultado, Version, Contenido, Fuente}` |
| Si el otro nodo no contesta | `timeout` o `nodo_caido` y siguiente borde; `rechaza` si ninguno entrega |

### Pruebas (`cliente_test.go`)

`TestBordeCaidoYElOtroEntrega` (nodo_caido en borde-1, miss por borde-2; el segundo pedido no vuelve a probar borde-1), `TestRechazaDeUnBordeNoEsFinal` (503 en borde-1, `sirve_obsoleta` por borde-2), `TestTodosRechazanOCaen` (`rechaza fuente=ninguna`), `TestFileDoesntExistSinCuerpo`, `TestSelectorOrden`.

## fase2/cmd/origen, cmd/cliente, cmd/publicar

- `cmd/origen -config fase2/config.json [-escucha host:puerto]`: anota `listo direccion=… bordes=… timeout=… cifrado=false` y sirve.
- `cmd/cliente -config … -recurso apunte.txt [-n 2] [-pedido id] [-nombre cliente] [-guardar archivo]`: uno o varios pedidos; imprime `pedido=… resultado=… version=… fuente=… bytes=…`; sale con 1 si hubo `rechaza` o `file_doesnt_exist`.
- `cmd/publicar -config … put <recurso> <archivo-local>` | `delete <recurso>`: anota `publica`/`borra` y `respuesta estado=… version=… bordes=…` en `logs/publicador.log`; imprime la versión y los bordes avisados.
- Implementa: Samy. Revisa: Rubén (pendiente).
