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

Se deberán registrar los aciertos y fallos para permitir evaluar el comportamiento del sistema.

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

