casino_vision_project/
│
├── core/                   # Lógica central
│   ├── video_stream.py     # Manejo de OpenCV y captura
│   ├── detector.py         # Instancia de YOLO y lógica de inferencia
│   └── tracker.py          # Lógica para no contar a la misma persona dos veces
│
├── database/               # Persistencia de datos
│   ├── models.py           # Esquemas de la base de datos
│   └── db_manager.py       # Conexiones y consultas
│
├── ui/                     # Interfaz gráfica
│   ├── main_window.py      # Contenedor principal
│   ├── video_widget.py     # Componente aislado para el renderizado de video
│   └── config_panel.py     # Componente para dibujar ROIs y botones
│
├── utils/                  # Herramientas auxiliares
│   ├── logger.py           # Reemplazo de los "print"
│   └── config.py           # Carga de variables de entorno (zonas, rutas)
│
├── main.py                 # Punto de entrada estricto (solo inicializa la app)
└── requirements.txt        # Dependencias del proyecto