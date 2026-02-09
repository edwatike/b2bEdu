"""Utilities for compressing and decompressing Checko data."""
import gzip
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def compress_checko_data(data: Dict[str, Any]) -> bytes:
    """Compress Checko data using gzip.
    
    Args:
        data: Dictionary containing Checko data
        
    Returns:
        Compressed bytes (gzip)
        
    Raises:
        ValueError: If data cannot be serialized to JSON
    """
    try:
        # Serialize to JSON string
        json_str = json.dumps(data, ensure_ascii=False)
        
        # Compress using gzip
        compressed = gzip.compress(json_str.encode('utf-8'))
        
        logger.debug(f"Compressed Checko data: {len(json_str)} bytes -> {len(compressed)} bytes "
                    f"({100 * (1 - len(compressed) / len(json_str)):.1f}% reduction)")
        
        return compressed
    except (TypeError, ValueError) as e:
        logger.error(f"Failed to compress Checko data: {e}")
        raise ValueError(f"Cannot serialize Checko data to JSON: {e}")


def decompress_checko_data(compressed: bytes) -> Dict[str, Any]:
    """Decompress Checko data from gzip.
    
    Args:
        compressed: Compressed bytes (gzip)
        
    Returns:
        Dictionary containing Checko data
        
    Raises:
        ValueError: If data cannot be decompressed or parsed
    """
    try:
        # Decompress from gzip
        json_str = gzip.decompress(compressed).decode('utf-8')
        
        # Parse JSON
        data = json.loads(json_str)
        
        logger.debug(f"Decompressed Checko data: {len(compressed)} bytes -> {len(json_str)} bytes")
        
        return data
    except (gzip.BadGzipFile, UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.error(f"Failed to decompress Checko data: {e}")
        raise ValueError(f"Cannot decompress or parse Checko data: {e}")


def compress_checko_data_string(data_str: str) -> bytes:
    """Compress Checko data string using gzip.
    
    Args:
        data_str: JSON string containing Checko data
        
    Returns:
        Compressed bytes (gzip)
        
    Raises:
        ValueError: If data_str is not valid JSON
    """
    try:
        # Validate JSON by parsing
        json.loads(data_str)
        
        # Compress
        compressed = gzip.compress(data_str.encode('utf-8'))
        
        logger.debug(f"Compressed Checko data string: {len(data_str)} bytes -> {len(compressed)} bytes "
                    f"({100 * (1 - len(compressed) / len(data_str)):.1f}% reduction)")
        
        return compressed
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in Checko data string: {e}")
        raise ValueError(f"Invalid JSON string: {e}")


def decompress_checko_data_to_string(compressed: bytes) -> str:
    """Decompress Checko data from gzip to JSON string.
    
    Args:
        compressed: Compressed bytes (gzip)
        
    Returns:
        JSON string containing Checko data
        
    Raises:
        ValueError: If data cannot be decompressed
    """
    try:
        # Decompress from gzip
        json_str = gzip.decompress(compressed).decode('utf-8')
        
        # Validate JSON by parsing
        json.loads(json_str)
        
        logger.debug(f"Decompressed Checko data to string: {len(compressed)} bytes -> {len(json_str)} bytes")
        
        return json_str
    except (gzip.BadGzipFile, UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.error(f"Failed to decompress Checko data string: {e}")
        raise ValueError(f"Cannot decompress Checko data: {e}")







