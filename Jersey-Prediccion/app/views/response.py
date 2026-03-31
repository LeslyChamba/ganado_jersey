# app/views/response.py
"""
CAPA VISTA
Estandariza todas las respuestas JSON del sistema.
Todos los controladores usan estas funciones para devolver datos.
"""
from typing import Any, Optional
from fastapi.responses import JSONResponse


def success(data: Any, message: str = "OK", status_code: int = 200) -> JSONResponse:
    """Respuesta exitosa estándar."""
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "success",
            "message": message,
            "data": _serialize(data),
        },
    )


def created(data: Any, message: str = "Recurso creado") -> JSONResponse:
    return success(data, message, status_code=201)


def error(message: str, status_code: int = 400, detail: Optional[Any] = None) -> JSONResponse:
    """Respuesta de error estándar."""
    body = {"status": "error", "message": message}
    if detail is not None:
        body["detail"] = detail
    return JSONResponse(status_code=status_code, content=body)


def not_found(resource: str = "Recurso") -> JSONResponse:
    return error(f"{resource} no encontrado", status_code=404)


def paginated(
    data: list[Any],
    total: int,
    page: int,
    page_size: int,
    message: str = "OK",
) -> JSONResponse:
    """Respuesta paginada."""
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": message,
            "data": _serialize(data),
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": max(1, -(-total // page_size)),  # ceil division
            },
        },
    )


def _serialize(obj: Any) -> Any:
    """Convierte Pydantic models, datetimes, etc. a tipos JSON serializables."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj
