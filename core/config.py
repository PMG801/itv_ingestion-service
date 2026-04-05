"""Configuración centralizada de la aplicación usando Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración de la aplicación.

    Attributes:
        APP_NAME: Nombre de la aplicación.
        LOG_LEVEL: Nivel de logging (DEBUG, INFO, WARNING, ERROR).

        RabbitMQ Configuration:
            RABBITMQ_HOST: Hostname del servidor RabbitMQ.
            RABBITMQ_PORT: Puerto del servidor RabbitMQ.
            RABBITMQ_USER: Usuario para autenticación.
            RABBITMQ_PASS: Contraseña para autenticación.
            RABBITMQ_VHOST: Virtual host de RabbitMQ.

        PostgreSQL Configuration:
            POSTGRES_HOST: Hostname del servidor PostgreSQL.
            POSTGRES_PORT: Puerto del servidor PostgreSQL.
            POSTGRES_USER: Usuario de PostgreSQL.
            POSTGRES_PASSWORD: Contraseña de PostgreSQL.
            POSTGRES_DB: Nombre de la base de datos.
    """

    # Application settings
    APP_NAME: str = "ITV Ingestion Service"
    LOG_LEVEL: str = "INFO"

    # RabbitMQ settings
    RABBITMQ_HOST: str = "rabbitmq"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "admin"
    RABBITMQ_PASS: str = "admin123"
    RABBITMQ_VHOST: str = "itv_data"

    # PostgreSQL settings
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "itv_user"
    POSTGRES_PASSWORD: str = "itv_pass123"
    POSTGRES_DB: str = "itv_database"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    @property
    def RABBITMQ_URL(self) -> str:
        """
        Construye la URL de conexión a RabbitMQ.

        Returns:
            URL completa en formato amqp://user:pass@host:port/vhost
        """
        return (
            f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASS}"
            f"@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{self.RABBITMQ_VHOST}"
        )

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        """
        Construye la URI de conexión asíncrona a PostgreSQL.

        Returns:
            URI completa en formato postgresql+asyncpg://user:pass@host:port/database
        """
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


# Instancia global de configuración
settings = Settings()
