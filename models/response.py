from decimal import Decimal
import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Union
from uuid import UUID


class JSONEncoderResponse(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj) 
        if isinstance(obj, UUID):
            return str(obj)
        if hasattr(obj, "_mapping"):
            return dict(obj._mapping)
        return super().default(obj)


class Response:
    @staticmethod
    def _build_response(
        success: bool,
        status_code: int,
        message: str,
        data: Optional[Union[Dict, List, Any]] = None,
        errors: Optional[Union[Dict, List, str]] = None,
    ) -> Dict[str, Any]:
        """Estructura base del diccionario de respuesta."""
        return {
            "success": success,
            "status_code": status_code,
            "message": message,
            "data": data if data is not None else ([] if isinstance(data, list) else {}),
            "errors": errors,
        }

    @classmethod
    def success(
        cls,
        data: Optional[Union[Dict, List, Any]] = None,
        message: str = "Operación exitosa",
        status_code: int = 200,
    ) -> Dict[str, Any]:
        return cls._build_response(
            success=True,
            status_code=status_code,
            message=message,
            data=data,
            errors=None,
        )

    @classmethod
    def error(
        cls,
        message: str = "Ocurrió un error en la petición",
        errors: Optional[Union[Dict, List, str]] = None,
        status_code: int = 400,
        data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        return cls._build_response(
            success=False,
            status_code=status_code,
            message=message,
            data=data,
            errors=errors,
        )

    @classmethod
    def server_error(
        cls,
        message: str = "Error interno del servidor",
        errors: Optional[Union[Dict, List, str]] = None,
    ) -> Dict[str, Any]:
        return cls.error(message=message, errors=errors, status_code=500)

    @staticmethod
    def to_json(payload: Dict[str, Any]) -> str:
        return json.dumps(payload, cls=JSONEncoderResponse, ensure_ascii=False)