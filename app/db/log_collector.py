"""
Log Collector - Sistema de recopilación de logs para la API de carga
Permite capturar y devolver logs detallados al frontend
"""

from typing import List, Dict, Any
from enum import Enum
from datetime import datetime


class LogLevel(str, Enum):
    """Niveles de log"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    SUCCESS = "success"


class LogEntry:
    """Representa un entrada de log individual"""
    
    def __init__(self, level: LogLevel, message: str, details: Dict[str, Any] = None):
        self.level = level
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario"""
        return {
            "level": self.level.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


class LogCollector:
    """
    Recopila logs durante el proceso de carga.
    
    Ejemplo de uso:
    ```
    logs = LogCollector()
    logs.info("Iniciando carga")
    logs.success("Estación cargada", {"estacion_nombre": "Estación A"})
    logs.error("Error al cargar", {"estacion": "Estación B", "razon": "CP fuera de rango"})
    
    resumen = logs.get_summary()
    """
    
    def __init__(self):
        self.entries: List[LogEntry] = []
        self.stats = {
            "total": 0,
            "exitosos": 0,
            "fallidos": 0,
            "advertencias": 0
        }
    
    def info(self, message: str, details: Dict[str, Any] = None):
        """Registra un mensaje de información"""
        entry = LogEntry(LogLevel.INFO, message, details)
        self.entries.append(entry)
    
    def success(self, message: str, details: Dict[str, Any] = None):
        """Registra un mensaje de éxito"""
        entry = LogEntry(LogLevel.SUCCESS, message, details)
        self.entries.append(entry)
        self.stats["exitosos"] += 1
        self.stats["total"] += 1
    
    def warning(self, message: str, details: Dict[str, Any] = None):
        """Registra un mensaje de advertencia"""
        entry = LogEntry(LogLevel.WARNING, message, details)
        self.entries.append(entry)
        self.stats["advertencias"] += 1
    
    def error(self, message: str, details: Dict[str, Any] = None):
        """Registra un mensaje de error"""
        entry = LogEntry(LogLevel.ERROR, message, details)
        self.entries.append(entry)
        self.stats["fallidos"] += 1
        self.stats["total"] += 1
    
    def get_entries(self) -> List[Dict[str, Any]]:
        """Devuelve todas las entradas de log"""
        return [entry.to_dict() for entry in self.entries]
    
    def get_summary(self) -> Dict[str, Any]:
        """Devuelve resumen de los logs"""
        return {
            "stats": self.stats,
            "logs": self.get_entries()
        }
    
    def get_errors(self) -> List[Dict[str, Any]]:
        """Devuelve solo los errores"""
        return [
            entry.to_dict()
            for entry in self.entries
            if entry.level == LogLevel.ERROR
        ]
    
    def get_successes(self) -> List[Dict[str, Any]]:
        """Devuelve solo los éxitos"""
        return [
            entry.to_dict()
            for entry in self.entries
            if entry.level == LogLevel.SUCCESS
        ]
    
    def format_for_textarea(self) -> str:
        """
        Formatea los logs para mostrar en un textarea en el frontend.
        
        Ejemplo:
        ```
        ✅ 45 registros cargados correctamente
        ❌ 2 fallidos
        
        Errores:
        ❌ Error carga registro 5: Código postal fuera de rango (CP: 99999)
        ❌ Error carga registro 12: FK error - Localidad no existe (municipio: XYZ)
        ```
        """
        lines = []
        
        # Encabezado con resumen
        lines.append("=" * 60)
        lines.append(f"✅ {self.stats['exitosos']} registros cargados correctamente")
        if self.stats['fallidos'] > 0:
            lines.append(f"❌ {self.stats['fallidos']} fallidos")
        if self.stats['advertencias'] > 0:
            lines.append(f"⚠️ {self.stats['advertencias']} advertencias")
        lines.append("=" * 60)
        lines.append("")
        
        # Errores detallados
        errors = self.get_errors()
        if errors:
            lines.append("ERRORES:")
            for i, error in enumerate(errors, 1):
                lines.append(f"")
                lines.append(f"❌ {error['message']}")
                for key, value in error['details'].items():
                    lines.append(f"   {key}: {value}")
        
        # Advertencias
        warnings = [e for e in self.entries if e.level == LogLevel.WARNING]
        if warnings:
            lines.append("")
            lines.append("ADVERTENCIAS:")
            for warning in warnings:
                lines.append(f"⚠️ {warning.message}")
                for key, value in warning.details.items():
                    lines.append(f"   {key}: {value}")
        
        return "\n".join(lines)
