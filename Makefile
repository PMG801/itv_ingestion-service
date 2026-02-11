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
	docker-compose up --build

up-infra: ## Levantar solo infraestructura (RabbitMQ + PostgreSQL)
	docker-compose -f infra/docker-compose.infrastructure.yml up -d

up-apps: ## Levantar solo aplicaciones
	docker-compose -f infra/docker-compose.apps.yml up --build

down: ## Detener todos los servicios
	docker-compose down
	docker-compose -f infra/docker-compose.apps.yml down
	docker-compose -f infra/docker-compose.infrastructure.yml down

logs: ## Ver logs de todos los servicios
	docker-compose logs -f

logs-gateway: ## Ver logs del Gateway
	docker-compose logs -f gateway

logs-normalizer: ## Ver logs del Normalizer
	docker-compose logs -f normalizer

logs-persister: ## Ver logs del Persister
	docker-compose logs -f persister

clean: ## Limpiar contenedores, volúmenes y caché
	docker-compose down -v
	docker system prune -f

clean-all: ## Limpiar TODO (incluye imágenes)
	docker-compose down -v --rmi all
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
