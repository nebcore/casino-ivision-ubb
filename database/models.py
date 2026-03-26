from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class RegistroDensidad(Base):
    __tablename__ = 'registros_densidad'

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    
    # Estas columnas guardarán el texto cifrado, por lo que deben ser String
    zona_id_cifrada = Column(String, nullable=False)
    conteo_cifrado = Column(String, nullable=False)

    def __repr__(self):
        # Mantenemos el log limpio y no revelamos información accidentalmente
        return f"<Registro(id={self.id}, fecha='{self.timestamp}', estado='Cifrado')>"