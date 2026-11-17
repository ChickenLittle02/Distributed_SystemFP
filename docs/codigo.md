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
  registro.py           Historial compartido (registrar)
  origen.py             Actor origen: versiones y responder
  arrancar_origen.py    Arranca Ray y prueba listo + responder
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
