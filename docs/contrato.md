# Contrato

Lo que se ve desde fuera al pedir un archivo. Samy construye el borde y el cliente contra este texto. Aquí no aparecen nombres de Ray ni de cómo se guarda la copia por dentro.

## Quién es el cliente

El cliente es un programa del sistema, un proceso distinto del origen y de los bordes. Representa a quien quiere el archivo: en una caché real, el navegador o la aplicación. En este proyecto es ese programa, no una persona y no una ventana.

El cliente crea el `pedido_id`, pide un recurso por su nombre y recibe la respuesta. No guarda la caché, no numera versiones y no aplica `STALE_LIMIT`.

El cliente no elige el borde. Pide el recurso. La selección, que vive junto al cliente, escoge la fuente (un borde o el origen). El historial anota esa fuente en la línea `solicitud`, como `fuente=borde-1`. Eso es el resultado de la selección, no un dato que el cliente envíe.

## Pedido

El cliente envía:

- `pedido_id`, que él mismo crea.
- `recurso`, el nombre del archivo. Por ejemplo, `apunte.pdf`.

## Respuesta

El cliente recibe tres cosas:

- `version`, la versión del contenido que se está entregando. Viaja cuando hay archivo.
- `resultado`: `hit`, `miss`, `sirve_obsoleta`, `rechaza` o `file_doesnt_exist`.
- `contenido`, los bytes del archivo.

`hit`, `miss` y `sirve_obsoleta` traen versión y contenido. `rechaza` y `file_doesnt_exist` no traen contenido.

El historial no guarda el contenido. La línea `respuesta` del cliente lleva la versión, si la hay, y el resultado. `file_doesnt_exist` es el resultado «file doesn't exist»: el origen contestó que ese recurso no está.

## Qué significa cada resultado

- `hit`: se entrega la copia del borde. Estaba fresca, o el origen acaba de confirmar la misma versión y el TTL volvió a empezar.
- `miss`: no había una copia que se pudiera usar, el contenido se obtuvo del origen y se entrega ese archivo.
- `sirve_obsoleta`: el origen no contesta, en un borde alcanzable hay una copia que no fue invalidada y su edad es menor o igual que `STALE_LIMIT`. Se entrega esa copia.
- `rechaza`: no se entrega el archivo. Los casos están abajo.
- `file_doesnt_exist`: el origen contestó y el recurso no existe. No se entrega el archivo. El borde borra en ese momento la copia de ese nombre.

## Cuándo el cliente ve `rechaza`

`rechaza` llega solo después de agotar las fuentes. Si el primer borde no tiene una copia que se pueda usar y el origen no contesta, la selección prueba el otro borde.

- Si el otro borde tiene una copia fresca, el resultado es `hit` y se entrega el archivo.
- Si el origen contesta con el archivo, el resultado es `miss`.
- Si el origen no contesta y algún borde alcanzable tiene una copia no invalidada dentro de `STALE_LIMIT`, el resultado es `sirve_obsoleta`.
- Si los dos bordes y el origen se quedan sin poder entregar el archivo, el resultado es `rechaza`.

Una copia cuya edad pasa de `STALE_LIMIT`, con el origen en silencio, no se entrega. Si el otro borde tampoco puede entregarla, el resultado es `rechaza`.

Una copia invalidada no se sirve mientras el borde no logre hablar con el origen y bajar la versión nueva. `STALE_LIMIT` no alcanza para entregarla. Si el origen no contesta y el otro borde tampoco tiene una copia que se pueda usar, el resultado es `rechaza`. Si el origen sí contesta, el borde baja la versión nueva y el cliente ve `miss` con ese archivo.

## Frescura

Una copia recién guardada está fresca durante `TTL = 30` segundos. Es un valor provisional, por la misma razón que `STALE_LIMIT`: poder ver frescura, obsolescencia y las dos ramas del límite sin esperas largas. Pasados los 30 segundos la copia está obsoleta. `STALE_LIMIT` (60 segundos) mide cuánto tiempo lleva obsoleta, no cuánto tiempo lleva guardada.

Si el borde pregunta al origen y el origen confirma la misma versión, el cliente ve `hit`. La copia sigue en el borde y el TTL vuelve a contar desde esa respuesta. `miss` queda para cuando el origen entrega otro contenido.

## Cuándo el borde borra la copia

El borde borra la copia en cuanto se entera de que no puede seguir guardándola:

- Al pedirla, el origen responde que ya no está. El cliente ve `file_doesnt_exist`.
- La edad obsoleta ya pasó `STALE_LIMIT` y el origen responde que esa copia es obsoleta. Esa copia vieja se borra. Si el origen además entrega una versión nueva, el cliente ve `miss` y el borde guarda ese archivo.

Si llega la invalidación, la copia no se borra. Se marca no válida y no se devuelve aunque la pidan. El borde pregunta al origen: si entrega el archivo, el cliente ve `miss` y esa copia nueva reemplaza a la invalidada; si dice que no está, ahí sí se borra.

Si el origen sigue en silencio, la copia no se borra. Solo sale del borde si la expulsión LRU la elige porque el borde se llenó. Mientras permanece, se entrega con `sirve_obsoleta` si no está invalidada y la edad obsoleta cabe en `STALE_LIMIT`. Si ya pasó ese límite, no se entrega y el resultado puede ser `rechaza`, pero la copia sigue guardada.
