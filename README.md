# Distributed_SystemFP
Proyecto Final de la asignatura Sistemas Distribuidos

# Caché de contenido en el borde y red de distribución

## Descripción

Las cachés reducen la distancia entre el contenido y los clientes, mejorando los tiempos de respuesta y reduciendo la carga sobre el origen. Sin embargo, la distribución de copias introduce el problema de la **consistencia y obsolescencia del contenido**.

Un nodo de borde puede continuar siendo accesible para los clientes incluso cuando ha perdido la comunicación con el origen. Del mismo modo, una operación de invalidación puede retrasarse, fallar o no llegar a todos los nodos de la red.

Este proyecto propone construir un sistema distribuido de distribución de contenido compuesto por un **origen**, varias **cachés de borde** y **clientes**, incorporando lógica para seleccionar la fuente adecuada y gestionar diferentes situaciones de disponibilidad y consistencia.

---

## Objetivo general

Construir un sistema de distribución de contenido con un origen y múltiples cachés de borde, implementando mecanismos para:

* Seleccionar el borde o fuente más apropiada según una política definida.
* Gestionar aciertos y fallos de caché.
* Aplicar políticas de expulsión de contenido.
* Controlar la expiración y las versiones del contenido.
* Obtener contenido desde el origen cuando sea necesario.
* Realizar operaciones de invalidación y revalidación.
* Detectar y tratar fallos de nodos de borde.
* Definir el comportamiento ante contenido obsoleto durante particiones de red.
* Establecer explícitamente bajo qué condiciones se permite servir una copia obsoleta.

---

## Arquitectura general

El sistema estará compuesto por tres tipos principales de componentes:

```text
                       ┌─────────────────┐
                       │     ORIGEN      │
                       │                 │
                       │ Contenido       │
                       │ Versiones       │
                       └────────┬────────┘
                                │
                 ┌──────────────┼──────────────┐
                 │              │              │
                 ▼              ▼              ▼
        ┌────────────────┐ ┌────────────────┐ ┌────────────────┐
        │  CACHE BORDE 1 │ │  CACHE BORDE 2 │ │  CACHE BORDE N │
        │                │ │                │ │                │
        │ Contenido      │ │ Contenido      │ │ Contenido      │
        │ Versiones      │ │ Versiones      │ │ Versiones      │
        │ Expiración     │ │ Expiración     │ │ Expiración     │
        └───────┬────────┘ └───────┬────────┘ └───────┬────────┘
                │                  │                  │
                └──────────────────┼──────────────────┘
                                   │
                              ┌────▼─────┐
                              │ CLIENTES │
                              └──────────┘
```

El cliente solicitará un recurso al sistema. La lógica de selección determinará qué nodo de borde o fuente debe atender la solicitud.

Si el recurso se encuentra disponible y es válido en la caché seleccionada, se devolverá directamente desde el borde.

Si no está disponible, ha expirado o no cumple las condiciones de consistencia establecidas, el sistema deberá determinar si puede obtenerlo desde otro borde o directamente desde el origen.

---

## Funcionalidades y alcance

### 1. Origen de contenido y cachés de borde

El sistema contará con:

* Un nodo de origen que mantiene la versión considerada como referencia del contenido.
* Múltiples nodos de borde capaces de almacenar copias.
* Clientes que solicitan contenido a través de la red de distribución.

Cada copia almacenada deberá mantener información suficiente para determinar su estado, como:

* Identificador del recurso.
* Versión del contenido.
* Instante de creación o actualización.
* Tiempo de expiración.
* Estado de validez.
* Información necesaria para revalidación.

---

### 2. Selección de fuente

Ante una solicitud, el sistema deberá seleccionar la fuente apropiada de acuerdo con una política definida.

La política podrá considerar factores como:

* Disponibilidad del nodo.
* Existencia del recurso en caché.
* Frescura del contenido.
* Versión disponible.
* Distancia o latencia.
* Estado de conectividad con el origen.
* Posibilidad de utilizar contenido obsoleto.

El objetivo es que la selección de fuente sea una política explícita y configurable, no una decisión implícita del sistema.

---

### 3. Aciertos y fallos de caché

El sistema deberá distinguir entre:

#### Cache Hit

El recurso solicitado está disponible en la caché seleccionada y cumple las condiciones necesarias para ser servido.

```text
Cliente
   │
   ▼
Borde
   │
   ├── Recurso válido ──► HIT ──► Cliente
   │
```

#### Cache Miss

El recurso no está disponible en la caché seleccionada o no puede utilizarse.

```text
Cliente
   │
   ▼
Borde
   │
   ├── Recurso no disponible ──► MISS
   │
   ▼
Otra fuente / Origen
```

Se deberán registrar los aciertos y fallos para permitir evaluar el comportamiento del sistema. El formato, las operaciones que se anotan y dónde se guarda ese historial están descritos en [Registro de operaciones](#registro-de-operaciones).

---

## 4. Políticas de expulsión

Cuando una caché alcance su capacidad máxima deberá decidir qué elementos eliminar.

Se podrá implementar y comparar una o varias políticas de expulsión, por ejemplo:

* **LRU (Least Recently Used)**.
* **FIFO (First In, First Out)**.
* Otra política definida para el proyecto.

La política deberá determinar qué contenido se elimina cuando sea necesario liberar espacio.

---

## 5. Expiración y versiones

Cada recurso deberá asociarse con una versión.

Por ejemplo:

```text
Recurso: documento.pdf

Origen:
    versión = 5

Borde 1:
    versión = 5

Borde 2:
    versión = 4

Borde 3:
    versión = 5
```

Una solicitud deberá poder determinar si una copia almacenada sigue siendo válida.

La expiración podrá representarse mediante un tiempo de vida (**TTL**) o mediante otro mecanismo definido por el sistema.

Una copia puede encontrarse en estados como:

```text
┌──────────────┐
│     FRESCA   │
└──────┬───────┘
       │
       │ Expiración
       ▼
┌──────────────┐
│   OBSOLETA   │
└──────┬───────┘
       │
       │ Revalidación
       ▼
┌──────────────┐
│  ACTUALIZADA │
└──────────────┘
```

---

## 6. Obtención desde el origen

Cuando un borde no pueda satisfacer una solicitud, podrá obtener el contenido desde el origen.

El flujo básico será:

```text
Cliente
   │
   ▼
Borde
   │
   │ MISS
   ▼
Origen
   │
   │ Contenido
   ▼
Borde
   │
   │ Actualización de caché
   ▼
Cliente
```

El nuevo contenido podrá almacenarse en la caché para atender futuras solicitudes.

---

## 7. Invalidación y revalidación

El sistema deberá contemplar mecanismos para actualizar o invalidar copias distribuidas.

### Invalidación

Una operación de invalidación indica que una copia almacenada ya no debe considerarse válida.

```text
Origen
   │
   │ INVALIDATE
   ├──────────────► Borde 1
   ├──────────────► Borde 2
   └──────────────► Borde N
```

La invalidación puede:

* Llegar correctamente.
* Retrasarse.
* Perderse.
* Llegar solamente a algunos nodos.

El sistema deberá contemplar estas situaciones.

### Revalidación

Cuando un borde dispone de una copia potencialmente obsoleta, podrá consultar al origen para determinar si existe una versión más reciente.

```text
Borde
  │
  │ ¿Versión actual?
  ▼
Origen
  │
  ├── Sí ──► Mantener copia
  │
  └── No ──► Descargar nueva versión
```

---

## 8. Tratamiento de fallos de nodos de borde

Un nodo de borde puede:

* Dejar de responder.
* Perder temporalmente la conexión con el origen.
* Mantener conexión con algunos nodos pero no con otros.
* Contener una versión antigua del contenido.

El sistema deberá detectar o manejar estas situaciones y evitar depender exclusivamente de un único nodo de borde.

Ejemplo:

```text
              ┌──────────┐
              │  ORIGEN  │
              └────┬─────┘
                   │
          ┌────────┼────────┐
          │        │        │
          ▼        ▼        ▼
       Borde 1  Borde 2  Borde 3
          │        X        │
          │      FALLA      │
          │                 │
          └───────┬─────────┘
                  │
               Cliente
```

Si un nodo no está disponible, la política de selección deberá determinar si se utiliza otro borde o el origen.

---

# 9. Contenido obsoleto durante particiones

Uno de los problemas centrales del proyecto será determinar qué hacer cuando un nodo de borde puede atender a los clientes, pero no puede comunicarse con el origen.

Por ejemplo:

```text
                  ORIGEN
                    X
                  /   \
             PARTITION
                /       \
               /         \
          Borde 1       Cliente
          versión 4
```

El origen podría tener:

```text
versión = 5
```

mientras que el borde conserva:

```text
versión = 4
```

En esta situación, el sistema deberá tener una política explícita para decidir si la versión 4 puede ser servida.

---

## 10. Política de contenido obsoleto

El sistema deberá definir una **cota o condición explícita** bajo la cual se permita servir contenido obsoleto.

Una posible política conceptual es:

```text
Si:
    origen no disponible
    Y
    copia local disponible
    Y
    edad de la copia <= STALE_LIMIT

Entonces:
    permitir servir la copia obsoleta

En otro caso:
    rechazar la solicitud
    o utilizar otra fuente disponible
```

Por ejemplo:

```text
STALE_LIMIT = 10 minutos
```

Una copia que lleva 3 minutos obsoleta podría ser servida durante una partición, mientras que una copia que lleva 30 minutos obsoleta no cumpliría la condición.

La condición exacta deberá ser definida e implementada como parte del proyecto.

---

# Flujo general de una solicitud

Un flujo posible para una solicitud es:

```text
                    ┌──────────┐
                    │ CLIENTE  │
                    └────┬─────┘
                         │
                         ▼
                 ┌───────────────┐
                 │ Selección de  │
                 │    fuente     │
                 └───────┬───────┘
                         │
                         ▼
                    ┌─────────┐
                    │  BORDE  │
                    └────┬────┘
                         │
                  ┌──────┴──────┐
                  │             │
               ¿Existe?       ¿Existe?
                  │             │
                 Sí            No
                  │             │
                  ▼             ▼
             ¿Está fresca?   Buscar fuente
                  │
            ┌─────┴─────┐
            │           │
           Sí           No
            │           │
            ▼           ▼
          SERVIR    Revalidar /
                     consultar
                     origen
                         │
                    ┌────┴────┐
                    │         │
                 Disponible  No disponible
                    │         │
                    ▼         ▼
                  Actualizar  Evaluar
                  caché       contenido
                              obsoleto
                                  │
                         ┌────────┴────────┐
                         │                 │
                      Permitido         No permitido
                         │                 │
                         ▼                 ▼
                       SERVIR          RECHAZAR
```

---

# Componentes principales

El proyecto podrá organizarse conceptualmente en los siguientes componentes:

| Componente               | Responsabilidad                                     |
| ------------------------ | --------------------------------------------------- |
| **Origin**               | Mantener la versión de referencia del contenido     |
| **Edge Cache**           | Almacenar y servir copias del contenido             |
| **Client**               | Generar solicitudes de contenido                    |
| **Source Selector**      | Seleccionar la fuente apropiada                     |
| **Cache Manager**        | Gestionar hits, misses, expiración y almacenamiento |
| **Eviction Policy**      | Determinar qué elementos expulsar                   |
| **Version Manager**      | Controlar versiones y consistencia                  |
| **Invalidation Manager** | Gestionar invalidaciones                            |
| **Revalidation Manager** | Comprobar y actualizar copias                       |
| **Registro**             | Anotar cada operación en una línea de historial     |
| **Transporte**           | Enviar y recibir mensajes entre nodos               |

---

# Registro de operaciones

Origen, bordes, selector y cliente anotan cada operación relevante en un historial de texto. El historial sirve para seguir un pedido de punta a punta y comprobar qué rama de la regla se tomó. No se guarda el contenido del archivo: solo la decisión y los datos que la justifican.

Todas las anotaciones pasan por una única función compartida:

```text
registrar(nodo, pedido_id, operacion, datos...)
```

Nadie escribe el historial por su cuenta. Así el formato es el mismo en todos los programas.

## Identificador de pedido

El cliente crea un `pedido_id` al armar la solicitud y lo incluye en el mensaje. El borde lo copia cuando habla con el origen, y el origen lo copia en su propia línea. Filtrar el historial por ese identificador muestra el recorrido completo del pedido.

## Qué se anota

Cada operación del sistema produce una línea:

| Quién    | Operación                                      | Qué queda escrito                                              |
| -------- | ---------------------------------------------- | -------------------------------------------------------------- |
| Cliente  | `solicitud`                                    | Recurso y borde elegido                                        |
| Cliente  | `respuesta`                                    | Versión recibida y resultado (`hit`, `miss`, `sirve_obsoleta` o `rechaza`) |
| Borde    | `hit`                                          | Recurso, versión y estado `fresca`                             |
| Borde    | `miss`                                         | Recurso y causa: `no_esta`, `expirada`, `invalidada` o `supera_limite` |
| Borde    | `pide_origen`                                  | Recurso y versión local, si había                              |
| Origen   | `responde`                                     | Recurso y versión entregada                                    |
| Borde    | `guarda`                                       | Recurso, versión y expiración                                  |
| Borde    | `expulsion`                                    | Recurso que sale, política y recurso que entra                 |
| Origen   | `invalidar`                                    | Recurso, versión nueva y bordes avisados                       |
| Borde    | `invalidacion_recibida` o `invalidacion_perdida` | Recurso                                                      |
| Borde    | `revalida`                                     | Versión local, versión del origen, y si renovó o bajó otra     |
| Borde    | `origen_no_responde`                           | Recurso, segundos de obsolescencia y `STALE_LIMIT`             |
| Borde    | `sirve_obsoleta` o `rechaza`                   | La rama que tomó la regla                                      |
| Cualquiera | `timeout` o `nodo_caido`                     | A quién se llamó y que no contestó                             |

Un miss también se anota cuando la copia está guardada y no se puede usar: expirada, invalidada o por encima de `STALE_LIMIT`. No solo cuando el archivo falta.

La edad de la copia, la expiración y `STALE_LIMIT` se escriben como datos de la línea. Quien lee el historial no tiene que recalcularlos.

## Formato de una línea

Cada línea lleva siempre la hora, el nodo, el `pedido_id` y la operación. El resto son los datos de esa operación.

Un primer pedido, resuelto contra el origen:

```text
12:01:03.120 cliente pedido=7d2 solicitud recurso=apunte.pdf fuente=borde-1
12:01:03.131 borde-1 pedido=7d2 miss recurso=apunte.pdf causa=no_esta
12:01:03.140 borde-1 pedido=7d2 pide_origen recurso=apunte.pdf
12:01:03.155 origen   pedido=7d2 responde recurso=apunte.pdf version=1
12:01:03.160 borde-1 pedido=7d2 guarda recurso=apunte.pdf version=1 expira=12:01:33
12:01:04.010 cliente pedido=7d2 respuesta version=1 resultado=miss
```

Una copia vencida, con el origen inalcanzable y dentro del límite:

```text
12:11:20.004 borde-1 pedido=9af origen_no_responde recurso=apunte.pdf edad_segundos=180 stale_limit=600
12:11:20.008 borde-1 pedido=9af sirve_obsoleta recurso=apunte.pdf version=4
```

## Dónde se guarda

Cada nodo abre un archivo al arrancar y agrega ahí una línea por operación:

```text
logs/origen.log
logs/borde-1.log
logs/borde-2.log
logs/cliente.log
```

La misma línea se muestra en la consola de ese programa, para verla mientras corre. El directorio `logs/` no se versiona.

Para reconstruir un pedido:

```text
grep "pedido=7d2" logs/*.log
```

Los aciertos y los fallos se cuentan a partir de las líneas `hit` y `miss`. Esa cuenta es la que permite decir si la caché está sirviendo de algo.

## Desde el primer paso

El registro existe desde la primera operación que se implemente. El origen, al responder un recurso, ya llama a `registrar`. Cada operación nueva agrega su línea con el mismo formato, sin cambiar los campos fijos: hora, nodo, `pedido_id` y operación.

---

# Transporte y cifrado

La comunicación entre el origen y los bordes pasa siempre por un único punto de transporte. La lógica de caché, versiones, invalidación, revalidación y registro no abre sockets ni conoce si el canal va en claro o cifrado.

## Qué dejar preparado desde el principio

Origen y bordes se hablan solo con estas dos operaciones:

```text
enviar(destino, mensaje)
recibir() -> mensaje
```

Por encima de esas operaciones el mensaje sigue siendo texto: recurso, versión, `pedido_id` e invalidación. La primera implementación de `enviar` y `recibir` usa TCP en claro. Con ese canal se construye y se prueba el resto del sistema.

El cifrado queda apagado en la configuración:

```text
cifrado = false
```

Con `false`, el transporte abre el socket y escribe el mensaje tal cual. Cambiarlo a `true` más adelante no modifica las reglas ni el formato del historial.

## A partir de cuándo agregar TLS

TLS es un plus. Se empieza solo cuando el proyecto completo ya funciona en claro y se puede demostrar de punta a punta:

* Selección de fuente, aciertos y fallos.
* Expulsión, expiración y versiones.
* Invalidación, incluido un aviso que no llega.
* Revalidación contra el origen.
* Fallo de un borde.
* Partición con el origen y la regla de `STALE_LIMIT` (servir la copia dentro del límite y rechazarla cuando lo supera).

Ese es el punto de partida. Antes de eso, el cifrado no se implementa.

A partir de ahí, si queda tiempo:

1. `enviar` y `recibir` pasan a envolver el mismo TCP con TLS, usando la biblioteca del lenguaje. El cifrado no se implementa a mano.
2. Se crea una autoridad local del proyecto. El origen tiene su certificado y cada borde comprueba que está hablando con ese origen.
3. Se pone `cifrado = true` y se repiten las mismas pruebas que ya pasaban en claro. Hit, invalidación perdida, revalidación y `STALE_LIMIT` tienen que dar el mismo resultado.
4. Un fallo de handshake se trata como `origen_no_responde`: el borde aplica la regla de contenido obsoleto y lo anota en el historial.

Si después de eso todavía hay tiempo, cada borde presenta también su certificado y el origen solo acepta a los bordes conocidos.

El canal cifrado cubre la bajada del archivo, la revalidación y la invalidación. El cliente puede seguir hablando con el borde en claro. Lo que esta capa protege es que un borde acepte versiones e invalidaciones solo del origen de verdad.

Quedan fuera de esta capa, aunque sobre tiempo: un cifrado propio, cifrar el historial y cifrar las copias guardadas en el borde.

