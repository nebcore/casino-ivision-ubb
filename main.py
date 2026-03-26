import os
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
import cv2
import csv
from datetime import datetime
import uvicorn
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import StreamingResponse, HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import time
import torch
import threading
import copy
import json
from pydantic import BaseModel
import platform
from database.db_manager import DatabaseManager

class SolicitudDescarga(BaseModel):
    password: str

class ZonaWeb(BaseModel):
    nombre: str
    coordenadas: list 

class EstadoIA(BaseModel):
    activo: bool

class ConfigWeb(BaseModel):
    confianza: float
    camara_index: int = 0
    intervalo_db: Optional[int] = None

ARCHIVO_CONFIG = "config_app.json"
confianza_global = 0.50
camara_global = 0
ia_activada = True
mostrar_cajas = True
intervalo_db_global = 5
ultimo_tiempo_registro = 0.0

# Instanciamos el DB Manager (creará casino_data.db automáticamente)
db = DatabaseManager()

# Memoria para registrar solo cuando hay cambios
ultima_foto_conteo = {}

def cargar_configuracion():
    global confianza_global, camara_global, ia_activada, mostrar_cajas
    try:
        with open(ARCHIVO_CONFIG, "r") as f:
            datos = json.load(f)
            confianza_global = datos.get("confianza", 0.50)
            camara_global = datos.get("camara_index", 0)
            ia_activada = datos.get("ia_activada", True)
            mostrar_cajas = datos.get("mostrar_cajas", True)
    except FileNotFoundError:
        pass

def guardar_config_en_disco():
    """Toma las variables globales actuales y las guarda en el JSON."""
    with open(ARCHIVO_CONFIG, "w") as f:
        json.dump({
            "confianza": confianza_global, 
            "camara_index": camara_global,
            "ia_activada": ia_activada,
            "mostrar_cajas": mostrar_cajas,
            "intervalo_db": intervalo_db_global,
        }, f)

cargar_configuracion()

# Y crea la variable global que controlará el sistema
# ia_activada = True

def escanear_camaras():
    """Escanea los puertos y extrae los nombres reales del hardware de Windows."""
    print("[INFO] Buscando nombres reales de cámaras...")
    camaras_activas = []
    sistema = platform.system()

    # --- INTENTO 1: Usar lector de Hardware en Windows ---
    if sistema == "Windows":
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            dispositivos = graph.get_input_devices() # Saca la lista de nombres reales
            
            for i, nombre in enumerate(dispositivos):
                # Verificamos si la cámara realmente responde (que no sea un puerto fantasma)
                cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        camaras_activas.append({"indice": i, "nombre": f"{nombre} (Índice {i})"})
                    cap.release()
        except ImportError:
            print("[WARN] pygrabber no instalado. Usando nombres genéricos.")
        except Exception as e:
            print(f"[WARN] Error leyendo hardware: {e}")

    # --- INTENTO 2: Método clásico (Fallback para Linux o si falla Windows) ---
    if not camaras_activas:
        for i in range(5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, _ = cap.read()
                if ret:
                    camaras_activas.append({"indice": i, "nombre": f"Cámara Detectada (Índice {i})"})
                cap.release()

    # --- CORTAFUEGOS: Si no hay NADA conectado ---
    if not camaras_activas:
        camaras_activas.append({"indice": 0, "nombre": "Cámara por defecto (0)"})
        
    print(f"[INFO] Cámaras encontradas operativas: {len(camaras_activas)}")
    return camaras_activas

# Ejecutamos el escáner UNA SOLA VEZ al arrancar el programa
lista_camaras_disponibles = escanear_camaras()

# Ejecutamos el escáner UNA SOLA VEZ al arrancar el programa
lista_camaras_disponibles = escanear_camaras()

# Variable para guardar la información técnica de la cámara
info_sistema = {"camara": "Cámara Principal (0)", "resolucion": "Calculando..."}

torch.set_num_threads(1)  # Limitar PyTorch a usar solo 1 hilo para evitar bloqueos en CPU

# Importamos las herramientas de nuestro core
from core.video_stream import VideoStream
from core.detector import PersonDetector
from core.zone_manager import ZoneManager
from database.db_manager import DatabaseManager

# Inicializamos FastAPI y el motor de plantillas HTML
app = FastAPI(title="Casino UBB Vision API")
templates = Jinja2Templates(directory="web")

# Instanciamos nuestros módulos
stream = VideoStream(src=0).start()
detector = PersonDetector('yolov8n_openvino_model') # Aseguramos usar OpenVINO si lo tienes
zone_manager = ZoneManager()

# --- 1. CARGAMOS LA MEMORIA PERMANENTE PRIMERO ---
ARCHIVO_ZONAS = "zonas_guardadas.json"

def cargar_zonas_desde_archivo():
    """Carga las zonas desde el disco duro al iniciar el programa."""
    try:
        with open(ARCHIVO_ZONAS, "r") as f:
            zonas_guardadas = json.load(f)
            for nombre, datos in zonas_guardadas.items():
                zone_manager.agregar_zona(nombre, datos["coords_norm"])
    except FileNotFoundError:
        # Si es la primera vez que abres el programa, no habrá archivo. Arrancamos en blanco.
        pass

# ¡Ejecutamos la carga INMEDIATAMENTE!
cargar_zonas_desde_archivo()


# --- 2. LA NUEVA ARQUITECTURA: Variables Compartidas ---
detecciones_globales = []
zonas_globales = zone_manager.obtener_zonas() # Cargamos el estado inicial
cerrojo = threading.Lock() 

# --- 3. AHORA SÍ, DEFINIMOS Y ENCENDEMOS LA IA ---
def motor_ia_background():
    """EL CEREBRO: Solo piensa y hace matemáticas. No toca el video web."""
    global detecciones_globales, zonas_globales, ultima_foto_conteo, ultimo_tiempo_registro, intervalo_db_global

    print("[IA] Motor de IA encendido. Estado:{'ACTIVO' if ia_activada else 'INACTIVO'}")
    
    while True:
        frame = stream.read()
        if frame is None:
            time.sleep(0.01)
            continue
            
        h, w = frame.shape[:2]
        info_sistema["resolucion"] = f"{w}x{h}"

        if not ia_activada:
            ultima_foto_conteo = {} # Reseteamos la memoria de cambios para evitar confusiones al volver a activar
            with cerrojo:
                detecciones_globales = []
                # Le pasamos una lista vacía para que el contador caiga a 0
                zonas_globales = zone_manager.actualizar_conteos([], w, h) 
            time.sleep(0.2) # Dormimos el procesador
            continue
        
        # 1. Ejecutamos YOLO (trabajo pesado)
        detecciones = detector.detect(frame, conf=confianza_global)
        zonas_actualizadas = zone_manager.actualizar_conteos(detecciones, w, h)
        
        tiempo_actual = time.time()

        if tiempo_actual - ultimo_tiempo_registro >= intervalo_db_global:
            for zona_id, datos in zonas_actualizadas.items():
                conteo_actual = datos['conteo']
            
                # Si la zona es nueva o el número de personas cambió
                if zona_id not in ultima_foto_conteo or ultima_foto_conteo[zona_id] != conteo_actual:
                
                    # ¡Novedad detectada! Guardamos y ciframos en la BD
                    db.guardar_registro(zona_id, conteo_actual)
                    ultima_foto_conteo[zona_id] = conteo_actual
                    print(f"[DB-SEGURA] Cambio en {zona_id}: {conteo_actual} personas.")

            ultimo_tiempo_registro = tiempo_actual
        # 2. Guardamos los resultados en la "memoria global" rápidamente
        with cerrojo:
            detecciones_globales = detecciones
            zonas_globales = zonas_actualizadas
        
        # 3. La IA descansa (Piensa a ~6 FPS para ahorrar CPU)
        time.sleep(0.15) 

# Encendemos el cerebro
hilo_ia = threading.Thread(target=motor_ia_background, daemon=True)
hilo_ia.start()

def generar_video():
    while True:
        frame = stream.read()
        if frame is None:
            time.sleep(0.01)
            continue
            
        h, w = frame.shape[:2]
        
        # 1. Leemos "el último recuerdo" de la IA
        with cerrojo:
            det_actuales = copy.deepcopy(detecciones_globales)
            zon_actuales = copy.deepcopy(zonas_globales)
            
        # 2. Dibujamos súper rápido sobre el frame en vivo
        for zona_id, datos in zon_actuales.items():
            x1 = int(datos["coords_norm"][0] * w)
            y1 = int(datos["coords_norm"][1] * h)
            x2 = int(datos["coords_norm"][2] * w)
            y2 = int(datos["coords_norm"][3] * h)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
            cv2.putText(frame, f"{zona_id}: {datos['conteo']}", (x1, y1-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)

        if mostrar_cajas:
            for (dx1, dy1, dx2, dy2) in det_actuales:
                cv2.rectangle(frame, (dx1, dy1), (dx2, dy2), (0, 255, 0), 1)
                # Punto rojo en el centro del cuadro
                center_x = (dx1 + dx2) // 2
                center_y = (dy1 + dy2) // 2
                cv2.circle(frame, (center_x, center_y), 5, (0, 0, 255), -1)

        # 3. Comprimimos y enviamos
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
        ret, buffer = cv2.imencode('.jpg', frame, encode_param)
        
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        
        # 4. Magia de cine: Transmitimos a 25 FPS (40 milisegundos de pausa)
        time.sleep(0.04)

@app.get("/video_feed")
def video_feed():
    """Ruta que la página web usará para consumir el video en vivo."""
    return StreamingResponse(generar_video(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    """Ruta principal que sirve la interfaz web."""
    zonas = zone_manager.obtener_zonas()
    return templates.TemplateResponse("index.html", {"request": request, "zonas": zonas})

@app.get("/api/datos_zonas")
def api_datos_zonas():
    """Entrega los datos matemáticos puros en formato JSON."""
    return zone_manager.obtener_zonas()

@app.post("/api/guardar_zona")
def guardar_zona(zona: ZonaWeb):
    """Recibe la zona desde el navegador, la activa en YOLO y la guarda en el disco."""
    # 1. Agregarla al motor en vivo
    zone_manager.agregar_zona(zona.nombre, zona.coordenadas)
    
    # 2. Guardarla en el archivo JSON
    todas_las_zonas = zone_manager.obtener_zonas()
    datos_a_guardar = {}
    for nombre, datos in todas_las_zonas.items():
        datos_a_guardar[nombre] = {"coords_norm": datos["coords_norm"]}
        
    with open(ARCHIVO_ZONAS, "w") as f:
        json.dump(datos_a_guardar, f, indent=4)
        
    return {"mensaje": f"Zona {zona.nombre} guardada correctamente"}

@app.delete("/api/borrar_zona/{nombre_zona}")
def borrar_zona(nombre_zona: str):
    """Elimina una zona del motor en vivo y del archivo guardado."""
    # 1. Eliminar de la memoria en vivo (buscamos en el diccionario interno del manager)
    if hasattr(zone_manager, 'zonas') and nombre_zona in zone_manager.zonas:
        del zone_manager.zonas[nombre_zona]
    
    # 2. Actualizar el archivo JSON (reescribiéndolo sin la zona borrada)
    todas_las_zonas = zone_manager.obtener_zonas()
    datos_a_guardar = {}
    for nombre, datos in todas_las_zonas.items():
        datos_a_guardar[nombre] = {"coords_norm": datos["coords_norm"]}
        
    with open(ARCHIVO_ZONAS, "w") as f:
        json.dump(datos_a_guardar, f, indent=4)
        
    return {"mensaje": f"Zona {nombre_zona} eliminada correctamente"}

@app.post("/api/estado_ia")
def cambiar_estado_ia(estado: EstadoIA):
    """Enciende o apaga el procesamiento pesado de YOLO."""
    global ia_activada
    ia_activada = estado.activo
    guardar_config_en_disco()
    return {"mensaje": f"Motor de IA {'activado' if ia_activada else 'desactivado'}"}

@app.get("/api/sistema")
def api_sistema():
    """Devuelve la información técnica de la transmisión de video."""
    return info_sistema

@app.get("/{file_path}")
async def get_static_file(file_path: str):
    """Sirve archivos estáticos desde la raíz del proyecto."""
    file_full_path = os.path.join(".", file_path)
    
    # Seguridad: evitar acceso fuera del directorio
    if not os.path.abspath(file_full_path).startswith(os.path.abspath(".")):
        return {"error": "Acceso denegado"}
    
    if os.path.isfile(file_full_path):
        return FileResponse(file_full_path)
    
    return {"error": "Archivo no encontrado"}

@app.post("/api/configuracion")
def guardar_configuracion(config: ConfigWeb):
    global confianza_global, camara_global, intervalo_db_global, stream, info_sistema
    
    if config.camara_index is not None and config.camara_index != camara_global:
        camara_global = config.camara_index
        stream.stop()
        time.sleep(1) 
        stream = VideoStream(src=camara_global).start()
        info_sistema["camara"] = f"Cámara Índice ({camara_global})"
        
    if config.confianza is not None:
        confianza_global = config.confianza
        
    if config.intervalo_db is not None:
        intervalo_db_global = config.intervalo_db
        
    guardar_config_en_disco()
    return {"mensaje": "Configuración guardada"}

@app.get("/api/configuracion")
def obtener_configuracion():
    return {
        "confianza": confianza_global,
        "camara_index": camara_global,
        "ia_activada": ia_activada,
        "mostrar_cajas": mostrar_cajas,
        "intervalo_db": intervalo_db_global # <-- Añadimos esto para la web
    }

@app.get("/api/camaras_disponibles")
def api_camaras_disponibles():
    """Envía la lista de cámaras reales detectadas al arrancar."""
    return lista_camaras_disponibles

@app.post("/api/estado_cajas")
def cambiar_estado_cajas(estado: EstadoIA): # Reutilizamos el modelo EstadoIA que ya tiene 'activo: bool'
    global mostrar_cajas
    mostrar_cajas = estado.activo
    guardar_config_en_disco() # <-- Guardamos
    return {"mensaje": "Estado de cajas actualizado"}

@app.post("/api/exportar_csv")
def exportar_csv(solicitud: SolicitudDescarga):
    """Valida la clave y genera un archivo CSV con los datos descifrados."""
    
    # 1. Validar la contraseña contra el .env
    password_maestra = os.getenv("DB_PASSWORD", "clave_temporal_123")
    
    if solicitud.password != password_maestra:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña de administrador incorrecta"
        )

    # 2. Si la clave es correcta, obtenemos los datos reales (descifrados)
    try:
        registros = db.obtener_registros_descifrados()
        if not registros:
            raise HTTPException(status_code=404, detail="No hay datos para exportar todavía.")

        ruta_csv = "reporte_seguro_casino.csv"
        
        # 3. Crear el archivo CSV al vuelo
        with open(ruta_csv, mode='w', newline='', encoding='utf-8') as f:
            escritor = csv.writer(f)
            # Cabeceras del Excel
            escritor.writerow(['ID', 'Fecha y Hora', 'Zona Monitoreada', 'Cantidad de Personas'])
            
            for r in registros:
                # Formateamos la fecha para que Excel la entienda bien
                fecha_str = r['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
                escritor.writerow([r['id'], fecha_str, r['zona'], r['conteo']])

        # 4. Enviar el archivo al navegador y luego borrarlo (opcional por seguridad)
        return FileResponse(
            path=ruta_csv, 
            filename=f"Reporte_Casino_{datetime.now().strftime('%d_%m_%Y')}.csv",
            media_type='text/csv'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el reporte: {str(e)}")

if __name__ == "__main__":
    # Arranca el servidor web. 0.0.0.0 permite que otros equipos en la red se conecten.
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)