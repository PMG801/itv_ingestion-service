# ADR 003: Plugin Architecture para Proveedores LLM

**Estado:** Aceptado
**Contexto:** El sistema inicialmente usaba Groq como único proveedor LLM. Se requería flexibilidad para soportar múltiples proveedores (Azure OpenAI, AWS Bedrock, etc.) sin cambios en el código de transformación.
**Decisión:** Implementar una arquitectura basada en plugins con una clase base abstracta `BaseLLMClient` y subclases concretas (`GroqClient`, `AzureOpenAIClient`, etc.). El patrón Factory (`LLMClientFactory`) selecciona la implementación correcta basándose en la configuración (`settings.LLM_PROVIDER`).
**Consecuencias:**
- (+) Soporta múltiples proveedores sin cambiar lógica de transformación.
- (+) Facilita testing con mocks de clientes LLM.
- (+) Migración de proveedores es configuración, no código.
- (+) Backward compatible: parámetros Groq existentes se mantienen activos.
- (-) Requiere validación de parámetros específicos por proveedor en `core/config.py`.
- (-) Latencias de API pueden variar entre proveedores.

**Validación:** Migramos de Groq a Azure OpenAI en tests exitosamente (113 domain tests + 34 gateway tests pasando).

# ADR 004: Cache de Reglas de Mapeo por Tipo de Provincia

**Estado:** Aceptado
**Contexto:** Cada batch de ingesta requería una llamada LLM para generar un mapeo entre campos. Para estaciones del mismo tipo de provincia (e.g., Barcelona), esto generaba llamadas redundantes y costos innecesarios de API.
**Decisión:** Implementar una tabla `llm_mapping_rules` que cachea el mapeo generado por LLM usando clave compuesta `(source_system, province_type)`. Una regla activa por clave; las antiguas se desactivan automáticamente. Las reglas incluyen metadatos (modelo LLM, versión de prompt, confianza, firma de esquema).
**Consecuencias:**
- (+) Reduce llamadas LLM en ~80% para datos rutinarios (mismo tipo de provincia).
- (+) Ahorro significativo de costos de API y latencia.
- (+) Versioning automático de reglas con campos `llm_model` y `llm_prompt_version`.
- (+) Endpoint manual `DELETE /api/v1/monitoring/llm-rules/{source}/{province_type}` permite invalidar caches.
- (+) Schema versioning mediante `sample_schema_signature` (SHA256 truncado).
- (-) Requiere migración de BD (Alembic 003).
- (-) Posible staleness: cambios en estructura de datos requieren invalidación manual.
- (-) Complejidad adicional en LLMTransformer.

**Métricas:** `llm_rule_cache_hit`, `llm_rule_cache_miss`, `llm_rule_generation_calls`, `llm_rule_application_errors`.

**Validación:** Todos los tests de caché pasan (7/7). Backward compatibility: sistema funciona sin DB session (modo clásico sin caché).

# ADR 005: Aislamiento de Métodos de Normalización para Experimentación

**Estado:** Aceptado
**Contexto:** El sistema implementa tres métodos de normalización: RULES (manual), FUZZY (búsqueda difusa), y LLM (generativo). Para evaluar eficacia, necesitamos ejecutarlos en paralelo sin interferencias.
**Decisión:** Mantener las tres estrategias (`RulesTransformer`, `FuzzyTransformer`, `LLMTransformer`) completamente aisladas:
- Cada una con su propia lógica sin dependencias cross-cutting.
- Métricas independientes para cada estrategia.
- Pruebas unitarias sin mocks cruzados.
- Configuración selectiva de cuál usar por `source_system`.

**Consecuencias:**
- (+) Datos experimentales limpios para comparación A/B.
- (+) Fácil paralelización (ejecutar en GPU threads independientes).
- (+) Rollback de un método no afecta otros.
- (-) Duplicación de código para operaciones comunes (e.g., minificación de payloads).
- (-) Mayor consumo de memoria si se ejecutan los 3 en paralelo.

**Metodología:** Cada método genera su propia métrica de "éxito"; frontend puede comparar tasas de acierto.

**Validación:** 113 domain tests verifican aislamiento. Pruebas independientes: `test_llm_transformer_cache.py`, `test_fuzzy_transformer.py`, `test_rules_transformer.py`.
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