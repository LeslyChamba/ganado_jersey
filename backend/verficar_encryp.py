# verificar_encriptacion.py
import sys
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

def main():
    from app.db.database import engine
    from app.core.encryption import decrypt, ya_encriptado

    print("\n" + "="*65)
    print("  VERIFICACIÓN DE ENCRIPTACIÓN — SISTEMA GANADERO")
    print("="*65)

    with engine.connect() as conn:

        # ── TABLA 1: auth.usuarios ───────────────────────────────────
        print("\n📋 TABLA 1: auth.usuarios")
        print("   Campos encriptados: email, nombre")
        print("-" * 65)

        try:
            usuarios = conn.execute(text(
                "SELECT id, email, nombre, rol FROM auth.usuarios LIMIT 5"
            )).fetchall()

            if not usuarios:
                print("  ⚠️  Sin usuarios — crea uno desde /docs")
            else:
                for fila in usuarios:
                    id_usr, email_bd, nombre_bd, rol = fila
                    print(f"\n  👤 ROL  : {rol}")
                    print(f"  📦 EMAIL en BD  : {email_bd}")
                    print(f"  📦 NOMBRE en BD : {nombre_bd}")
                    print(f"  🔒 email encriptado  → {'SÍ ✅' if ya_encriptado(email_bd)  else 'NO ❌'}")
                    print(f"  🔒 nombre encriptado → {'SÍ ✅' if ya_encriptado(nombre_bd) else 'NO ❌'}")
                    print(f"  🔓 EMAIL real   : {decrypt(email_bd)}")
                    print(f"  🔓 NOMBRE real  : {decrypt(nombre_bd)}")
                    print("  " + "-"*60)
        except ProgrammingError:
            print("  ❌ ERROR: La tabla 'auth.usuarios' no existe.")

        # ── TABLA 2: ganaderia.mediciones ───────────────────────────────
        print("\n\n📋 TABLA 2: ganaderia.mediciones")
        print("   Campo encriptado: notas")
        print("-" * 65)

        try:
            mediciones = conn.execute(text(
                "SELECT id, peso_estimado_kg, bcs, notas FROM ganaderia.mediciones WHERE notas IS NOT NULL LIMIT 5"
            )).fetchall()
            
            if not mediciones:
                print("  ⚠️  Sin mediciones con notas — crea una desde /docs")
            else:
                for fila in mediciones:
                    id_med, peso, bcs, notas_bd = fila
                    print(f"\n   Peso estimado : {peso} kg  |  BCS: {bcs}")
                    print(f"  📦 NOTAS en BD  : {notas_bd}")
                    print(f"  🔒 notas encriptadas → {'SÍ ✅' if ya_encriptado(notas_bd) else 'NO ❌'}")
                    print(f"  🔓 NOTAS reales : {decrypt(notas_bd)}")
                    print("  " + "-"*60)
        except ProgrammingError:
            print("  ❌ ERROR: La tabla 'ganaderia.mediciones' no existe.")

    print("\n" + "="*65)
    print("  Verificación completada — 2 tablas, 3 campos encriptados")
    print("="*65)

if __name__ == "__main__":
    main()