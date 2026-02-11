#!/bin/bash
# Script para ejecutar todos los tests refactorizados
# Uso: ./tests/run_tests.sh [opciones]

set -e  # Salir si hay error

echo "🧪 Ejecutando Tests Refactorizados - Arquitectura Microservicios"
echo "================================================================"
echo ""

# Ir al directorio raíz del proyecto
cd "$(dirname "$0")/.."

# Colores
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar que pytest está instalado
if ! command -v pytest &> /dev/null; then
    echo -e "${YELLOW}⚠️  pytest no está instalado. Instalando dependencias...${NC}"
    pip install -q -r tests/requirements-test.txt
    echo -e "${GREEN}✅ Dependencias instaladas${NC}"
    echo ""
fi

# Función para ejecutar tests con formato bonito
run_test_suite() {
    local name=$1
    local path=$2
    
    echo -e "${BLUE}📦 $name${NC}"
    echo "-----------------------------------------------------------"
    
    if pytest "$path" -v --tb=short; then
        echo -e "${GREEN}✅ $name: PASSED${NC}"
    else
        echo -e "${YELLOW}⚠️  $name: ALGUNOS TESTS FALLARON${NC}"
    fi
    echo ""
}

# Si se pasa argumento, ejecutar solo ese test
if [ $# -gt 0 ]; then
    echo "Ejecutando: $1"
    pytest "$1" -v
    exit 0
fi

# Ejecutar todos los suites de tests
echo -e "${BLUE}🚀 Ejecutando todos los test suites...${NC}"
echo ""

run_test_suite "Common Schemas" "tests/test_common_schemas.py"
run_test_suite "Valencia API" "tests/test_valencia_api.py"
run_test_suite "Catalunya API" "tests/test_catalunya_api.py"
run_test_suite "Galicia API" "tests/test_galicia_api.py"
run_test_suite "API Central Ingest" "tests/test_api_central_ingest.py"

echo ""
echo "================================================================"
echo -e "${GREEN}✅ Tests completados${NC}"
echo ""

# Mostrar resumen
echo -e "${BLUE}📊 Generando reporte de cobertura...${NC}"
pytest tests/ --cov=app --cov=extractor_services --cov-report=term-missing --tb=no -q

echo ""
echo -e "${GREEN}✨ ¡Tests refactorizados completados!${NC}"
