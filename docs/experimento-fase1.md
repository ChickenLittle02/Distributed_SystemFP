# Experimento de la fase 1: partición borde→origen y `STALE_LIMIT` (F1-S10)

Un fallo provocado, con la predicción escrita antes de correrlo y la evidencia en `logs/`. Es el experimento que pide la fase 1 (README §9 y §10): un borde que puede atender al cliente pero no puede hablar con el origen, y la política explícita de contenido obsoleto. Se repite con un comando.

## Escenario

- Un origen, dos bordes (`borde-1` preferido, `borde-2`) y un cliente, en cuatro procesos Ray.
- Configuración de la corrida: `TTL = 3 s`, `STALE_LIMIT = 4 s`, `timeout = 2 s`, capacidad 2, LRU. Son los valores provisionales acortados con variables de entorno para no esperar 30 y 60 segundos; la regla es la misma.
- El fallo: se corta el camino `borde-1 → origen` con `particion(True)` en `borde-1`. El camino `cliente → borde-1` sigue abierto, y `borde-2` sigue viendo al origen. Es la figura del README §9: el borde conserva una versión y el cliente le sigue llegando.

```text
python3 -m fase1.escenarios obsoleto        # con P20_TTL=3 P20_STALE_LIMIT=4
```

## Carga

Cinco pedidos del mismo cliente por `apunte.txt`, uno tras otro, con esperas entre medias para cruzar el TTL y después el límite.

## Afirmación que se pone a prueba

Con el origen inalcanzable, el borde sirve su copia obsoleta mientras lleve obsoleta como mucho `STALE_LIMIT`, y la rechaza cuando lo supera; el cliente entonces va al otro borde. Cuando el origen vuelve, la copia que quedó guardada se revalida sin bajar otra vez.

## Predicción (escrita antes de correr)

| Pedido | Momento | Lo que debe pasar |
| --- | --- | --- |
| 1 | t = 0 | `miss causa=no_esta`, baja del origen, `guarda … expira=t+3` |
| corte | t ≈ 0 | `particion con=origen estado=cortada` en `borde-1` |
| 2 | t ≈ 0 | `hit estado=fresca`: la copia es fresca, el borde no toca el origen y no nota el corte |
| espera 4 s | | la copia pasa a obsoleta en t = 3 |
| 3 | t ≈ 4 | `miss causa=expirada edad_segundos=1`, `timeout destino=origen causa=particion`, `origen_no_responde edad_segundos=1 stale_limit=4`, **`sirve_obsoleta`**. El cliente recibe la versión 1 con `resultado=sirve_obsoleta` |
| espera 5 s | | la edad obsoleta pasa de 4 |
| 4 | t ≈ 9 | `miss causa=expirada edad_segundos=6`, `origen_no_responde`, **`rechaza causa=supera_limite`** en `borde-1`. El cliente prueba `borde-2`: `miss causa=no_esta`, baja del origen, `resultado=miss fuente=borde-2`. La copia de `borde-1` sigue guardada |
| reparación | | `particion … estado=reparada` |
| 5 | t ≈ 9 | `borde-1` pregunta al origen, misma versión: `revalida renovo=si`, `hit` |

## Configuración

`fase1/config.py` con `P20_TTL=3 P20_STALE_LIMIT=4`. Todo lo demás por defecto (`timeout_segundos=2`, `capacidad=2`, `expulsion=LRU`, `evitar_borde_segundos=10`, `cifrado=false`).

## Cómo se dispara el fallo

`borde-1.particion(True)`: un interruptor del actor. Con él activo, `_hablar_con_origen` no llama al origen y anota `timeout destino=origen causa=particion`. Es una simulación: Ray entregaría la llamada si la hiciéramos. Se eligió así porque es reproducible en una máquina y no depende de la red; en la fase 2 el corte será de red (proceso matado, puerto cerrado). La diferencia con `origen_caido` (el actor origen muerto con `ray.kill`, línea `nodo_caido`) está en el escenario `python3 -m fase1.escenarios origen_caido`.

## Evidencia recogida

Corrida del 19 nov. Filtrando `logs/*.log` por cada `pedido_id` (las líneas de un mismo milisegundo se muestran en el orden en que las escribió el borde):

Pedido 1, miss y guardado:

```text
21:36:10.050 cliente pedido=fdec90 solicitud recurso=apunte.txt fuente=borde-1
21:36:10.053 borde-1 pedido=fdec90 miss recurso=apunte.txt causa=no_esta
21:36:10.053 borde-1 pedido=fdec90 pide_origen recurso=apunte.txt
21:36:10.055 origen  pedido=fdec90 responde recurso=apunte.txt version=1
21:36:10.057 borde-1 pedido=fdec90 guarda recurso=apunte.txt version=1 bytes=50 expira=21:36:13
21:36:10.058 cliente pedido=fdec90 respuesta version=1 resultado=miss fuente=borde-1
21:36:10.062 borde-1 pedido=particion particion con=origen estado=cortada
```

Pedido 2, copia fresca, el corte no se nota:

```text
21:36:10.065 cliente pedido=94dbc7 solicitud recurso=apunte.txt fuente=borde-1
21:36:10.067 borde-1 pedido=94dbc7 hit recurso=apunte.txt version=1 estado=fresca
21:36:10.068 cliente pedido=94dbc7 respuesta version=1 resultado=hit fuente=borde-1
```

Pedido 3, obsoleta 1 s, dentro del límite:

```text
21:36:14.079 cliente pedido=11b12d solicitud recurso=apunte.txt fuente=borde-1
21:36:14.090 borde-1 pedido=11b12d miss recurso=apunte.txt causa=expirada version=1 expiro=21:36:13 edad_segundos=1
21:36:14.090 borde-1 pedido=11b12d pide_origen recurso=apunte.txt version=1
21:36:14.090 borde-1 pedido=11b12d timeout destino=origen causa=particion segundos=2.0
21:36:14.090 borde-1 pedido=11b12d origen_no_responde recurso=apunte.txt version=1 edad_segundos=1 stale_limit=4
21:36:14.090 borde-1 pedido=11b12d sirve_obsoleta recurso=apunte.txt version=1 edad_segundos=1 stale_limit=4
21:36:14.092 cliente pedido=11b12d respuesta version=1 resultado=sirve_obsoleta fuente=borde-1
```

Pedido 4, obsoleta 6 s, supera el límite; el cliente pasa a `borde-2`:

```text
21:36:19.106 cliente pedido=90bd3e solicitud recurso=apunte.txt fuente=borde-1
21:36:19.122 borde-1 pedido=90bd3e miss recurso=apunte.txt causa=expirada version=1 expiro=21:36:13 edad_segundos=6
21:36:19.123 borde-1 pedido=90bd3e pide_origen recurso=apunte.txt version=1
21:36:19.123 borde-1 pedido=90bd3e timeout destino=origen causa=particion segundos=2.0
21:36:19.123 borde-1 pedido=90bd3e origen_no_responde recurso=apunte.txt version=1 edad_segundos=6 stale_limit=4
21:36:19.123 borde-1 pedido=90bd3e rechaza recurso=apunte.txt causa=supera_limite version=1 edad_segundos=6 stale_limit=4
21:36:19.126 cliente pedido=90bd3e solicitud recurso=apunte.txt fuente=borde-2
21:36:19.129 borde-2 pedido=90bd3e miss recurso=apunte.txt causa=no_esta
21:36:19.129 borde-2 pedido=90bd3e pide_origen recurso=apunte.txt
21:36:19.132 origen  pedido=90bd3e responde recurso=apunte.txt version=1
21:36:19.134 borde-2 pedido=90bd3e guarda recurso=apunte.txt version=1 bytes=50 expira=21:36:22
21:36:19.136 cliente pedido=90bd3e respuesta version=1 resultado=miss fuente=borde-2
```

`estado()` de `borde-1` después del pedido 4: `apunte.txt` sigue guardada, `estado=obsoleta`, `edad_obsoleta=6`.

Pedido 5, reparado el corte, revalidación sin bajar:

```text
21:36:19.149 cliente pedido=c46cff solicitud recurso=apunte.txt fuente=borde-1
21:36:19.152 borde-1 pedido=c46cff miss recurso=apunte.txt causa=expirada version=1 expiro=21:36:13 edad_segundos=6
21:36:19.152 borde-1 pedido=c46cff pide_origen recurso=apunte.txt version=1
21:36:19.154 origen  pedido=c46cff responde recurso=apunte.txt version=1
21:36:19.157 borde-1 pedido=c46cff revalida recurso=apunte.txt version_local=1 version_origen=1 renovo=si expira=21:36:22
21:36:19.157 borde-1 pedido=c46cff hit recurso=apunte.txt version=1 estado=fresca
21:36:19.159 cliente pedido=c46cff respuesta version=1 resultado=hit fuente=borde-1
```

Nota: la corrida de arriba es anterior a F1-S08/R08. Desde esa tarde, en el pedido 5 la línea del origen lleva `misma=si` y no viajan bytes; el resto es igual.

## Qué se observó

Las cinco filas de la predicción se cumplieron, con los mismos nombres de operación y los mismos datos. Los dos pedidos de la partición dejan en una sola línea la edad y el límite (`edad_segundos=1 stale_limit=4` y `edad_segundos=6 stale_limit=4`), así que quien lee el historial no tiene que recalcular nada. El pedido 4 muestra además los dos niveles de `rechaza`: el borde rechaza y el cliente no lo da por final hasta probar `borde-2`.

Una segunda corrida con una copia **invalidada** durante la partición (`python3 -m fase1.escenarios invalidada`): los dos bordes anotan `miss causa=invalidada`, `origen_no_responde … edad_segundos=0` y `rechaza causa=invalidada`, y el cliente anota `respuesta resultado=rechaza fuente=ninguna`. `STALE_LIMIT` no habilita una copia que el origen mandó quitar, aunque su edad obsoleta sea 0.

## Conclusión

La política de contenido obsoleto queda definida y comprobada: cota de tiempo sobre la edad obsoleta (no sobre la edad total), medida en el borde, que es el único que puede medirla cuando el origen no contesta. Dentro de la cota el sistema prefiere disponibilidad (sirve una versión que puede estar vieja y lo dice en el resultado); fuera de la cota prefiere no mentir (rechaza y deja que el selector busque otra fuente). La copia rechazada no se tira: si el origen vuelve, un `revalida` la confirma sin bajar nada.

## Qué queda sin saber

- Cuál debe ser el valor definitivo de `STALE_LIMIT` para la entrega. El experimento muestra las dos ramas con 4 s; el número final se decide con Rubén al cerrar la fase 1 (sigue en 60 s provisionales).
- Qué pasa con un origen lento pero vivo (un `timeout` de verdad, no simulado). No hay escenario; es la ficha F3-R03.
- Si `borde-2` hubiera tenido una copia fresca durante la partición de `borde-1`, el pedido 3 habría servido igualmente la obsoleta de `borde-1` sin preguntar a `borde-2`: es la consecuencia aceptada del orden fijo del selector (decisión del 19 nov). No se midió.
- La partición es un interruptor del actor, no un corte de red. Lo que no se observa aquí es la latencia de un timeout real de 2 s: con el interruptor la respuesta «no responde» es inmediata.
