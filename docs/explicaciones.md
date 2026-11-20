# Explicaciones de la fase 1

Notas para poder decir, con palabras propias, cómo arranca el prototipo Ray,
por qué el selector no es un nodo, y qué significan hit, miss, timeout y
`STALE_LIMIT`. La revisión de F1-S01, F1-S03 y F1-S04 (Rubén, 19 nov) usa
este texto.

## Iniciar Ray, crear el origen y levantar un borde

Iniciar Ray, crear el origen y levantar el borde son tres procesos distintos.
El script `fase1/arrancar_borde.py` solo los pide; no es ni el origen ni el borde.

```python
cfg = Config.desde_entorno()
ray.init(ignore_reinit_error=True)
origen = Origen.remote()
borde = Borde.remote("borde-1", origen, cfg)
print(f"origen listo: {ray.get(origen.listo.remote())}", flush=True)
print(f"borde listo: {ray.get(borde.listo.remote())}", flush=True)
print(f"copias en el borde: {ray.get(borde.estado.remote())}", flush=True)
ray.shutdown()
```

### Iniciar Ray

`ray.init()` arranca, en esta máquina, el runtime de Ray: el registro de actores,
el planificador y el almacén de objetos donde viajan los resultados. El proceso
del script pasa a ser el conductor. Hasta que eso existe, `Origen.remote()` no
tiene dónde ejecutarse. `ray.shutdown()` al final apaga ese runtime y mata a
los actores.

### Crear el origen

`@ray.remote` sobre la clase `Origen` no construye el objeto en el script.
`Origen.remote()` le pide a Ray un proceso nuevo (un worker), importa
`fase1.origen` ahí y llama a `__init__`. Ese constructor deja el origen vacío
de verdad: nombre `"origen"`, `_versiones` vacío y `_bordes` vacío. Los
archivos de `contenido/` siguen en disco; el origen todavía no ha leído ninguno.

Lo que vuelve al script no es el objeto. Es un handle: una referencia opaca
con la que Ray sabe a qué proceso mandar la siguiente llamada. El script no
puede leer `_versiones`. Solo puede hacer `origen.listo.remote()`.

### Levantar el borde

`Borde.remote("borde-1", origen, cfg)` pide un segundo worker. Ray serializa
los tres argumentos y los entrega en ese proceso:

- `"borde-1"` es el nombre del nodo.
- `cfg` es una copia de la configuración (TTL, capacidad, `STALE_LIMIT`).
- `origen` es el mismo handle, no una copia de la memoria del origen. Por eso,
  más adelante, el borde puede llamar a `responder` y la llamada llega al
  proceso del origen.

`__init__` del borde guarda ese handle y crea `_copias` como un diccionario
vacío. Eso es «el borde vacío»: cero recursos guardados. `estado()` devuelve
`{}` porque recorre ese diccionario y no hay nada.

### Qué pasa en `listo`

`borde.listo.remote()` no ejecuta `listo` en el script. Deja un mensaje en la
cola de ese actor. El worker del borde lo ejecuta, llama a `registrar` y
escribe una línea en `logs/borde-1.log` (`pedido=arranque`, `listo`, y la
capacidad, la política, el TTL y el límite). El valor de vuelta (`"borde-1"`)
queda en el almacén de objetos. `ray.get` bloquea al script hasta que ese
valor llega y entonces lo imprime. Lo mismo, en el otro proceso, con
`origen.listo()`.

Ray atiende una llamada por actor a la vez y se las entrega en orden. Por eso
el diccionario de copias no necesita cerrojos: nadie más está escribiendo en
ese proceso mientras corre un método.

Al hacer `ray.shutdown()`, esos dos procesos mueren. La memoria del origen y
la del borde desaparecen. La siguiente corrida vuelve a empezar vacía, aunque
`logs/` conserve las líneas de la anterior.

## Worker y handle

El worker es el proceso. El handle es la referencia que usan los demás para
hablar con ese proceso. En el script, `origen` y `borde` son handles; cada uno
apunta a su propio worker.

### Worker

Un worker es un proceso del sistema operativo que Ray arranca para hospedar un
actor. Ahí vive el objeto de verdad: su `__init__` y sus atributos
(`_versiones` en el origen, `_copias` en el borde). Cuando se llama `listo` o
`pedir`, el método corre dentro de ese proceso, no en el script.

En `python3 -m fase1.arrancar_borde` hay tres procesos del proyecto, más los
del propio Ray:

- El script, que solo pide y espera.
- Un worker con el objeto `Origen`.
- Otro worker con el objeto `Borde`.

No comparten memoria. Si el worker del borde muere, `_copias` desaparece y el
siguiente arranque vuelve vacío.

### Handle

Un handle es lo que devuelve `.remote()`. No es el objeto. Es una referencia
opaca: Ray sabe a qué worker mandar la siguiente llamada, y quien la tiene no
puede leer `_versiones` ni `_copias`.

`Origen.remote()` le pide a Ray el worker, construye el `Origen` ahí y
devuelve el handle. La variable `origen` del script es ese handle.
`origen.listo.remote()` deja el mensaje en la cola de ese worker; `ray.get`
espera el resultado.

Lo mismo con `borde`: la variable del script es el handle del segundo worker.

### Qué es cada nombre

| Nombre en el código | Qué es |
| --- | --- |
| La variable `origen` en el script | Un handle |
| El objeto `Origen` (`self` dentro de `listo`, `responder`) | El actor, dentro de su worker |
| La variable `borde` en el script | Otro handle |
| El objeto `Borde` (`self._copias`) | El actor, dentro de otro worker |
| `self.origen` dentro del borde | El mismo handle del origen, copiado a ese proceso para poder llamar a `responder` |

El borde no recibe una copia del origen. Recibe el handle, y por eso una
llamada suya llega al worker del origen.

## El selector no es un quinto actor

El selector es la política con la que el cliente elige a qué borde pedirle
el archivo. Vive en `fase1/selector.py`, como un objeto normal dentro del
proceso del cliente. No tiene `@ray.remote`, no tiene worker y no tiene
handle.

`Cliente.__init__` lo crea así:

```python
self.selector = Selector([b for b in config.bordes if b in bordes],
                         config.evitar_borde_segundos)
```

La lista de preferencia sale de `Config.bordes`: primero `borde-1`, después
`borde-2`. `evitar_borde_segundos` (10 s por defecto) es cuánto tiempo un
borde que no contestó deja de ser el primero.

### Cómo ordena

`orden()` parte la lista en dos y las concatena. Los que están bien van
delante, en el orden fijo. Los que no contestaron hace menos de
`evitar_segundos` van al final. Nunca se borra un borde de la lista: si el
otro también falla, se le vuelve a preguntar al que estaba al final.

El cliente, en `pedir`, recorre ese orden. Por cada nombre anota `solicitud`
y llama a `borde.pedir`. Según lo que pase, le avisa al selector:

- No contestó (`timeout` o `nodo_caido`): `no_respondio(borde)`. El selector
  guarda «hasta cuándo» (`ahora + evitar_segundos`). En los pedidos
  siguientes ese borde sale al final.
- Contestó, aunque la respuesta sea `rechaza`: `respondio(borde)`. Se le
  quita la marca y recupera su lugar en la lista. Un `rechaza` significa que
  el borde sí habló; el cliente igual prueba el siguiente borde de este
  mismo pedido, porque el rechazo de un borde no es el rechazo final.

El selector no llama a nadie. Solo devuelve nombres. Quien llama es el
cliente, con el handle que ya tiene de cada borde.

Tampoco decide hit, miss ni obsoleto. Eso lo decide cada borde mirando su
copia. El origen no está en la lista: el cliente nunca le habla.

### Por qué no es un quinto actor

Los nodos del sistema son cuatro: origen, `borde-1`, `borde-2` y cliente.
Cada uno es un actor porque tiene estado propio y habla con los otros por
la red de Ray. El selector no tiene nada de eso.

Es una lista y un diccionario de plazos, usados por un solo proceso. Si
fuera un actor, el cliente tendría que hacer `selector.orden.remote()` y
`ray.get` antes de cada pedido: un proceso de más, un fallo de más, y un
componente que el README no pide. La decisión del 17 nov lo deja escrito:
un selector como nodo aparte sería un componente inventado solo para la
fase 1. El contrato dice que la selección vive junto al cliente.

Por eso en el diagrama el selector aparece dentro del proceso del cliente,
y en la tabla de «qué pone Ray» esa fila dice «nada».

## Hit, miss, timeout y STALE_LIMIT

Los cuatro nombres salen en el historial. Hit y miss los decide el borde
mirando su copia. Timeout lo anota quien estaba esperando una llamada de
Ray. `STALE_LIMIT` solo entra cuando el origen no contesta.

### Hit

Hit significa que el borde entregó una copia que ya tenía y que podía
servir. En `fase1/borde.py`, `pedir` entra por ahí cuando la copia está
fresca y no está invalidada (`copia.usable`). No llama al origen. Anota
`hit recurso=… version=… estado=fresca` y devuelve la versión y los bytes.

El segundo pedido de `apunte.txt` en `python3 -m fase1.arrancar_sistema`
es un hit. En `logs/origen.log` no aparece ese `pedido_id`.

También hay hit después de una revalidación: la copia ya había expirado, el
origen confirma la misma versión (`misma=si`, sin bytes), el borde renueva
el TTL y anota `revalida renovo=si` y después `hit`. El cliente ve
`resultado=hit` en los dos casos.

### Miss

Miss significa que el borde no pudo servir la copia que tenía, así que tuvo
que hablar con el origen y el archivo viajó. La línea `miss` lleva la causa:

- `no_esta`: no había copia de ese nombre. Es el primer pedido de
  `apunte.txt`. Sigue `pide_origen`, el origen responde, el borde anota
  `guarda` y el cliente ve `resultado=miss`.
- `expirada`: había copia, pero ya pasó `expira_en`. La línea lleva la
  versión, la hora en que expiró y `edad_segundos`.
- `invalidada`: el origen avisó que esa versión ya no vale. La copia sigue
  guardada, marcada, y no se devuelve.

Si el origen entrega otra versión, el borde guarda la nueva y el cliente
también ve `miss`. Si el origen dice que el archivo no existe, el resultado
no es miss: es `file_doesnt_exist`, sin versión y sin bytes.

### Timeout

Timeout significa que una llamada de Ray no volvió dentro de
`timeout_segundos` (2 s en `Config`). Quien esperaba anota
`timeout destino=<nodo> segundos=2.0` y trata a ese nodo como «no responde».

Hay dos sitios:

- El cliente espera a un borde (`cliente._llamar_borde`). Si vence, anota
  `timeout destino=borde-1` y el selector prueba el siguiente borde.
- El borde espera al origen (`borde._hablar_con_origen`). Si vence, anota
  `timeout destino=origen` y aplica `STALE_LIMIT`.

La partición simulada escribe la misma línea con `causa=particion`, y no
espera los 2 s: el borde ni llama. Si el actor al que se llamó ya murió, la
línea no es `timeout`: es `nodo_caido`, porque Ray lanza `RayActorError` sin
llegar al plazo.

### STALE_LIMIT

`STALE_LIMIT` es cuántos segundos puede llevar una copia ya obsoleta y aun
así servirse cuando el origen no contesta. No cuenta desde que se guardó.
Cuenta desde `expira_en`. Con el TTL provisional de 30 s y el límite
provisional de 60 s, una copia es servible hasta 90 s después de guardada
si el origen calla: 30 fresca y 60 obsoleta.

Solo se mira en `_sin_origen`, después de un timeout, de un `nodo_caido` o
de la partición. El borde anota `origen_no_responde` con la edad y el límite:

- edad menor o igual que `STALE_LIMIT`: `sirve_obsoleta`. El cliente recibe
  la versión vieja y el resultado dice que es obsoleta.
- edad mayor: `rechaza causa=supera_limite`. La copia no se borra.
- no hay copia: `rechaza causa=no_esta`.
- la copia está invalidada: `rechaza causa=invalidada`, aunque la edad sea 0.
  El límite no habilita una copia que el origen mandó quitar.

El número de la entrega sigue en 60 s. La corrida del experimento usa
`P20_STALE_LIMIT=4` solo para no esperar.
