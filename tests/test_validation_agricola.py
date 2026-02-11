"""Script de prueba para validar estaciones agrícolas móviles."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'extractor_services'))

from common.schemas import TipoEstacion
from common.validators import validar_estacion_agricola, validar_coordenadas

print("=" * 70)
print("PRUEBA: Validación de estaciones agrícolas móviles")
print("=" * 70)

# Caso 1: Estación agrícola SIN código postal (VÁLIDA)
print("\n1. Estación agrícola SIN código postal:")
es_valida, error = validar_estacion_agricola(None, TipoEstacion.OTROS)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")
if error:
    print(f"   Error: {error}")

# Caso 2: Estación agrícola CON código postal (INVÁLIDA - debe rechazarse)
print("\n2. Estación agrícola CON código postal '46001':")
es_valida, error = validar_estacion_agricola("46001", TipoEstacion.OTROS)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")
if error:
    print(f"   Error: {error}")

# Caso 3: Estación agrícola CON código postal vacío (VÁLIDA)
print("\n3. Estación agrícola CON código postal vacío '':")
es_valida, error = validar_estacion_agricola("", TipoEstacion.OTROS)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")
if error:
    print(f"   Error: {error}")

# Caso 4: Estación FIJA con código postal (VÁLIDA - no aplica regla)
print("\n4. Estación FIJA con código postal '46001':")
es_valida, error = validar_estacion_agricola("46001", TipoEstacion.ESTACION_FIJA)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")
if error:
    print(f"   Error: {error}")

# Caso 5: Estación MÓVIL con código postal (VÁLIDA - no aplica regla)
print("\n5. Estación MÓVIL con código postal '46001':")
es_valida, error = validar_estacion_agricola("46001", TipoEstacion.ESTACION_MOVIL)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")
if error:
    print(f"   Error: {error}")

print("\n" + "=" * 70)
print("PRUEBA: Validación de coordenadas según tipo de estación")
print("=" * 70)

# Caso 6: Estación agrícola (OTROS) - NO se validan coordenadas
print("\n6. Estación agrícola (OTROS) con coordenadas [39.5, -0.5]:")
es_valida = validar_coordenadas(39.5, -0.5, "Valencia", "Estación Agrícola Test", TipoEstacion.OTROS)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")

# Caso 7: Estación FIJA con coordenadas válidas
print("\n7. Estación FIJA con coordenadas [39.5, -0.5] en Valencia:")
es_valida = validar_coordenadas(39.5, -0.5, "Valencia", "Estación Fija Test", TipoEstacion.ESTACION_FIJA)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")

# Caso 8: Estación FIJA con coordenadas fuera de España (debe rechazarse)
print("\n8. Estación FIJA con coordenadas [51.5, -0.1] fuera de España:")
es_valida = validar_coordenadas(51.5, -0.1, "Valencia", "Estación Fija Test", TipoEstacion.ESTACION_FIJA)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")

# Caso 9: Estación agrícola con coordenadas fuera de España (NO se valida, pasa)
print("\n9. Estación agrícola (OTROS) con coordenadas [51.5, -0.1] fuera de España:")
es_valida = validar_coordenadas(51.5, -0.1, "Valencia", "Estación Agrícola Test", TipoEstacion.OTROS)
print(f"   Resultado: {'✅ VÁLIDA' if es_valida else '❌ INVÁLIDA'}")

print("\n" + "=" * 70)
print("Pruebas completadas")
print("=" * 70)
