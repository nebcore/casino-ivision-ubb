import cv2
import threading
import time
import platform

class VideoStream:
    def __init__(self, src=0):
        """Inicializa las variables pero espera a start() para abrir la cámara."""
        self.src = src
        self.stream = None
        self.grabbed = False
        self.frame = None
        self.stopped = True
        self.lock = threading.Lock()

    def start(self):
        """Abre la cámara detectando el SO y fuerza la resolución."""
        sistema = platform.system()
        
        if sistema == "Windows":
            self.stream = cv2.VideoCapture(self.src, cv2.CAP_DSHOW)
        elif sistema == "Linux":
            self.stream = cv2.VideoCapture(self.src, cv2.CAP_V4L2)
        else:
            self.stream = cv2.VideoCapture(self.src)

        if not self.stream.isOpened():
            raise ValueError(f"No se pudo abrir la cámara {self.src} en {sistema}")
        
        # --- AQUÍ FORZAMOS LA RESOLUCIÓN DESPUÉS DE ABRIRLA ---
        self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        # ------------------------------------------------------
        
        self.grabbed, self.frame = self.stream.read()
        self.stopped = False

        self.thread = threading.Thread(target=self.update, args=(), daemon=True)
        self.thread.start()
        return self

    def update(self):
        """Mantiene el frame más reciente leído en segundo plano."""
        while True:
            if self.stopped:
                if self.stream is not None:
                    self.stream.release()
                return

            grabbed, frame = self.stream.read()
            
            # Guardamos el frame usando el cerrojo para evitar bloqueos con la web
            with self.lock:
                self.grabbed = grabbed
                self.frame = frame
            
            time.sleep(0.03)

    def read(self):
        """Devuelve el frame más reciente. Es llamado por la IA o la Interfaz."""
        with self.lock:
            if self.frame is not None:
                return self.frame.copy() 
            return None

    def stop(self):
        """Detiene el hilo y libera la cámara de forma segura."""
        self.stopped = True
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
        
        if self.stream is not None:
            self.stream.release()