# verificar_bd.py  — ejecutar desde backend/
import sys
from sqlalchemy import text

def main():
    print("🔍 Verificando conexión a PostgreSQL...\n")

    # 1. Importar configuración
    try:
        from app.core.config import settings
        print(f"✅ Configuración cargada")
        print(f"   Host     : {settings.DB_HOST}:{settings.DB_PORT}")
        print(f"   Base     : {settings.DB_NAME}")
        print(f"   Usuario  : {settings.DB_USER}")
        print(f"   URL      : postgresql://{settings.DB_USER}:***@"
              f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}\n")
    except Exception as e:
        print(f"❌ Error cargando config: {e}")
        sys.exit(1)

    # 2. Conectar al engine
    try:
        from app.db.database import engine
        with engine.connect() as conn:

            # Ping básico
            conn.execute(text("SELECT 1"))
            print("✅ Conexión establecida\n")

            # Versión de PostgreSQL
            version = conn.execute(text("SELECT version()")).scalar()
            print(f"📦 PostgreSQL: {version.split(',')[0]}\n")

            # Verificar que la base de datos existe
            db_existe = conn.execute(text(
                "SELECT datname FROM pg_database WHERE datname = :db"
            ), {"db": settings.DB_NAME}).scalar()
            print(f"{'✅' if db_existe else '❌'} Base de datos '{settings.DB_NAME}': "
                  f"{'encontrada' if db_existe else 'NO encontrada'}\n")

            # Listar tablas del proyecto
            tablas = conn.execute(text("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)).fetchall()

            tablas_esperadas = {"usuarios", "hatos", "animales", "mediciones", "reportes"}
            tablas_existentes = {t[0] for t in tablas}

            print("📋 Tablas en la BD:")
            if tablas_existentes:
                for tabla in sorted(tablas_existentes):
                    estado = "✅" if tabla in tablas_esperadas else "➕"
                    print(f"   {estado} {tabla}")
            else:
                print("   ⚠️  No hay tablas — ejecuta el servidor en modo development")
                print("       para que lifespan() las cree automáticamente\n")

            faltantes = tablas_esperadas - tablas_existentes
            if faltantes:
                print(f"\n⚠️  Tablas faltantes: {', '.join(sorted(faltantes))}")

            print("\n✅ Todo OK — tu backend está conectado a PostgreSQL")

    except Exception as e:
        print(f"❌ No se pudo conectar: {e}")
        print("\n💡 Revisa:")
        print("   • Que PostgreSQL esté corriendo (pg_ctl status)")
        print("   • Que el .env tenga las credenciales correctas")
        print(f"   • Que exista el usuario '{settings.DB_USER}' en PostgreSQL")
        sys.exit(1)

if __name__ == "__main__":
    main()