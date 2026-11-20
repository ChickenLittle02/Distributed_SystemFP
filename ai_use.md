# Declaración de uso de asistentes de IA

Formato de la metodología del curso («Trabajo asistido por IA y disclosure»,
<https://matcom.github.io/distributed-systems-2026/es/projects/methodology/>): una declaración
ligera por repositorio, sin transcripciones. La responsabilidad por la corrección es de los
integrantes, no del asistente.

```yaml
ai_use:
  used: true
  tools:
    - Claude Code (Samy)
    - <Rubén completa las suyas>
  activities:
    - discusión de arquitectura y de las decisiones de diseño (TTL, LRU, selección, STALE_LIMIT)
    - implementación del borde, el selector, el cliente, los escenarios y el checklist de la fase 1
    - redacción y revisión de la documentación (contrato, decisiones, código, diagrama, experimento, mapa de Ray)
    - depuración con los historiales de logs/
  verification:
    - corrida repetible del checklist (python3 -m fase1.checklist): los diez comportamientos comprobados en logs/
    - escenarios de fallo (borde muerto, origen muerto, partición, aviso perdido) con la evidencia en logs/
    - revisión cruzada entre los dos integrantes de cada tarea y cada decisión (schedule.md, docs/decisiones.md)
    - lectura manual de los historiales filtrados por pedido_id
```

Qué se delegó y qué no. El asistente escribió código y texto a partir de las reglas del README,
del contrato y de las decisiones que los integrantes discutieron y aprobaron una por una; cada
decisión lleva en `docs/decisiones.md` quién la implementa y quién la revisó. Las reglas de la
caché (hit, miss, TTL, LRU, invalidación, revalidación, `STALE_LIMIT`, selección) son del
proyecto y están explicadas por los integrantes en `docs/explicaciones.md` y `docs/salida-fase1.md`.
Ninguna biblioteca ni asistente decide esas reglas en tiempo de ejecución.

Esta declaración se actualiza en cada fase (F2-S16, F3-S09 del tablero).
