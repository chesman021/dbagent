import logging
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


# --- Excepciones de Dominio ---
class DatabaseInspectorError(Exception):
    """Excepción base para errores en la inspección de base de datos."""


class DBObjectNotFoundError(DatabaseInspectorError):
    """Lanzada cuando un objeto de base de datos no existe."""


class DBObjectMetadata(BaseModel):
    """Representa los metadatos y código DDL de un objeto de base de datos."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(..., description="Nombre del objeto en la BD")
    schema_name: str = Field(default="public", description="Esquema donde reside")
    object_type: str = Field(..., description="Tipo de objeto (TRIGGER, PROCEDURE, FUNCTION, TYPE)")
    definition: Optional[str] = Field(None, description="Código fuente DDL del objeto")


class DatabaseInspector:
    """Clase encargada de inspeccionar la estructura y extraer DDLs de la base de datos."""

    def __init__(self, session: AsyncSession) -> None:
        """Inicializa el inspector con una sesión asíncrona de SQLAlchemy.

        Args:
            session (AsyncSession): Sesión activa de base de datos.
        """
        self._session = session

    async def get_stored_procedure(
        self, name: str, schema_name: str = "public"
    ) -> DBObjectMetadata:
        """Obtiene la definición de un Stored Procedure específico.

        Args:
            name (str): Nombre del Stored Procedure.
            schema_name (str): Esquema de la base de datos. Por defecto 'public'.

        Returns:
            DBObjectMetadata: Objeto con la metadata y DDL del procedimiento.

        Raises:
            DBObjectNotFoundError: Si el procedimiento no existe.
            DatabaseInspectorError: Si ocurre un error de ejecución en la consulta.
        """
        query = text(
            """
            SELECT routine_name AS name, routine_schema AS schema_name, routine_definition AS definition
            FROM information_schema.routines
            WHERE routine_type = 'PROCEDURE' 
              AND routine_name = :name 
              AND routine_schema = :schema_name
            """
        )
        try:
            result = await self._session.execute(
                query, {"name": name, "schema_name": schema_name}
            )
            row = result.mappings().first()

            if not row:
                raise DBObjectNotFoundError(
                    f"Stored Procedure '{schema_name}.{name}' no fue encontrado."
                )

            return DBObjectMetadata(
                name=row["name"],
                schema_name=row["schema_name"],
                object_type="PROCEDURE",
                definition=row["definition"],
            )
        except SQLAlchemyError as exc:
            logger.error("Error consultando Stored Procedure %s: %s", name, exc)
            raise DatabaseInspectorError("Error al consultar la base de datos") from exc

    async def get_stored_procedures(
        self, schema_name: str = "public"
    ) -> List[DBObjectMetadata]:
        """Obtiene el listado de todos los Stored Procedures en el esquema.

        Args:
            schema_name (str): Esquema a consultar.

        Returns:
            List[DBObjectMetadata]: Lista de metadatos de los procedimientos encontrados.
        """
        query = text(
            """
            SELECT routine_name AS name, routine_schema AS schema_name
            FROM information_schema.routines
            WHERE routine_type = 'PROCEDURE' AND routine_schema = :schema_name
            """
        )
        try:
            result = await self._session.execute(query, {"schema_name": schema_name})
            rows = result.mappings().all()
            return [
                DBObjectMetadata(
                    name=r["name"],
                    schema_name=r["schema_name"],
                    object_type="PROCEDURE",
                )
                for r in rows
            ]
        except SQLAlchemyError as exc:
            logger.error("Error consultando Stored Procedures: %s", exc)
            raise DatabaseInspectorError("Error al listar los procedimientos") from exc

    async def get_triggers(self, schema_name: str = "public") -> List[DBObjectMetadata]:
        """Obtiene todos los triggers definidos en el esquema especificado."""
        query = text(
            """
            SELECT trigger_name AS name, trigger_schema AS schema_name
            FROM information_schema.triggers
            WHERE trigger_schema = :schema_name
            """
        )
        try:
            result = await self._session.execute(query, {"schema_name": schema_name})
            return [
                DBObjectMetadata(
                    name=r["name"],
                    schema_name=r["schema_name"],
                    object_type="TRIGGER",
                )
                for r in result.mappings().all()
            ]
        except SQLAlchemyError as exc:
            raise DatabaseInspectorError("Error al listar triggers") from exc