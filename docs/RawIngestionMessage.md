from pydantic import BaseModel
from typing import Any, Union
from datetime import datetime

class RawIngestionMessage(BaseModel):
    """
    Contrato de Ingestión: Lo que el Gateway lanza a la cola 'itv.raw_data'
    """
    source: str               # 'catalunya', 'valencia', 'galicia'
    payload: Union[dict, str] # El JSON o XML original
    ingested_at: datetime     # Timestamp para trazabilidad
    format: str               # 'json', 'xml', 'csv'