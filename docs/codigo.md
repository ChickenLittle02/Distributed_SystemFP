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
  registro.py     Historial compartido (registrar)
contenido/        Archivos que reparte el origen (aún sin origen)
logs/             Historial en disco (no se versiona; lo crea registrar)
docs/
  codigo.md       Este mapa
```

## fase1/registro.py

- Qué es: el registro compartido del historial. Es la única función que escribe líneas de operación.
- Dónde: `fase1/registro.py`.
- Qué hace: `registrar(nodo, pedido_id, operacion, **datos)` arma una línea con hora, nodo, `pedido=…`, operación y los pares `clave=valor`, la imprime en consola y la agrega a `logs/<nodo>.log`. Crea `logs/` si no existe.
- Qué no hace: no decide hit, miss, invalidación ni `STALE_LIMIT`. No abre sockets. No guarda el contenido de los archivos repartidos.
- Quién lo usa: todavía nadie del sistema. El origen, el borde y el cliente tienen que llamar a esta función; no escribir el historial por su cuenta.
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

## contenido/

- Qué es: carpeta local de la que el origen leerá los archivos a repartir.
- Dónde: `contenido/` en la raíz del repositorio.
- Qué hace hoy: solo existe la carpeta (con `.gitkeep` para que Git la conserve vacía). Todavía no hay origen que la lea.
- Regla ya decidida: cada archivo empieza en versión 1; si el contenido cambia, la versión sube en 1; si se borra, el origen responde `file_doesnt_exist`.
- Tarea relacionada: F1-R05 (cuando el origen lea esta carpeta).

## logs/

- Qué es: historial en disco, un archivo por nodo (`origen.log`, `borde-1.log`, …).
- Dónde: `logs/` en la raíz. No se versiona (está en `.gitignore`).
- Quién lo crea: `registrar`, al escribir la primera línea.
