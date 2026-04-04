# Contexto del Normalizer para Análisis de Rendimiento

Este documento resume la base crítica actual del normalizer para poder comparar otro normalizador implementado con diferentes tecnologías.

## Alcance funcional

El normalizer actual no solo transforma datos. También aplica validaciones de negocio, normaliza campos, deduplica estaciones dentro del mismo mensaje y publica rechazos cuando algo no cumple las reglas.

## Flujo real de procesamiento

1. El worker recibe un mensaje con `message_id`, `source`, `payload` y `format`.
2. Valida la estructura básica del mensaje.
3. Selecciona el transformer correcto según la fuente.
4. El transformer parsea el payload y construye objetos `NormalizedStation`.
5. Se aplican normalizaciones comunes.
6. Se aplican validaciones de negocio.
7. Se eliminan duplicados dentro del mismo mensaje.
8. Los resultados válidos se publican en `normalized_data`.
9. Los fragmentos rechazados se publican en la cola de rechazo para trazabilidad.

## Capa de validación y normalización

### 1. Validación del mensaje de entrada

Situada en el worker del normalizer.

- Comprueba que exista `source`.
- Comprueba que exista `payload`.
- Comprueba que `source` sea una de las fuentes soportadas.
- Comprueba que `format` sea `json`, `xml` o `csv`.

Esto mide el coste mínimo de orquestación antes de entrar en la lógica de dominio.

### 2. Normalización común

Implementada en la clase base de los transformers.

- Normalización de strings opcionales.
- Generación de `station_id` con prefijo de fuente.
- Parseo de números flotantes.
- Limpieza de teléfono.
- Limpieza de código postal.

Estas operaciones forman la base comparable entre normalizadores, porque representan el coste común de preparación de datos.

### 3. Validaciones de negocio

También definidas en la base común.

- Validación simple del email.
- Validación de provincia española.
- Validación de coordenadas por provincia.
- Validación de código postal por provincia.
- Validación de mínimos de contacto y localización.

Estas validaciones determinan el coste de filtrado y rechazo del pipeline.

### 4. Deduplicación intra-mensaje

La capa base filtra estaciones repetidas dentro del mismo lote.

- Duplicado por `station_id`.
- Duplicado por combinación `name + city`.
- Duplicado de teléfono.
- Duplicado de email.

Esto añade coste adicional por mensaje, pero evita propagar datos repetidos al downstream.

## Normalización específica por fuente

### Catalunya

- Entrada: XML o payload ya parseado.
- Mapea campos como `id`, `nom`, `adreca`, `ciutat`, `provincia`, `codi_postal`, `latitud`, `longitud`, `telefon`, `email`.
- Convierte el payload a `NormalizedStation`.
- Aplica validación común.
- Aplica deduplicación al final del lote.

### Valencia

- Entrada: JSON o lista/dict equivalente.
- Mapea campos como `codigo`, `nombre`, `direccion`, `poblacion`, `provincia`, `codigo_postal`, `latitud`, `longitud`, `telefono`, `correo`.
- Convierte el payload a `NormalizedStation`.
- Aplica validación común.
- Aplica deduplicación al final del lote.

### Galicia

- Entrada: CSV, lista de dicts o dict equivalente.
- Mapea campos como `id`, `nome`, `enderezo`, `concello`, `provincia`, `cp`, `lat`, `lon`, `telefono`, `email`.
- Convierte el payload a `NormalizedStation`.
- Aplica validación común.
- Aplica deduplicación al final del lote.

## Qué medir en un benchmark

Para comparar otro normalizador con una base equivalente, conviene medir estas fases por separado:

- Tiempo de validación del mensaje.
- Tiempo de parseo por formato.
- Tiempo de mapeo a modelo normalizado.
- Tiempo de validación de negocio.
- Tiempo de deduplicación.
- Tiempo de serialización/publicación de válidos.
- Tiempo de publicación de rechazados.

## Observaciones para comparación justa

- El normalizer actual mezcla transformación y validación en la misma cadena de ejecución.
- El coste no depende solo del parseo del formato, sino también de la cantidad de reglas aplicadas por estación.
- Para comparar otra tecnología de forma justa, conviene mantener el mismo contrato de entrada, las mismas reglas y la misma política de rechazo.

## Puntos de referencia en el código

- Validación y orquestación del worker: [apps/normalizer/worker.py](../apps/normalizer/worker.py)
- Normalización y validación base: [domain/itv_stations/transformers/base.py](../domain/itv_stations/transformers/base.py)
- Transformador Catalunya: [domain/itv_stations/transformers/catalunya.py](../domain/itv_stations/transformers/catalunya.py)
- Transformador Valencia: [domain/itv_stations/transformers/valencia.py](../domain/itv_stations/transformers/valencia.py)
- Transformador Galicia: [domain/itv_stations/transformers/galicia.py](../domain/itv_stations/transformers/galicia.py)
