"""  
Gestión de conexiones a PostgreSQL.

Este módulo proporciona una clase singleton para gestionar el pool de conexiones
a la base de datos PostgreSQL usando psycopg v3.

Características:
- Pool de conexiones para mejor rendimiento
- Ejecución asíncrona usando ThreadPoolExecutor
- Compatible con FastAPI (async/await)
- Manejo robusto de errores y logging
"""

import logging
from contextlib import contextmanager
from typing import Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    import psycopg
    from psycopg_pool import ConnectionPool
except Exception:
    psycopg = None
    ConnectionPool = None

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Clase singleton para gestionar conexiones a PostgreSQL.
    
    Esta implementación usa psycopg v3 en modo síncrono con un pool de conexiones
    para optimizar el rendimiento. Las queries se ejecutan en threads separados
    usando ThreadPoolExecutor para mantener compatibilidad con FastAPI async.
    
    Características:
    - Pool de conexiones (min 2, max 10 por defecto)
    - Ejecución asíncrona mediante ThreadPoolExecutor
    - Context manager para manejo seguro de conexiones
    - Manejo automático de commits y rollbacks
    
    Attributes:
        _pool: Pool de conexiones a PostgreSQL
        _thread_pool: Pool de threads para ejecución asíncrona
        _connection_string: String de conexión a la base de datos
    
    Example:
        >>> DatabaseConnection.connect_to_database("postgresql://user:pass@host/db")
        >>> results = await DatabaseConnection.execute_query("SELECT * FROM estacion")
    """

    _pool: Optional[ConnectionPool] = None
    _thread_pool: Optional[ThreadPoolExecutor] = None
    _connection_string: Optional[str] = None

    @classmethod
    def connect_to_database(cls, database_url: str, min_conn: int = 2, max_conn: int = 10):
        """
        Inicializa el pool de conexiones a PostgreSQL.
        
        Este método debe ser llamado al inicio de la aplicación (en el lifespan).
        Crea tanto el pool de conexiones a la BD como el pool de threads para
        ejecución asíncrona.
        
        Args:
            database_url: URL de conexión PostgreSQL (formato: postgresql://user:pass@host:port/db)
            min_conn: Número mínimo de conexiones en el pool (default: 2)
            max_conn: Número máximo de conexiones en el pool (default: 10)
            
        Raises:
            RuntimeError: Si psycopg no está instalado
            Exception: Si falla la conexión a la base de datos
        
        Note:
            Si el pool ya está inicializado, este método no hace nada.
        """
        
        if psycopg is None or ConnectionPool is None:
            logger.error("psycopg library not installed. Install 'psycopg[binary]' and 'psycopg-pool' in requirements.")
            raise RuntimeError("Missing dependency: psycopg or psycopg-pool")

        if cls._pool is not None:
            logger.info("Database connection pool already initialized, skipping setup")
            return

        try:
            # Guardar string de conexión para uso futuro
            cls._connection_string = database_url
            
            # Crear ThreadPoolExecutor para ejecutar operaciones síncronas de BD
            cls._thread_pool = ThreadPoolExecutor(max_workers=max_conn, thread_name_prefix="db_worker")
            
            # Crear pool de conexiones (síncrono)
            cls._pool = ConnectionPool(
                database_url,
                min_size=min_conn,
                max_size=max_conn,
                timeout=30  # Timeout de 30 segundos para obtener conexión
            )
            
            # Verificar conectividad con una consulta de prueba
            with cls._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if not result or result[0] != 1:
                        raise RuntimeError("Database ping failed")

            logger.info(f"Conexión a PostgreSQL verificada correctamente (pool: {min_conn}-{max_conn})")
        except Exception as e:
            logger.exception("Error conectando a PostgreSQL")
            cls._connection_string = None
            cls._pool = None
            if cls._thread_pool:
                cls._thread_pool.shutdown(wait=False)
                cls._thread_pool = None
            raise

    @classmethod
    def close_database_connection(cls):
        """Cerrar el pool de conexiones y el ThreadPoolExecutor."""
        if cls._pool:
            logger.info("Cerrando pool de conexiones a PostgreSQL")
            cls._pool.close()
            cls._pool = None
        
        if cls._thread_pool:
            logger.info("Cerrando ThreadPoolExecutor")
            cls._thread_pool.shutdown(wait=True)
            cls._thread_pool = None
            
        cls._connection_string = None

    @classmethod
    @contextmanager
    def get_connection(cls):
        """Context manager para obtener una conexión del pool (síncrono)."""
        if cls._pool is None:
            raise RuntimeError("Database no inicializada. Llama a connect_to_database() en el arranque de la app.")
        
        with cls._pool.connection() as conn:
            yield conn

    @classmethod
    async def execute_query(cls, query: str, params=None):
        """Execute a query asíncronamente usando ThreadPoolExecutor.
        
        Returns:
            Para SELECT/RETURNING: lista de tuplas (rows)
            Para INSERT/UPDATE/DELETE: rowcount
        """
        if cls._pool is None or cls._thread_pool is None:
            raise RuntimeError("Database no inicializada")
        
        def _execute():
            with cls.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params or ())
                    query_upper = query.strip().upper()
                    
                    if query_upper.startswith("SELECT") or "RETURNING" in query_upper:
                        result = cur.fetchall()
                        # Commit if it's an INSERT/UPDATE/DELETE with RETURNING
                        if "RETURNING" in query_upper:
                            conn.commit()
                        return result
                    
                    conn.commit()
                    return cur.rowcount
        
        # Run in thread pool to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(cls._thread_pool, _execute)

    @classmethod
    async def ping(cls) -> bool:
        """Return True if DB responds to a simple SELECT 1."""
        if cls._pool is None or cls._thread_pool is None:
            return False
        
        def _ping():
            try:
                with cls.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        result = cur.fetchone()
                        return bool(result and result[0] == 1)
            except Exception:
                return False
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(cls._thread_pool, _ping)


# ---------------------------------------------------------------------------
# Synchronous helper for existing sync code (extractors / legacy scripts)
# ---------------------------------------------------------------------------
from app.config import settings


@contextmanager
def get_db_connection(database_url: Optional[str] = None):
    """Context manager that yields a synchronous DB connection.

    It prefers (in order): explicit database_url argument, the stored
    DatabaseConnection._connection_string set at app startup, or
    `settings.database_url` loaded from the environment.

    This helper uses `psycopg.connect(...)` (sync) so existing synchronous
    code can continue to work without large refactors.
    """

    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Install 'psycopg[binary]'")

    url = database_url or DatabaseConnection._connection_string or getattr(settings, "database_url", None)
    if not url:
        raise RuntimeError("Database URL no configurada. Establece DATABASE_URL en el .env o pasa database_url al helper.")

    conn = psycopg.connect(url)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            logger.debug("Error cerrando la conexión sincrónica (ignorado)", exc_info=True)