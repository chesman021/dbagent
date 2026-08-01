import os
import json
import argparse
import difflib
from datetime import datetime
import pyodbc
import pymysql
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# --- CONEXION UNIFICADA ---
def get_connection(env_prefix="DEV"):
    db_type = os.getenv("DB_TYPE", "mssql").lower()
    host = os.getenv(f"{env_prefix}_HOST")
    db = os.getenv(f"{env_prefix}_DB")
    user = os.getenv(f"{env_prefix}_USER")
    password = os.getenv(f"{env_prefix}_PASS")
    port = os.getenv(f"{env_prefix}_PORT")

    if db_type == "mssql":
        conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={host},{port};DATABASE={db};UID={user};PWD={password}"
        return pyodbc.connect(conn_str), db_type
    elif db_type == "mysql":
        conn = pymysql.connect(host=host, user=user, password=password, database=db, port=int(port or 3306))
        return conn, db_type
    elif db_type == "postgres":
        conn = psycopg2.connect(host=host, user=user, password=password, dbname=db, port=int(port or 5432))
        return conn, db_type
    else:
        raise ValueError(f"DB_TYPE no soportado: {db_type}")

# --- EXTRACCION DE SCHEMA ---
def extract_schema(conn, db_type):
    cursor = conn.cursor()
    schema = {
        "fecha_extraccion": datetime.now().isoformat(),
        "tablas": [],
        "stored_procedures": {},
        "funciones": {},
        "triggers": {},
        "vistas": []
    }

    try:
        if db_type == "mssql":
            # Tablas + columnas
            cursor.execute("""
                SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME
            """)
            tablas = [r[0] for r in cursor.fetchall()]
            for tabla in tablas:
                cursor.execute(f"SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{tabla}'")
                cols = [{"nombre": r[0], "tipo": r[1], "nulo": r[2]} for r in cursor.fetchall()]
                schema["tablas"].append({"tabla": tabla, "columnas": cols})

            # Stored Procedures
            cursor.execute("SELECT ROUTINE_NAME, ROUTINE_DEFINITION FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_TYPE='PROCEDURE'")
            for name, definition in cursor.fetchall():
                if not definition:
                    cursor.execute(f"EXEC sp_helptext '{name}'")
                    definition = "\n".join([r[0] for r in cursor.fetchall()])
                schema["stored_procedures"][name] = definition

            # Funciones
            cursor.execute("SELECT ROUTINE_NAME, ROUTINE_DEFINITION FROM INFORMATION_SCHEMA.ROUTINES WHERE ROUTINE_TYPE='FUNCTION'")
            for name, definition in cursor.fetchall():
                schema["funciones"][name] = definition

            # Triggers
            cursor.execute("SELECT name, OBJECT_DEFINITION(object_id) FROM sys.triggers WHERE is_ms_shipped = 0")
            for name, definition in cursor.fetchall():
                schema["triggers"][name] = definition

            # Vistas
            cursor.execute("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS")
            schema["vistas"] = [r[0] for r in cursor.fetchall()]

        elif db_type == "mysql":
            cursor.execute("SHOW TABLES")
            for (tabla,) in cursor.fetchall():
                cursor.execute(f"SHOW COLUMNS FROM {tabla}")
                cols = [{"nombre": r[0], "tipo": r[1], "nulo": r[2]} for r in cursor.fetchall()]
                schema["tablas"].append({"tabla": tabla, "columnas": cols})

            cursor.execute("SHOW PROCEDURE STATUS WHERE Db = DATABASE()")
            for row in cursor.fetchall():
                proc_name = row[1]
                cursor.execute(f"SHOW CREATE PROCEDURE {proc_name}")
                schema["stored_procedures"][proc_name] = cursor.fetchone()[2]

            cursor.execute("SHOW FUNCTION STATUS WHERE Db = DATABASE()")
            for row in cursor.fetchall():
                func_name = row[1]
                cursor.execute(f"SHOW CREATE FUNCTION {func_name}")
                schema["funciones"][func_name] = cursor.fetchone()[2]

            cursor.execute("SHOW TRIGGERS")
            for row in cursor.fetchall():
                schema["triggers"][row[0]] = row[4]

        elif db_type == "postgres":
            cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
            tablas = [r[0] for r in cursor.fetchall()]
            for tabla in tablas:
                cursor.execute(f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name='{tabla}'")
                cols = [{"nombre": r[0], "tipo": r[1], "nulo": r[2]} for r in cursor.fetchall()]
                schema["tablas"].append({"tabla": tabla, "columnas": cols})

            cursor.execute("SELECT proname, pg_get_functiondef(oid) FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND prokind='p'")
            for name, defn in cursor.fetchall():
                schema["stored_procedures"][name] = defn

            cursor.execute("SELECT proname, pg_get_functiondef(oid) FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND prokind='f'")
            for name, defn in cursor.fetchall():
                schema["funciones"][name] = defn

            cursor.execute("SELECT trigger_name, action_statement FROM information_schema.triggers WHERE trigger_schema='public'")
            for name, defn in cursor.fetchall():
                schema["triggers"][name] = defn

    finally:
        cursor.close()

    return schema

def get_sp_definition(conn, db_type, sp_name):
    cursor = conn.cursor()
    try:
        if db_type == "mssql":
            cursor.execute(f"EXEC sp_helptext '{sp_name}'")
            rows = cursor.fetchall()
            if not rows: return None
            return "".join([r[0] for r in rows])
        elif db_type == "mysql":
            cursor.execute(f"SHOW CREATE PROCEDURE {sp_name}")
            r = cursor.fetchone()
            return r[2] if r else None
        elif db_type == "postgres":
            cursor.execute("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname=%s", (sp_name,))
            r = cursor.fetchone()
            return r[0] if r else None
    finally:
        cursor.close()
    return None

# --- COMPARACION ---
def comparar_sps(sp_name):
    print(f"--- Comparando SP: {sp_name} | DEV vs QA ---")
    conn_dev, type_dev = get_connection("DEV")
    conn_qa, type_qa = get_connection("QA")

    def_dev = get_sp_definition(conn_dev, type_dev, sp_name)
    def_qa = get_sp_definition(conn_qa, type_qa, sp_name)

    conn_dev.close()
    conn_qa.close()

    if not def_dev:
        print(f"[ERROR] SP '{sp_name}' no existe en DEV")
        return
    if not def_qa:
        print(f"[ERROR] SP '{sp_name}' no existe en QA")
        return

    # Normalizar
    dev_lines = def_dev.splitlines()
    qa_lines = def_qa.splitlines()

    diff = difflib.unified_diff(dev_lines, qa_lines, fromfile='DEV_'+sp_name, tofile='QA_'+sp_name, lineterm='')

    diff_list = list(diff)
    if not diff_list:
        print("✅ Los SPs son IDÉNTICOS")
    else:
        print("\n".join(diff_list))
        # Generar HTML bonito
        html_diff = difflib.HtmlDiff().make_file(dev_lines, qa_lines, fromdesc='DEV', todesc='QA')
        html_file = f"diff_{sp_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_diff)
        print(f"\n📄 Reporte HTML generado: {html_file}")

# --- MAIN ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extractor de Schema y Comparador de SPs DEV vs QA")
    parser.add_argument("--extraer", choices=["DEV", "QA"], help="Extrae schema completo de un ambiente")
    parser.add_argument("--comparar-sp", help="Nombre del SP a comparar entre DEV y QA")
    parser.add_argument("--output", default="schema.json", help="Archivo de salida para extraccion")

    args = parser.parse_args()

    if args.extraer:
        conn, db_type = get_connection(args.extraer)
        print(f"Extrayendo schema de {args.extraer} ({db_type})...")
        schema = extract_schema(conn, db_type)
        conn.close()
        with open(f"{args.extraer}_{args.output}", "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=4, ensure_ascii=False)
        print(f"✅ Schema guardado en {args.extraer}_{args.output}")

    elif args.comparar_sp:
        comparar_sps(args.comparar_sp)

    else:
        parser.print_help()