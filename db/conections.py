import os
from contextlib import contextmanager
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.exc import DBAPIError, OperationalError

load_dotenv()

Base = declarative_base()


class DatabaseDEV:
    @staticmethod
    def build_uri() -> str:
        engine_type = os.getenv("DB_TYPE", "postgresql").lower()
        user = os.getenv("DB_USER_DEV", "")
        password = os.getenv("DB_PASSWORD_DEV", "")
        host = os.getenv("DB_HOST_DEV", "localhost")
        port = os.getenv("DB_PORT_DEV", "")
        db_name = os.getenv("DB_NAME_DEV", "")

        if engine_type == "postgresql":
            # Requiere driver: psycopg2 o psycopg
            port = port or "5432"
            return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

        elif engine_type == "mysql":
            # Requiere driver: pymysql o mysqlconnector
            port = port or "3306"
            return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"

        elif engine_type == "mssql":
            # Requiere driver: pyodbc
            port = port or "1433"
            driver = "ODBC+Driver+17+for+SQL+Server"
            return f"mssql+pyodbc://{user}:{password}@{host}:{port}/{db_name}?driver={driver}"

        else:
            raise ValueError(f"Motor de base de datos '{engine_type}' no soportado.")

class DatabaseQA:
    @staticmethod
    def build_uri() -> str:
        engine_type = os.getenv("DB_TYPE", "postgresql").lower()
        user = os.getenv("DB_USER_QA", "")
        password = os.getenv("DB_PASSWORD_QA", "")
        host = os.getenv("DB_HOST_QA", "localhost")
        port = os.getenv("DB_PORT_QA", "")
        db_name = os.getenv("DB_NAME_QA", "")

        if engine_type == "postgresql":
            # Requiere driver: psycopg2 o psycopg
            port = port or "5432"
            return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"

        elif engine_type == "mysql":
            # Requiere driver: pymysql o mysqlconnector
            port = port or "3306"
            return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db_name}"

        elif engine_type == "mssql":
            # Requiere driver: pyodbc
            port = port or "1433"
            driver = "ODBC+Driver+17+for+SQL+Server"
            return f"mssql+pyodbc://{user}:{password}@{host}:{port}/{db_name}?driver={driver}"

        else:
            raise ValueError(f"Motor de base de datos '{engine_type}' no soportado.")

#Clase conexion DB DEV
class DatabaseManagerDev:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManagerDev, cls).__new__(cls)
            cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        database_uri = DatabaseDEV.build_uri()

        pool_size = int(os.getenv("DB_POOL_SIZE", 10))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", 20))
        pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", 30))
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE", 1800)) 

        self.engine = create_engine(
            database_uri,
            # CONFIGURACIÓN CLAVE PARA EVITAR CONEXIONES HUÉRFANAS Y MUERTAS
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle, 
            pool_pre_ping=True, 
        )

        self.SessionFactory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session = self.SessionFactory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def dispose_pool(self):
        self.engine.dispose()


#Clase conexion DB QA
class DatabaseManagerQA:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManagerQA, cls).__new__(cls)
            cls._instance._init_engine()
        return cls._instance

    def _init_engine(self):
        database_uri = DatabaseQA.build_uri()

        pool_size = int(os.getenv("DB_POOL_SIZE", 10))
        max_overflow = int(os.getenv("DB_MAX_OVERFLOW", 20))
        pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", 30))
        pool_recycle = int(os.getenv("DB_POOL_RECYCLE", 1800)) 

        self.engine = create_engine(
            database_uri,
            # CONFIGURACIÓN CLAVE PARA EVITAR CONEXIONES HUÉRFANAS Y MUERTAS
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle, 
            pool_pre_ping=True, 
        )

        self.SessionFactory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        session = self.SessionFactory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def dispose_pool(self):
        self.engine.dispose()