class ZoneManager:
    def __init__(self):
        """
        Inicializa el gestor de zonas.
        El diccionario 'zonas' tendrá la estructura:
        { "id_zona": {"coords_norm": (x1, y1, x2, y2), "conteo": 0} }
        """
        self.zonas = {}

    def agregar_zona(self, zona_id: str, coords_norm: tuple):
        """
        Registra una nueva zona en el sistema.
        :param zona_id: Nombre identificador (ej. "Ruleta_1")
        :param coords_norm: Tupla con coordenadas normalizadas entre 0 y 1 (x1, y1, x2, y2)
        """
        self.zonas[zona_id] = {
            "coords_norm": coords_norm,
            "conteo": 0
        }

    def limpiar_zonas(self):
        """Elimina todas las zonas registradas."""
        self.zonas.clear()

    def obtener_zonas(self):
        """Devuelve el diccionario actual de zonas."""
        return self.zonas

    def actualizar_conteos(self, detecciones: list, frame_width: int, frame_height: int) -> dict:
        """
        Calcula cuántas personas hay en cada zona basándose en sus centroides.
        :param detecciones: Lista de coordenadas en píxeles [(x1, y1, x2, y2), ...] entregada por YOLO.
        :param frame_width: Ancho actual del frame de video.
        :param frame_height: Alto actual del frame de video.
        :return: Diccionario actualizado con los conteos por zona.
        """
        # 1. Resetear todos los conteos a 0 para este nuevo frame
        for zona in self.zonas.values():
            zona["conteo"] = 0

        if not detecciones or not self.zonas:
            return self.zonas

        # 2. Calcular el centroide (punto central) de cada persona detectada
        centroides = []
        for (px1, py1, px2, py2) in detecciones:
            cx = (px1 + px2) / 2
            cy = (py1 + py2) / 2
            centroides.append((cx, cy))

        # 3. Verificar si el centroide cae dentro de los límites de alguna zona
        for zona_id, datos in self.zonas.items():
            xn1, yn1, xn2, yn2 = datos["coords_norm"]
            
            # Convertimos las coordenadas normalizadas (0 a 1) a píxeles reales de la imagen
            zx1 = xn1 * frame_width
            zy1 = yn1 * frame_height
            zx2 = xn2 * frame_width
            zy2 = yn2 * frame_height

            conteo_actual = 0
            for cx, cy in centroides:
                # Lógica de colisión básica (bounding box)
                if zx1 < cx < zx2 and zy1 < cy < zy2:
                    conteo_actual += 1
            
            datos["conteo"] = conteo_actual
            
        return self.zonas