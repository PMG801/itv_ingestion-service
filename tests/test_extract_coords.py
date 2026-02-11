#!/usr/bin/env python3
"""Script de prueba para verificar extracción de coordenadas desde Google Maps URL"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'extractor_services'))

from catalunya_api.transformer import extraer_coordenadas_google_maps

# Casos de prueba del XML
test_cases = [
    ("http://maps.google.com/maps?t=k&q=41.3028+2.019474", 41.3028, 2.019474, "Viladecans"),
    ("http://maps.google.com/maps?t=k&q=41.357138+2.095921", 41.357138, 2.095921, "Cornellà"),
    ("http://maps.google.com/maps?t=k&q=41.89709+1.059282", 41.89709, 1.059282, "Artesa de Segre"),
    ("http://maps.google.com/maps?t=k&q=41.480016+2.06332", 41.480016, 2.06332, "Sant Cugat"),
    ("http://maps.google.com/maps?t=k&q=41.990997+1.54423", 41.990997, 1.54423, "Solsona"),
    ("http://maps.google.com/maps?t=k&q=41.441284+2.203403", 41.441284, 2.203403, "BCN Caracas"),
]

print("=" * 80)
print("VERIFICACIÓN DE EXTRACCIÓN DE COORDENADAS DESDE GOOGLE MAPS URL")
print("=" * 80)
print()

errores = []

for url, lat_esperada, lon_esperada, desc in test_cases:
    lat, lon = extraer_coordenadas_google_maps(url)
    
    if lat is None or lon is None:
        print(f"❌ {desc}")
        print(f"   URL:       {url}")
        print(f"   Error:     No se pudieron extraer coordenadas")
        errores.append(desc)
    else:
        lat_ok = abs(lat - lat_esperada) < 0.000001
        lon_ok = abs(lon - lon_esperada) < 0.000001
        
        status = "✅" if (lat_ok and lon_ok) else "❌"
        
        print(f"{status} {desc}")
        print(f"   Esperado:  lat={lat_esperada:>10.6f}, lon={lon_esperada:>10.6f}")
        print(f"   Obtenido:  lat={lat:>10.6f}, lon={lon:>10.6f}")
        
        if not (lat_ok and lon_ok):
            errores.append(desc)
            if not lat_ok:
                print(f"   ⚠️  Error en latitud: diferencia = {abs(lat - lat_esperada)}")
            if not lon_ok:
                print(f"   ⚠️  Error en longitud: diferencia = {abs(lon - lon_esperada)}")
    
    print()

print("=" * 80)
if errores:
    print(f"❌ FALLARON {len(errores)} de {len(test_cases)} casos:")
    for err in errores:
        print(f"   - {err}")
else:
    print(f"✅ TODOS LOS {len(test_cases)} CASOS PASARON CORRECTAMENTE")
print("=" * 80)

sys.exit(0 if not errores else 1)
