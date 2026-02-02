"""FastAPI application entry point."""
import sys
import os

# CRITICAL: Ensure backend directory is in Python path for uvicorn reload mode
# When uvicorn runs with reload=True and import string, it spawns a new process
# that needs to have the correct Python path to import modules
# This is a safety measure in case PYTHONPATH is not set correctly
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from dotenv import load_dotenv
load_dotenv(os.path.join(_backend_dir, ".env"))

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
import traceback
from sqlalchemy import text

from app.config import settings
from app.logging_config import setup_logging, log_service_event, get_logger
from app.adapters.db.session import AsyncSessionLocal
from app.transport.routers import (
    health,
    moderator_suppliers,
    moderator_users,
    keywords,
    blacklist,
    parsing,
    parsing_runs,
    domains_queue,
    attachments,
    checko,
    domain_parser,
    learning,
    auth,
    cabinet,
    mail,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Setup structured logging
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
    log_structured = getattr(settings, 'ENV', 'development') == 'production'
    log_file = getattr(settings, 'LOG_FILE', None)
    
    setup_logging(
        level=log_level,
        structured=log_structured,
        log_file=log_file
    )
    
    # Log startup event
    log_service_event(
        event_type="startup",
        service="backend",
        message="B2B Platform Backend starting up",
        port=8000,
        version="1.0.0"
    )

    # Ensure DB schema is compatible with encrypted integration keys.
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS openai_api_key_encrypted TEXT"))
            await db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS groq_api_key_encrypted TEXT"))
            await db.commit()
    except Exception as e:
        logger = get_logger("db")
        logger.warning(f"DB schema check failed (openai_api_key_encrypted): {type(e).__name__}: {e}")
    
    yield
    # Shutdown
    log_service_event(
        event_type="shutdown", 
        service="backend",
        message="B2B Platform Backend shutting down"
    )


app = FastAPI(
    title="B2B Platform API",
    version="1.0.0",
    description="API for B2B Platform - supplier moderation and parsing system",
    lifespan=lifespan,
)

# CRITICAL: Verify app is created correctly
logger = get_logger(__name__)
logger.info("FastAPI app instance created", extra={"app_id": id(app)})

# Log CORS configuration
logger.info("CORS configured", extra={
    "origins": settings.cors_origins_list,
    "app_id": id(app)
})

# Добавляем обработчик ошибок на уровне Starlette
from starlette.requests import Request as StarletteRequest

async def starlette_exception_handler(request: StarletteRequest, exc: Exception):
    """Starlette-level exception handler."""
    logger = get_logger(__name__)
    logger.error("Starlette exception", extra={
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "path": str(request.url.path) if hasattr(request, 'url') else None
    }, exc_info=True)
    
    error_detail = f"{type(exc).__name__}: {str(exc)}"
    if settings.ENV == "development":
        error_detail += f"\n{traceback.format_exc()}"
    
    response = JSONResponse(
        status_code=500,
        content={"detail": error_detail}
    )
    
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

# Добавляем обработчик на уровне Starlette
app.add_exception_handler(Exception, starlette_exception_handler)

# CORS Middleware - должен быть первым
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Ngrok bypass middleware - добавляем заголовки для обхода ngrok warning
class NgrokBypassMiddleware(BaseHTTPMiddleware):
    """Middleware to bypass ngrok browser warning by adding required headers."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Добавляем заголовки для обхода ngrok warning ко всем ответам
        response.headers["ngrok-skip-browser-warning"] = "true"
        
        return response

app.add_middleware(NgrokBypassMiddleware)

# Middleware для обработки ошибок с CORS
from starlette.responses import Response
import json

class CORSExceptionMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления CORS заголовков к ошибкам."""
    async def dispatch(self, request, call_next):
        import logging
        logger = logging.getLogger(__name__)
        
        # DEBUG: Log all requests to /parsing/runs/*/logs
        if "/parsing/runs" in str(request.url.path) and "/logs" in str(request.url.path):
            logger.info(f"[DEBUG MIDDLEWARE] Request to: {request.method} {request.url.path}")
            logger.info(f"[DEBUG MIDDLEWARE] Request scope path: {request.scope.get('path', 'N/A')}")
            logger.info(f"[DEBUG MIDDLEWARE] Request scope method: {request.scope.get('method', 'N/A')}")
        
        # DEBUG: Log INN extraction requests
        if "/inn-extraction" in str(request.url.path):
            logger.info(f"[DEBUG MIDDLEWARE] INN extraction request: {request.method} {request.url.path}")
            logger.info(f"[DEBUG MIDDLEWARE] Available routes: {[r.path for r in app.routes if hasattr(r, 'path')][:10]}")
        
        try:
            response = await call_next(request)
            
            # DEBUG: Log response for /parsing/runs/*/logs
            if "/parsing/runs" in str(request.url.path) and "/logs" in str(request.url.path):
                logger.info(f"[DEBUG MIDDLEWARE] Response status: {response.status_code}")
                logger.info(f"[DEBUG MIDDLEWARE] Response headers: {dict(response.headers)}")
            
            # Убедимся, что CORS заголовки есть даже при ошибках
            origin = request.headers.get("origin")
            if origin and origin in settings.cors_origins_list:
                if "Access-Control-Allow-Origin" not in response.headers:
                    response.headers["Access-Control-Allow-Origin"] = origin
                    response.headers["Access-Control-Allow-Credentials"] = "true"
                    response.headers["Access-Control-Allow-Methods"] = "*"
                    response.headers["Access-Control-Allow-Headers"] = "*"
            return response
        except Exception as exc:
            import traceback
            # Безопасное логирование - оборачиваем в try-except
            try:
                logger.error(f"Exception in middleware: {type(exc).__name__}: {exc}", exc_info=True)
            except Exception:
                pass  # Если логирование не работает, просто пропускаем
            
            # Обработка исключений на уровне middleware
            
            error_detail = f"{type(exc).__name__}: {str(exc)}"
            if settings.ENV == "development":
                error_detail += f"\n{traceback.format_exc()}"
            
            response = JSONResponse(
                status_code=500,
                content={"detail": error_detail}
            )
            
            origin = request.headers.get("origin")
            if origin and origin in settings.cors_origins_list:
                response.headers["Access-Control-Allow-Origin"] = origin
                response.headers["Access-Control-Allow-Credentials"] = "true"
                response.headers["Access-Control-Allow-Methods"] = "*"
                response.headers["Access-Control-Allow-Headers"] = "*"
            
            return response

app.add_middleware(CORSExceptionMiddleware)

# Ngrok warning bypass middleware
class NgrokWarningMiddleware(BaseHTTPMiddleware):
    """Middleware to bypass ngrok browser warning."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        
        # Check if this is an ngrok request
        if "ngrok" in request.headers.get("host", ""):
            # Add headers to bypass ngrok warning
            response.headers["ngrok-skip-browser-warning"] = "true"
        
        return response

app.add_middleware(NgrokWarningMiddleware)

# Global exception handler for debugging - ДОЛЖЕН быть ДО включения роутеров!
from fastapi.exceptions import HTTPException as FastAPIHTTPException

@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    """HTTP exception handler with CORS headers."""
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
    
    # Add CORS headers manually
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler to log errors and return details with CORS headers."""
    import logging
    logger = logging.getLogger(__name__)
    # Безопасное логирование - оборачиваем в try-except
    try:
        logger.error(f"Global exception handler called: {type(exc).__name__}: {exc}", exc_info=True)
    except Exception:
        pass  # Если логирование не работает, просто пропускаем
    
    error_detail = f"{type(exc).__name__}: {str(exc)}"
    if settings.ENV == "development":
        error_detail += f"\n{traceback.format_exc()}"
    
    # Create response with CORS headers
    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": error_detail}
    )
    
    # Add CORS headers manually
    origin = request.headers.get("origin")
    if origin and origin in settings.cors_origins_list:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "B2B Platform API",
        "version": "1.0.0",
        "description": "API for B2B Platform - supplier moderation and parsing system",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "suppliers": "/moderator/suppliers",
            "keywords": "/keywords",
            "blacklist": "/moderator/blacklist",
            "parsing": "/parsing",
            "parsing_runs": "/parsing/runs",
            "domains_queue": "/domains",
            "attachments": "/attachments",
        }
    }

@app.get("/debug/routes")
async def debug_routes():
    """Debug endpoint to check route registration."""
    from fastapi.routing import APIRoute
    routes_info = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            if '/parsing/runs' in route.path and 'logs' in route.path:
                routes_info.append({
                    "path": route.path,
                    "methods": list(route.methods),
                    "name": getattr(route, 'name', None),
                    "endpoint": route.endpoint.__name__ if hasattr(route, 'endpoint') else None
                })
    return {"logs_routes": routes_info, "total_routes": len(app.routes)}

@app.get("/debug/all-routes")
async def debug_all_routes():
    """Debug endpoint to check all registered routes."""
    from fastapi.routing import APIRoute
    routes_info = []
    for route in app.routes:
        if isinstance(route, APIRoute):
            routes_info.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": getattr(route, 'name', None),
                "endpoint": route.endpoint.__name__ if hasattr(route, 'endpoint') else None
            })
    # Filter INN extraction routes
    inn_routes = [r for r in routes_info if 'inn' in r['path'].lower()]
    return {
        "total_routes": len(routes_info),
        "inn_routes": inn_routes,
        "all_routes": routes_info
    }


# Include routers
logger.info("Starting router registration")

try:
    logger.info("Registering health router")
    app.include_router(health.router, tags=["Health"])
    
    logger.info("Registering moderator suppliers router")
    app.include_router(moderator_suppliers.router, prefix="/moderator", tags=["Suppliers"])

    logger.info("Registering moderator users router")
    app.include_router(moderator_users.router, prefix="/moderator", tags=["Users"])
    
    logger.info("Registering keywords router")
    app.include_router(keywords.router, prefix="/keywords", tags=["Keywords"])
    
    logger.info("Registering blacklist router")
    app.include_router(blacklist.router, prefix="/moderator", tags=["Blacklist"])
    
    logger.info("Registering parsing runs router")
    app.include_router(parsing_runs.router, prefix="/parsing", tags=["Parsing Runs"])
    
    logger.info("Registering parsing router")
    app.include_router(parsing.router, prefix="/parsing", tags=["Parsing"])
    
    logger.info("Registering domains queue router")
    app.include_router(domains_queue.router, prefix="/domains", tags=["Domains Queue"])
    
    logger.info("Registering attachments router")
    app.include_router(attachments.router, prefix="/attachments", tags=["Attachments"])
    
    logger.info("Registering checko router")
    app.include_router(checko.router, prefix="/moderator", tags=["Checko"])
    
    logger.info("Registering domain parser router")
    app.include_router(domain_parser.router, prefix="/domain-parser", tags=["Domain Parser"])
    
    if learning is not None:
        logger.info("Registering learning router")
        app.include_router(learning.router, prefix="/learning", tags=["Learning"])
    
    logger.info("Registering auth router")
    app.include_router(auth.router, prefix="/api", tags=["Authentication"])

    logger.info("Registering cabinet router")
    app.include_router(cabinet.router, prefix="/cabinet", tags=["Cabinet"])
    
    logger.info("Registering mail router")
    app.include_router(mail.router, prefix="/api", tags=["Mail"])
    
    # Log registration summary
    from fastapi.routing import APIRoute
    api_routes = [r for r in app.routes if isinstance(r, APIRoute)]
    comet_routes = [r for r in api_routes if '/comet' in r.path]
    
    logger.info("All routers registered successfully", extra={
        "comet_routes": len(comet_routes),
        "comet_paths": [r.path for r in comet_routes],
        "app_id": id(app)
    })
except Exception as e:
    logger.error("Error registering routers", extra={"error": str(e)}, exc_info=True)
    raise

# Final verification after all routers are registered
try:
    from fastapi.routing import APIRoute
    final_routes = [r for r in app.routes if isinstance(r, APIRoute)]
    
    # Check for INN-related routes (checko endpoints)
    inn_routes = [r for r in final_routes if 'checko' in r.path.lower()]
    
    logger.info("Final route verification", extra={
        "total_routes": len(final_routes),
        "inn_checko_routes": len(inn_routes),
        "inn_checko_paths": [r.path for r in inn_routes],
        "app_id": id(app)
    })
    
    if not inn_routes:
        logger.warning("No INN/Checko routes found - this may be expected")
    else:
        logger.info("INN/Checko routes successfully registered")
        
except Exception as e:
    logger.error("Error in final verification", extra={"error": str(e)}, exc_info=True)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

