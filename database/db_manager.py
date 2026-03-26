import os
import base64
import hashlib
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from database.models import Base, RegistroDensidad

load_dotenv()

class DatabaseManager:
    def __init__(self):
        # 1. Obtener la contraseña del .env
        db_password = os.getenv("DB_PASSWORD", "clave_temporal_123")
        
        # 2. Transformar tu contraseña en una llave criptográfica válida para Fernet
        llave_hash = hashlib.sha256(db_password.encode()).digest()
        llave_fernet = base64.urlsafe_b64encode(llave_hash)
        self.cipher = Fernet(llave_fernet)
        
        # 3. Configurar la base de datos SQLite estándar
        db_path = "casino_data.db"
        db_url = f"sqlite:///{db_path}"
        
        # 4. Iniciar el motor de la base de datos
        self.engine = create_engine(db_url, echo=False)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def guardar_registro(self, zona_id: str, conteo: int):
        """Cifra los datos y los guarda en la base de datos."""
        session = self.Session()
        try:
            # Encriptar los datos (Fernet solo cifra bytes, así que codificamos y decodificamos)
            zona_cifrada = self.cipher.encrypt(zona_id.encode()).decode()
            conteo_cifrado = self.cipher.encrypt(str(conteo).encode()).decode()
            
            nuevo_registro = RegistroDensidad(
                zona_id_cifrada=zona_cifrada, 
                conteo_cifrado=conteo_cifrado
            )
            session.add(nuevo_registro)
            session.commit()
            # print("Dato guardado y cifrado con éxito.") # Descomentar para debug
        except Exception as e:
            session.rollback()
            print(f"Error crítico al guardar en BD: {e}")
        finally:
            session.close()

    def obtener_registros_descifrados(self):
        """Lee la base de datos y descifra los datos para poder usarlos en la UI."""
        session = self.Session()
        registros_legibles = []
        try:
            registros = session.query(RegistroDensidad).all()
            for reg in registros:
                # Descifrar los datos volviendo a usar la llave
                zona_real = self.cipher.decrypt(reg.zona_id_cifrada.encode()).decode()
                conteo_real = int(self.cipher.decrypt(reg.conteo_cifrado.encode()).decode())
                
                registros_legibles.append({
                    "id": reg.id,
                    "timestamp": reg.timestamp,
                    "zona": zona_real,
                    "conteo": conteo_real
                })
            return registros_legibles
        finally:
            session.close()