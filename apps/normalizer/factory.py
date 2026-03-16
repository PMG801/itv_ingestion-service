"""
Transformer Factory - Strategy Pattern implementation.

This module provides a factory for creating appropriate transformers
based on the data source system.
"""

import logging
from typing import List

from domain.itv_stations.transformers.base import BaseTransformer
from domain.itv_stations.transformers.catalunya import CatalunyaTransformer
from domain.itv_stations.transformers.valencia import ValenciaTransformer
from domain.itv_stations.transformers.galicia import GaliciaTransformer

logger = logging.getLogger(__name__)


class TransformerFactory:
    """
    Factory for instantiating transformers based on source_system.
    
    Implements the Strategy Pattern - selects the appropriate
    transformation strategy at runtime based on the data source.
    
    This design follows the Open/Closed Principle: the system is open
    for extension (adding new transformers) but closed for modification
    (no need to change existing code).
    
    Example:
        >>> factory = TransformerFactory()
        >>> transformer = factory.create("catalunya")
        >>> normalized_data = transformer.transform(raw_xml)
    """
    
    # Registry of available transformers
    _transformers = {
        "catalunya": CatalunyaTransformer,
        "valencia": ValenciaTransformer,
        "galicia": GaliciaTransformer,
    }
    
    @classmethod
    def create(cls, source_system: str) -> BaseTransformer:
        """
        Create transformer for the given source system.
        
        Args:
            source_system: Source identifier (catalunya, valencia, galicia).
                Case-insensitive.
                
        Returns:
            BaseTransformer instance for the specified source.
            
        Raises:
            ValueError: If source_system is not supported.
            
        Example:
            >>> transformer = TransformerFactory.create("catalunya")
            >>> isinstance(transformer, CatalunyaTransformer)
            True
        """
        source_lower = source_system.lower().strip()
        
        transformer_class = cls._transformers.get(source_lower)
        
        if not transformer_class:
            supported = ", ".join(cls._transformers.keys())
            error_msg = (
                f"Unsupported source system: '{source_system}'. "
                f"Supported sources: {supported}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        logger.debug(f"Creating transformer for source: {source_lower}")
        return transformer_class()
    
    @classmethod
    def supported_sources(cls) -> List[str]:
        """
        Get list of supported source systems.
        
        Returns:
            List of source system identifiers.
            
        Example:
            >>> TransformerFactory.supported_sources()
            ['catalunya', 'valencia', 'galicia']
        """
        return list(cls._transformers.keys())
    
    @classmethod
    def register_transformer(
        cls,
        source_system: str,
        transformer_class: type[BaseTransformer]
    ) -> None:
        """
        Register a new transformer for a source system.
        
        This method allows dynamic registration of new transformers
        without modifying the factory code, further supporting the
        Open/Closed Principle.
        
        Args:
            source_system: Source identifier (e.g., "madrid", "euskadi").
            transformer_class: Class that inherits from BaseTransformer.
            
        Raises:
            TypeError: If transformer_class doesn't inherit from BaseTransformer.
            
        Example:
            >>> class MadridTransformer(BaseTransformer):
            ...     pass
            >>> TransformerFactory.register_transformer("madrid", MadridTransformer)
            >>> "madrid" in TransformerFactory.supported_sources()
            True
        """
        # Validate that the class is a subclass of BaseTransformer
        if not issubclass(transformer_class, BaseTransformer):
            raise TypeError(
                f"{transformer_class.__name__} must inherit from BaseTransformer"
            )
        
        source_lower = source_system.lower().strip()
        
        if source_lower in cls._transformers:
            logger.warning(
                f"Overwriting existing transformer for source: {source_lower}"
            )
        
        cls._transformers[source_lower] = transformer_class
        logger.info(f"Registered transformer for source: {source_lower}")
    
    @classmethod
    def is_supported(cls, source_system: str) -> bool:
        """
        Check if a source system is supported.
        
        Args:
            source_system: Source identifier to check.
            
        Returns:
            True if supported, False otherwise.
            
        Example:
            >>> TransformerFactory.is_supported("catalunya")
            True
            >>> TransformerFactory.is_supported("madrid")
            False
        """
        return source_system.lower().strip() in cls._transformers
