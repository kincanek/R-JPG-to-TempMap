# R-JPG to TempMap

Convierte imágenes térmicas R-JPEG capturadas con drones DJI (M3T, M2EA, M30T, H20T, H20N, XT S) a GeoTIFF de temperatura (float32, grados Celsius) listos para construir ortomosaicos térmicos en **Agisoft Metashape** u otros programas de fotogrametría.

Cada píxel del TIFF resultante contiene la temperatura medida en grados Celsius. Los metadatos EXIF / GPS / XMP del R-JPEG original se copian al TIFF de salida para que Metashape pueda alinear las imágenes por geolocalización.

## Características

- Conversión masiva R-JPEG → TIFF float32 (temperatura en °C).
- Parámetros radiométricos configurables (distancia, humedad, emisividad, temperatura reflejada).
- Preservación de metadatos EXIF / GPS / XMP.
- Procesamiento paralelo multi-hilo.
- Interfaz gráfica (Tkinter) e interfaz de línea de comandos.
- Usa el **DJI Thermal SDK 1.4** oficial y **ExifTool** empaquetados.

## Requisitos

- Windows 10 / 11 (x64) — el DJI Thermal SDK solo se incluye precompilado para Windows.
- Python 3.9 o superior (si se ejecuta desde fuente).
- Dependencias Python: `numpy`, `tifffile` (ver `requirements.txt`).

## Instalación desde fuente

```bash
git clone https://github.com/kincanek/R-JPG-to-TempMap.git
cd R-JPG-to-TempMap
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Los binarios del DJI Thermal SDK y ExifTool ya vienen en `plugins/`.

## Uso

### Interfaz gráfica

```bash
python app.py
```

Selecciona la carpeta con las imágenes R-JPEG (archivos `*_R.JPG` o `*_T.JPG`), la carpeta de salida, ajusta los parámetros radiométricos y pulsa **Convert**.

### Línea de comandos

```bash
# Convertir una carpeta completa
python app.py ruta/a/imagenes -o ruta/a/salida

# Con parámetros radiométricos personalizados
python app.py ruta/a/imagenes -o ruta/a/salida \
    --distance 10 --humidity 65 --emissivity 0.96 --reflection 20

# Recursivo + 8 workers paralelos
python app.py ruta/a/imagenes -o ruta/a/salida --recursive --workers 8

# Sin copiar metadatos EXIF/GPS
python app.py ruta/a/imagenes -o ruta/a/salida --no-metadata
```

## Parámetros radiométricos

| Parámetro    | Rango        | Por defecto | Descripción                                    |
|--------------|--------------|-------------|------------------------------------------------|
| `distance`   | 1 – 25 m     | 5.0         | Distancia aproximada del sensor al objetivo.   |
| `humidity`   | 20 – 100 %   | 70.0        | Humedad relativa ambiental.                    |
| `emissivity` | 0.10 – 1.00  | 0.95        | Emisividad de la superficie (0.95 = vegetación).|
| `reflection` | -40 – 500 °C | 23.0        | Temperatura reflejada del entorno.             |

## Flujo para ortomosaicos en Metashape

1. Convierte las imágenes con `python app.py` o la GUI.
2. Importa los `.tif` resultantes en Metashape **como si fueran fotos normales** — Metashape leerá las coordenadas GPS del EXIF copiado.
3. Alinea las cámaras, construye la nube densa y el ortomosaico.
4. El ortomosaico resultante está en grados Celsius por píxel, utilizable directamente para análisis térmico.

## Estructura del proyecto

```
R-JPG-to-TempMap/
├── app.py                # Entrada (GUI por defecto, CLI si hay argumentos)
├── src/
│   ├── sdk.py            # Wrapper del DJI Thermal SDK (dji_irp.exe)
│   ├── metadata.py       # Wrapper de ExifTool
│   ├── converter.py      # Pipeline de conversión y batch
│   ├── cli.py            # Interfaz de línea de comandos
│   └── gui.py            # Interfaz Tkinter
├── plugins/
│   ├── dji_thermal_sdk_v1.4_20220929/
│   └── exiftool.exe
├── requirements.txt
└── README.md
```

## Referencias

- **DJI Thermal SDK**: https://www.dji.com/downloads/softwares/dji-thermal-sdk
- **FLIR/DJI IR Camera Data Parser** (referencia Python): https://github.com/SanNianYiSi/thermal_parser
- **ExifTool** por Phil Harvey: https://exiftool.org/

## Licencia

MIT — ver `LICENSE`. El DJI Thermal SDK y ExifTool conservan sus propias licencias.
