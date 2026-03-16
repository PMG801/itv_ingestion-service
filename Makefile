# Makefile para ITV Data Engine
# Comandos útiles para desarrollo

.PHONY: help setup up down logs clean test

help: ## Mostrar ayuda
	@echo "Comandos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Configurar entorno inicial
	cp .env.example .env
	@echo "✅ Archivo .env creado. Edítalo con tus credenciales."

up: ## Levantar todos los servicios
	docker compose up --build

up-infra: ## Levantar solo infraestructura (RabbitMQ + PostgreSQL)
	docker compose -f infra/docker-compose.infrastructure.yml up -d

up-apps: ## Levantar solo aplicaciones
	docker compose -f infra/docker-compose.apps.yml up --build

down: ## Detener todos los servicios
	docker compose down
	docker compose -f infra/docker-compose.apps.yml down
	docker compose -f infra/docker-compose.infrastructure.yml down

logs: ## Ver logs de todos los servicios
	docker compose logs -f

logs-gateway: ## Ver logs del Gateway
	docker compose logs -f gateway

logs-normalizer: ## Ver logs del Normalizer
	docker compose logs -f normalizer

logs-persister: ## Ver logs del Persister
	docker compose logs -f persister

clean: ## Limpiar contenedores, volúmenes y caché
	docker compose down -v
	docker system prune -f

clean-all: ## Limpiar TODO (incluye imágenes)
	docker compose down -v --rmi all
	docker system prune -af --volumes

restart: down up ## Reiniciar todos los servicios

install: ## Instalar dependencias con PDM
	pdm install

install-dev: ## Instalar dependencias de desarrollo
	pdm install -d

test: ## Ejecutar tests
	pdm run test

test-cov: ## Ejecutar tests con cobertura
	pdm run test-cov

format: ## Formatear código con black
	pdm run format

lint: ## Ejecutar linter (ruff)
	pdm run lint

type-check: ## Verificar tipos con mypy
	pdm run type-check

quality: format lint type-check ## Ejecutar todas las verificaciones de calidad

rabbitmq-ui: ## Abrir RabbitMQ Management UI
	@echo "Abriendo http://localhost:15672"
	@echo "Usuario: admin | Contraseña: admin123"

psql: ## Conectar a PostgreSQL
	docker exec -it itv_postgres psql -U itv_user -d itv_database

check-health: ## Verificar estado de servicios
	@echo "🔍 Verificando servicios..."
	@curl -s http://localhost:8000/health > /dev/null && echo "✅ Gateway OK" || echo "❌ Gateway FAIL"
	@curl -s http://localhost:15672 > /dev/null && echo "✅ RabbitMQ OK" || echo "❌ RabbitMQ FAIL"
	@docker exec itv_postgres pg_isready -U itv_user > /dev/null 2>&1 && echo "✅ PostgreSQL OK" || echo "❌ PostgreSQL FAIL"

# ============================================================================
# Comandos de Alembic (Migraciones de Base de Datos)
# ============================================================================

migrate-create: ## Crear nueva migración (uso: make migrate-create MSG="descripcion")
	@if [ -z "$(MSG)" ]; then \
		echo "❌ Error: Debes proporcionar un mensaje."; \
		echo "Uso: make migrate-create MSG='Descripcion del cambio'"; \
		exit 1; \
	fi
	@echo "📝 Creando migración: $(MSG)"
	alembic revision --autogenerate -m "$(MSG)"
	@echo "✅ Migración creada en alembic/versions/"
	@echo "⚠️  Revisa el archivo generado antes de aplicar!"

migrate-up: ## Aplicar todas las migraciones pendientes
	@echo "⬆️  Aplicando migraciones..."
	alembic upgrade head
	@echo "✅ Migraciones aplicadas"

migrate-down: ## Revertir última migración
	@echo "⬇️  Revirtiendo última migración..."
	alembic downgrade -1
	@echo "✅ Migración revertida"

migrate-status: ## Ver estado actual de migraciones
	@echo "📊 Estado de migraciones:"
	@echo ""
	@echo "▶️  Versión actual:"
	@alembic current
	@echo ""
	@echo "📜 Última migración aplicada:"
	@alembic history --verbose | head -n 10

migrate-history: ## Ver historial completo de migraciones
	@echo "📜 Historial de migraciones:"
	alembic history --verbose

migrate-sql: ## Generar SQL de migración sin aplicarla (uso: make migrate-sql > migration.sql)
	@echo "-- SQL generado por Alembic (no ejecutado)"
	alembic upgrade head --sql

migrate-reset: ## PELIGRO: Resetear todas las migraciones (borra alembic_version)
	@echo "⚠️  ADVERTENCIA: Esto eliminará el tracking de versiones de Alembic"
	@read -p "¿Estás seguro? (escribe 'SI' para confirmar): " confirm; \
	if [ "$$confirm" = "SI" ]; then \
		docker exec itv_postgres psql -U itv_user -d itv_database -c "DROP TABLE IF EXISTS itv.alembic_version CASCADE;"; \
		echo "✅ Tabla alembic_version eliminada. Ejecuta 'make migrate-up' para volver a crear."; \
	else \
		echo "❌ Operación cancelada"; \
	fi

migrate-init-db: ## Inicializar BD con extensiones y aplicar migraciones
	@echo "🔧 Inicializando base de datos..."
	@echo "1️⃣  Verificando PostgreSQL..."
	@docker exec itv_postgres pg_isready -U itv_user > /dev/null 2>&1 || (echo "❌ PostgreSQL no está disponible" && exit 1)
	@echo "2️⃣  Aplicando migraciones..."
	@make migrate-up
	@echo "✅ Base de datos inicializada"

