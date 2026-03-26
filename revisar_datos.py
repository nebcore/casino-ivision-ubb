import os
from database.db_manager import DatabaseManager
from dotenv import load_dotenv

def main():
    # 1. Cargar la clave del .env
    load_dotenv()
    
    if not os.getenv("DB_PASSWORD"):
        print("[ERROR] No se encontró DB_PASSWORD en el archivo .env")
        return

    # 2. Iniciar el gestor (él se encarga de derivar la llave y conectar)
    try:
        db = DatabaseManager()
        registros = db.obtener_registros_descifrados()
        
        if not registros:
            print("\n[INFO] La base de datos está conectada pero aún no hay registros.")
            return

        # 3. Formatear la salida en la terminal
        print("\n" + "="*75)
        print(f"{'CASINO UBB VISION - AUDITORÍA DE DATOS CIFRADOS':^75}")
        print("="*75)
        
        # Encabezados de tabla
        header = f"{'ID':<5} | {'FECHA Y HORA':<20} | {'ZONA':<20} | {'AFORO'}"
        print(header)
        print("-" * 75)

        # Imprimir cada fila descifrada
        # Nota: Usamos r['timestamp'] que SQLAlchemy genera automáticamente
        for r in registros:
            fecha = r['timestamp'].strftime("%d/%m/%Y %H:%M:%S")
            print(f"{r['id']:<5} | {fecha:<20} | {r['zona']:<20} | {r['conteo']}")
            
        print("-" * 75)
        print(f"Total de novedades registradas: {len(registros)}")
        print("="*75 + "\n")

    except Exception as e:
        print(f"[ERROR CRÍTICO] No se pudo leer o descifrar la base de datos: {e}")

if __name__ == "__main__":
    main()