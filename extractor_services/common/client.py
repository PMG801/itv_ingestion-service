"""
Cliente HTTP para comunicación con la API Central.
Usado por todos los servicios extractores.
"""
import httpx
import logging
from typing import Optional
from .schemas import PayloadExtraccion, IngestResponse

logger = logging.getLogger(__name__)


class CentralAPIClient:
    """Cliente para comunicación con la API Central"""
    
    def __init__(self, base_url: str, timeout: int = 60):
        """
        Inicializa el cliente.
        
        Args:
            base_url: URL base de la API central (ej: http://localhost:8000)
            timeout: Timeout en segundos para las peticiones
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.ingest_endpoint = f"{self.base_url}/api/ingest/"
    
    async def enviar_payload(self, payload: PayloadExtraccion) -> IngestResponse:
        """
        Envía el payload de extracción a la API central.
        
        Args:
            payload: PayloadExtraccion con los datos transformados
            
        Returns:
            IngestResponse con el resultado de la operación
            
        Raises:
            httpx.HTTPError: Si hay error en la comunicación
            ValueError: Si la respuesta no es válida
        """
        logger.info(f"📤 Enviando {len(payload.estaciones)} estaciones a API central: {self.ingest_endpoint}")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.ingest_endpoint,
                    json=payload.model_dump(mode="json"),
                    headers={"Content-Type": "application/json"}
                )
                
                response.raise_for_status()
                
                data = response.json()
                result = IngestResponse(**data)
                
                logger.info(f"✅ Respuesta de API central: {result.status} - {result.mensaje}")
                return result
                
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Error HTTP de API central: {e.response.status_code} - {e.response.text}")
                raise
            except httpx.RequestError as e:
                logger.error(f"❌ Error de conexión con API central: {e}")
                raise
            except Exception as e:
                logger.error(f"❌ Error inesperado: {e}")
                raise
    
    async def health_check(self) -> bool:
        """
        Verifica que la API central esté disponible.
        
        Returns:
            True si la API está disponible, False en caso contrario
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/")
                return response.status_code == 200
        except Exception as e:
            logger.warning(f"⚠️ API central no disponible: {e}")
            return False


def create_client(base_url: str, timeout: int = 60) -> CentralAPIClient:
    """
    Factory function para crear un cliente de API central.
    
    Args:
        base_url: URL base de la API central
        timeout: Timeout en segundos
        
    Returns:
        Instancia de CentralAPIClient
    """
    return CentralAPIClient(base_url=base_url, timeout=timeout)
