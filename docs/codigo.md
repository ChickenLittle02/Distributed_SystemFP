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
  borde.py              Actor borde: copias con TTL y LRU; hit, miss, pide_origen, revalida, guarda, expulsion
  selector.py           Selector de fuente: en qué orden el cliente prueba los bordes
  cliente.py            Actor cliente: pedido_id, solicitud y respuesta; pasa al otro borde si uno no responde
  arrancar_origen.py    Arranca Ray y prueba listo + responder
  arrancar_borde.py     Arranca Ray, origen y un borde vacío
  arrancar_sistema.py   Arranca origen, dos bordes y cliente; tres pedidos (miss, hit, file_doesnt_exist)
  escenarios.py         Escenarios ttl, lru y selector (F1-S05, S06, S07)
contenido/
  apunte.txt            Archivo de prueba que reparte el origen
  apunte-2.txt          Segundo archivo de prueba, para llenar el borde (F1-S06)
  apunte-3.txt          Tercero: al guardarlo sale el menos usado
logs/                   Historial en disco (no se versiona)
requirements.txt        Dependencias de la fase 1 (Ray)
docs/
  codigo.md             Este mapa
```

## fase1/registro.py

- Qué es: el registro compartido del historial. Es la única función que escribe líneas de operación.
- Dónde: `fase1/registro.py`.
- Qué hace: `registrar(nodo, pedido_id, operacion, **datos)` arma una línea con hora, nodo, `pedido=…`, operación y los pares `clave=valor`, la imprime en consola y la agrega a `logs/<nodo>.log`. Crea `logs/` si no existe.
- Qué no hace: no decide hit, miss, invalidación ni `STALE_LIMIT`. No abre sockets. No guarda el contenido de los archivos repartidos.
- Quién lo usa: el origen (`listo`, `responder`), el borde (`listo`, `miss`, `pide_origen`, `guarda`, `hit`) y el cliente (`listo`, `solicitud`, `respuesta`).
- Tarea: F1-R03.
- Implementa: Rubén. Revisa: Samy (pendiente).

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
- Qué hace: lee `contenido/`, lleva por cada recurso `(version, hash SHA-256)` en `_versiones`, y con `responder(pedido_id, recurso)` entrega los bytes y la versión o `file_doesnt_exist`. Anota `responde` en el historial. Si el hash cambió desde la última vez, la versión sube en 1; si es la primera vez, empieza en 1. Solo acepta nombres de archivo simples (sin rutas ni `..`).
- Qué no hace: no es el borde (no hay hit/miss, TTL, `STALE_LIMIT` ni expulsión). Todavía no invalida bordes (F1-R06) ni tiene la API fina de revalidación (F1-R08); `responder` ya da la versión actual del disco.
- Tareas: F1-R01, F1-R04, F1-R05.
- Implementa: Rubén. Revisa: Samy (pendiente).

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
| Entra | `pedido_id` y `recurso` (nombre del archivo) |
| Sale | Dict: `existe`, `version`, `contenido`, `resultado`. Si existe: `resultado=responde` y los bytes. Si no: `resultado=file_doesnt_exist`, sin bytes |
| Si el otro nodo no contesta | No aplica: solo lee el disco local |

Historial si hay archivo:

```text
origen pedido=prueba-1 responde recurso=apunte.txt version=1
```

Historial si no está:

```text
origen pedido=prueba-2 responde recurso=no-existe.txt resultado=file_doesnt_exist
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
- Implementa: Rubén. Revisa: Samy (pendiente).

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
- Implementa: Samy. Revisa: Rubén (pendiente).

## fase1/borde.py

- Qué es: el actor Ray del borde, la caché cercana al cliente. Es el «borde con caché» de la guía (parte 6, paso 3), con TTL y expulsión.
- Dónde: `fase1/borde.py`, clase `Borde` y dataclass `Copia`.
- Qué hace: lleva `_copias` (recurso → `Copia` con `version`, `contenido`, `guardada_en` y `expira_en`) en un `OrderedDict` en la memoria del actor, en orden de uso (la primera es la menos usada recientemente). `pedir(pedido_id, recurso)`:
  - copia **fresca** (`ahora < expira_en`): anota `hit … estado=fresca`, la mueve al final (uso reciente) y la entrega sin hablar con el origen;
  - sin copia: anota `miss causa=no_esta` y `pide_origen`, llama a `origen.responder`, guarda lo que baja con `_guardar` (anota `guarda` con versión, bytes y `expira`) y responde `miss`;
  - copia **obsoleta** (pasó el TTL): anota `miss causa=expirada` (con versión, hora en que expiró y segundos de obsolescencia) y `pide_origen … version=N`; si el origen confirma la misma versión, `_renovar` reinicia el TTL, anota `revalida … renovo=si expira=…` y luego `hit estado=fresca` (contrato, «Frescura»); si el origen trae otra versión, anota `revalida … renovo=no bajo_otra=si`, guarda la nueva y responde `miss`;
  - si el origen dice que el archivo no existe, borra la copia de ese nombre si la hubiera (contrato) y responde `file_doesnt_exist`.
  `_guardar` aplica la **expulsión LRU**: si el recurso es nuevo y ya hay `capacidad` copias, saca la primera del `OrderedDict` (la menos usada) y anota `expulsion recurso=<sale> version=… politica=LRU entra=<entra>`. Reemplazar una copia que ya estaba no expulsa. `estado()` devuelve recurso → `{version, estado (fresca/obsoleta), expira, edad_obsoleta}` en orden LRU.
- Qué no hace: espera al origen sin límite, sin `origen_no_responde`, `sirve_obsoleta` ni `rechaza` (F1-S09); no aplica `invalidar` (cuando exista F1-R06; la causa `invalidada` del `miss` llega con eso); la revalidación de hoy baja los bytes enteros para saber la versión: el mensaje de revalidación sin bajar el archivo es F1-S08, cuando el origen tenga F1-R08. La caché vive solo en memoria: si el actor muere, arranca vacío.
- Tareas: F1-S01, F1-S03, F1-S04, F1-S05, F1-S06.
- Implementa: Samy. Revisa: Rubén (pendiente).

### Método `listo`

| | |
| --- | --- |
| Entra | Nada |
| Sale | El nombre del nodo (`"borde-1"`) |
| Si el otro nodo no contesta | No aplica |

Deja `listo capacidad=2 politica=LRU ttl=30 stale_limit=60` en `logs/borde-1.log`.

### Método `pedir`

| | |
| --- | --- |
| Entra | `pedido_id` (del cliente) y `recurso` |
| Sale | Dict `resultado` (`hit`, `miss` o `file_doesnt_exist`), `version`, `contenido`, con el formato de `docs/contrato.md` |
| Si el otro nodo no contesta | Hoy espera sin límite; el tiempo de espera y `STALE_LIMIT` llegan con F1-S09 |

Historial de un miss seguido de un hit del mismo recurso (dos `pedido_id`):

```text
19:12:17.170 borde-1 pedido=b5260c miss recurso=apunte.txt causa=no_esta
19:12:17.170 borde-1 pedido=b5260c pide_origen recurso=apunte.txt
19:12:17.176 borde-1 pedido=b5260c guarda recurso=apunte.txt version=1 bytes=50 expira=19:12:20
19:12:17.185 borde-1 pedido=093bc5 hit recurso=apunte.txt version=1 estado=fresca
```

El mismo recurso pedido después de expirar el TTL (corrida con `P20_TTL=3`), con el origen confirmando la misma versión:

```text
19:12:21.218 borde-1 pedido=a593e5 miss recurso=apunte.txt causa=expirada version=1 expiro=19:12:20 edad_segundos=1
19:12:21.219 borde-1 pedido=a593e5 pide_origen recurso=apunte.txt version=1
19:12:21.221 origen  pedido=a593e5 responde recurso=apunte.txt version=1
19:12:21.223 borde-1 pedido=a593e5 revalida recurso=apunte.txt version_local=1 version_origen=1 renovo=si expira=19:12:24
19:12:21.223 borde-1 pedido=a593e5 hit recurso=apunte.txt version=1 estado=fresca
```

Un tercer recurso en un borde de capacidad 2, donde `apunte-2.txt` era la copia menos usada:

```text
19:12:24.104 borde-1 pedido=b5079d miss recurso=apunte-3.txt causa=no_esta
19:12:24.104 borde-1 pedido=b5079d pide_origen recurso=apunte-3.txt
19:12:24.112 borde-1 pedido=b5079d expulsion recurso=apunte-2.txt version=1 politica=LRU entra=apunte-3.txt
19:12:24.112 borde-1 pedido=b5079d guarda recurso=apunte-3.txt version=1 bytes=76 expira=19:12:27
```

`causa` en la línea `miss` dice por qué no se usó la copia: `no_esta` o `expirada`. Con la invalidación llegará `invalidada` y con `STALE_LIMIT`, `supera_limite` (README, «Qué se anota»).

### Método `estado`

| | |
| --- | --- |
| Entra | Nada |
| Sale | Dict recurso → `{version, estado, expira, edad_obsoleta}` en orden LRU (la primera es la próxima en salir). Vacío si no hay copias |
| Si el otro nodo no contesta | No aplica |

## fase1/selector.py

- Qué es: la política de selección de fuente. Una clase sin Ray que vive dentro del proceso del cliente, como dice el contrato («la selección, que vive junto al cliente»). No es un nodo.
- Dónde: `fase1/selector.py`, clase `Selector`.
- Qué hace: `orden()` devuelve los bordes en el orden de preferencia de `Config.bordes`, moviendo al final a los que no respondieron en los últimos `evitar_borde_segundos`. Nunca descarta un borde: si los demás fallan, también se le pregunta. `no_respondio(borde)` anota el momento; `respondio(borde)` le devuelve su lugar.
- Qué no hace: no decide hit, miss ni obsoleto (eso es del borde con su copia). No llama a nadie. El origen no está en su lista: el cliente nunca le habla al origen; es el borde quien baja de ahí.
- Tareas: F1-S07.
- Implementa: Samy. Revisa: Rubén (pendiente).

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
- Implementa: Samy. Revisa: Rubén (pendiente).

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
- Tareas: F1-S01. Implementa: Samy. Revisa: Rubén (pendiente).

## fase1/arrancar_sistema.py

- Qué es: arranque del sistema completo de la fase 1.
- Qué hace: crea origen, `borde-1`, `borde-2` y `cliente` (cuatro procesos), llama a `listo()` de cada uno y hace tres pedidos por el cliente: `apunte.txt` dos veces (el primero es `miss`, el segundo `hit`) y `no-existe.txt` (`file_doesnt_exist`). Al final imprime `estado()` del borde preferido. Se corre con `python3 -m fase1.arrancar_sistema`. El primer pedido deja estas líneas, con el mismo `pedido_id` en los tres nodos:

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

- Qué no hace: no es la corrida del checklist (F1-J06): falta la regla de obsoleto. TTL, expulsión y selector se ven en `fase1/escenarios.py`.
- Tareas: F1-S03, F1-S04. Implementa: Samy. Revisa: Rubén (pendiente).

## fase1/escenarios.py

- Qué es: tres corridas cortas que provocan los comportamientos de F1-S05, S06 y S07 y los dejan en el historial.
- Dónde: `fase1/escenarios.py`. Se corre con `python3 -m fase1.escenarios ttl|lru|selector|todos`. Con `P20_TTL=3` el escenario `ttl` no espera los 30 s provisionales.
- Qué hace:
  - `ttl`: miss, hit fresca, espera `TTL + 1` s, y el tercer pedido anota `miss causa=expirada`, `pide_origen version=1`, `revalida renovo=si` y `hit`. Muestra `estado()` antes y después (fresca → obsoleta → fresca).
  - `lru`: `apunte.txt`, `apunte-2.txt` (borde lleno), `apunte.txt` otra vez (hit, pasa a más usada), `apunte-3.txt` (`expulsion` de `apunte-2.txt`), `apunte-2.txt` otra vez (`miss causa=no_esta`, sale `apunte.txt`).
  - `selector`: un miss por `borde-1`, `ray.kill` de `borde-1`, y el siguiente pedido anota `nodo_caido destino=borde-1` y lo resuelve `borde-2`; el tercero va directo a `borde-2` porque `borde-1` queda evitado `evitar_borde_segundos`.
- Qué no hace: no prueba `timeout` (haría falta un borde lento; eso es la ficha F3-R03), ni partición ni `STALE_LIMIT` (F1-S09, F1-R09). No es la corrida del checklist.
- Tareas: F1-S05, F1-S06, F1-S07. Implementa: Samy. Revisa: Rubén (pendiente).
