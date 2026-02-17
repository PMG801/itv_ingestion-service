# ADR 001: Arquitectura Orientada a Eventos con RabbitMQ

**Estado:** Aceptado
**Contexto:** El sistema original era funcional pero poco escalable y difícil de mantener al integrar nuevas fuentes.
**Decisión:** Separar la ingestión (Gateway) de la normalización (Normalizer) usando RabbitMQ como broker.
**Consecuencias:**
- (+) Desacoplamiento total entre fuentes y base de datos.
- (+) Capacidad de procesar picos de carga sin tirar la API.
- (-) Mayor complejidad operativa (requiere gestionar el broker).

# ADR 002: Normalización Centralizada (Patrón Strategy)

**Estado:** Aceptado
**Contexto:** Cada comunidad autónoma provee datos en formatos heterogéneos (XML, JSON, CSV).
**Decisión:** El `itv_normalizer` centraliza toda la lógica de transformación. Se usa el patrón Strategy para seleccionar el transformador según el campo `source` del mensaje.