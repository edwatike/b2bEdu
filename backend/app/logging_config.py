"""Structured logging configuration for B2B Platform."""
import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from pathlib import Path


class StructuredFormatter(logging.Formatter):
    """JSON structured formatter for better log analysis."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": "backend",
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add extra fields if present
        if hasattr(record, 'service_name'):
            log_data["service_name"] = record.service_name
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }
        
        return json.dumps(log_data, ensure_ascii=False)


class SimpleFormatter(logging.Formatter):
    """Simple formatter for development with readable output."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with timestamp and module info."""
        timestamp = datetime.utcnow().strftime("%H:%M:%S.%f")[:-3]
        return f"[{timestamp}] {record.levelname:8} | {record.module:20} | {record.getMessage()}"


def setup_logging(
    level: str = "INFO",
    structured: bool = False,
    log_file: str = None
) -> None:
    """Setup logging configuration.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        structured: Use JSON structured logging
        log_file: Optional log file path
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create formatters
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = SimpleFormatter()
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    root_logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        root_logger.addHandler(file_handler)
    
    # Configure specific loggers
    loggers_config = {
        "uvicorn": {"level": logging.WARNING, "propagate": False},
        "uvicorn.access": {"level": logging.WARNING, "propagate": False},
        "starlette": {"level": logging.WARNING, "propagate": False},
        "fastapi": {"level": logging.WARNING, "propagate": False},
        "sqlalchemy.engine": {"level": logging.WARNING, "propagate": False},
        "httpx": {"level": logging.WARNING, "propagate": False},
    }
    
    for logger_name, config in loggers_config.items():
        logger = logging.getLogger(logger_name)
        logger.setLevel(config["level"])
        logger.propagate = config["propagate"]


def get_logger(name: str, **kwargs) -> logging.Logger:
    """Get logger with additional context.
    
    Args:
        name: Logger name
        **kwargs: Additional context fields
        
    Returns:
        Configured logger
    """
    logger = logging.getLogger(name)
    
    # Add context as adapter
    if kwargs:
        return logging.LoggerAdapter(logger, kwargs)
    
    return logger


# Convenience functions for different log levels
def log_service_event(
    event_type: str,
    service: str,
    message: str,
    level: str = "INFO",
    **extra
) -> None:
    """Log service-specific event.
    
    Args:
        event_type: Type of event (startup, shutdown, error, etc.)
        service: Service name
        message: Event message
        level: Log level
        **extra: Additional context
    """
    logger = get_logger("service")
    log_data = {
        "event_type": event_type,
        "service_name": service,
        **extra
    }
    
    getattr(logger, level.lower())(message, extra=log_data)


def log_api_request(
    method: str,
    path: str,
    status_code: int = None,
    duration_ms: float = None,
    **extra
) -> None:
    """Log API request.
    
    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        **extra: Additional context
    """
    logger = get_logger("api")
    log_data = {
        "method": method,
        "path": path,
        "status_code": status_code,
        "duration_ms": duration_ms,
        **extra
    }
    
    message = f"{method} {path}"
    if status_code:
        message += f" -> {status_code}"
    if duration_ms:
        message += f" ({duration_ms:.2f}ms)"
    
    logger.info(message, extra=log_data)
