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
  borde.py              Actor borde: hoy reenvía al origen (esqueleto)
  cliente.py            Actor cliente: pedido_id, solicitud y respuesta (esqueleto)
  arrancar_origen.py    Arranca Ray y prueba listo + responder
  arrancar_borde.py     Arranca Ray, origen y un borde vacío
  arrancar_sistema.py   Arranca origen, dos bordes y cliente, y hace un pedido
contenido/
  apunte.txt            Archivo de prueba que reparte el origen
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
- Quién lo usa: el origen (`listo`, `responder`). Más adelante, borde y cliente.
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
- Qué hay hoy: `apunte.txt`, archivo de prueba. El origen lo sirve en versión 1 hasta que cambien sus bytes.
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
- Qué hace: guarda `ttl_segundos` (30), `stale_limit_segundos` (60), `capacidad` (2), `expulsion` (`LRU`), `timeout_segundos` (2), `cifrado` (`False`) y `bordes` (`["borde-1", "borde-2"]`, orden de preferencia). `Config.desde_entorno()` deja cambiar los cuatro números con `P20_TTL`, `P20_STALE_LIMIT`, `P20_CAPACIDAD` y `P20_TIMEOUT` para acortar una prueba. Lleva la frase de la política de selección como comentario.
- Qué no hace: no decide nada; borde y cliente leen de aquí.
- Tareas: F1-S03 (y la usan S05, S06, S07, S09).
- Implementa: Samy. Revisa: Rubén (pendiente).

## fase1/borde.py

- Qué es: el actor Ray del borde, la caché cercana al cliente. Hoy es un esqueleto: el «borde que reenvía» de la guía (parte 6, paso 2).
- Dónde: `fase1/borde.py`, clase `Borde`.
- Qué hace: `pedir(pedido_id, recurso)` anota `pide_origen`, llama a `origen.responder` y devuelve `miss` con versión y contenido, o `file_doesnt_exist`. `estado()` devuelve las copias (vacío por ahora).
- Qué no hace: no guarda copias, así que no hay `hit` (F1-S04), ni TTL (F1-S05), ni expulsión (F1-S06), ni revalidación (F1-S08), ni `STALE_LIMIT` ni tiempo de espera al origen (F1-S09), ni `invalidar` (lo aplica el borde cuando exista F1-R06).
- Tareas: F1-S01, F1-S03.
- Implementa: Samy. Revisa: Rubén (pendiente).

### Método `listo`

| | |
| --- | --- |
| Entra | Nada |
| Sale | El nombre del nodo (`"borde-1"`) |
| Si el otro nodo no contesta | No aplica |

Deja `listo capacidad=2 ttl=30 stale_limit=60` en `logs/borde-1.log`.

### Método `pedir`

| | |
| --- | --- |
| Entra | `pedido_id` (del cliente) y `recurso` |
| Sale | Dict `resultado`, `version`, `contenido` con el formato de `docs/contrato.md` |
| Si el otro nodo no contesta | Hoy espera sin límite; el tiempo de espera llega con F1-S09 |

Historial de hoy:

```text
borde-1 pedido=f3cb77 pide_origen recurso=apunte.txt
```

## fase1/cliente.py

- Qué es: el actor Ray del cliente, en su propio proceso.
- Dónde: `fase1/cliente.py`, clase `Cliente`.
- Qué hace: `pedir(recurso)` crea el `pedido_id` (6 hex), anota `solicitud recurso=… fuente=borde-1`, llama a `pedir` del primer borde de `Config.bordes` y anota `respuesta version=… resultado=…`. Devuelve el dict del borde más `fuente` y `pedido_id`. Acepta un `pedido_id` dado, para repetir un pedido en las pruebas.
- Qué no hace: no elige entre bordes ni pasa al otro si uno no responde o rechaza (F1-S07). No habla con el origen.
- Tareas: F1-S03.
- Implementa: Samy. Revisa: Rubén (pendiente).

### Método `pedir`

| | |
| --- | --- |
| Entra | `recurso`; `pedido_id` opcional |
| Sale | Dict `resultado`, `version`, `contenido`, `fuente`, `pedido_id` |
| Si el otro nodo no contesta | Hoy espera; el paso a otro borde es F1-S07 |

## fase1/arrancar_borde.py

- Qué es: script de arranque de F1-S01.
- Qué hace: `ray.init()`, crea `Origen` y `Borde("borde-1")`, llama a `listo()` de los dos y muestra `estado()` vacío. Se corre con `python3 -m fase1.arrancar_borde`.
- Tareas: F1-S01. Implementa: Samy. Revisa: Rubén (pendiente).

## fase1/arrancar_sistema.py

- Qué es: arranque del sistema completo de la fase 1.
- Qué hace: crea origen, `borde-1`, `borde-2` y `cliente` (cuatro procesos), llama a `listo()` de cada uno y hace un pedido de `apunte.txt` por el cliente. Se corre con `python3 -m fase1.arrancar_sistema`. Un pedido deja hoy estas cuatro líneas, una por nodo, con el mismo `pedido_id`:

```text
11:29:00.725 cliente pedido=f3cb77 solicitud recurso=apunte.txt fuente=borde-1
11:29:00.728 borde-1 pedido=f3cb77 pide_origen recurso=apunte.txt
11:29:00.732 origen  pedido=f3cb77 responde recurso=apunte.txt version=1
11:29:00.736 cliente pedido=f3cb77 respuesta version=1 resultado=miss fuente=borde-1
```

- Qué no hace: no es la corrida del checklist (F1-J06).
- Tareas: F1-S03. Implementa: Samy. Revisa: Rubén (pendiente).
