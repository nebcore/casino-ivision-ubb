from ultralytics import YOLO
import numpy as np

class PersonDetector:
    # 1. Cambiamos el valor por defecto a .onnx
    def __init__(self, model_path: str = 'yolov8n_openvino_model'): 
        try:
            self.model = YOLO(model_path, task='detect') 
        except Exception as e:
            raise RuntimeError(f"Error crítico: {e}")

    def detect(self, frame: np.ndarray, conf: float = 0.5) -> list:
        """
        Analiza un frame y devuelve una lista con las coordenadas de las personas.
        :param frame: Imagen en formato numpy array (entregada por OpenCV).
        :param conf: Nivel de confianza mínimo para validar una detección (0.0 a 1.0).
        :return: Lista de tuplas con las coordenadas (x1, y1, x2, y2) en píxeles.
        """
        if frame is None:
            return []

        # classes=[0] obliga a YOLO a ignorar sillas, mesas, etc., y buscar SOLO personas.
        # verbose=False evita que la terminal se llene de texto en cada frame.
        results = self.model(frame, classes=[0], conf=conf, verbose=False)
        
        personas_detectadas = []

        # Extraemos las cajas delimitadoras (bounding boxes)
        if results and len(results) > 0 and results[0].boxes:
            # .cpu().numpy() asegura que funcione bien sin importar si tienes tarjeta de video (GPU) o no
            cajas = results[0].boxes.xyxy.cpu().numpy()
            
            for box in cajas:
                # Convertimos las coordenadas a enteros (píxeles exactos)
                x1, y1, x2, y2 = map(int, box)
                personas_detectadas.append((x1, y1, x2, y2))

        return personas_detectadas