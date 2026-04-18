# R-JPG to TempMap

Convierte imágenes térmicas R-JPEG capturadas con drones DJI (M3T, M2EA, M30T, H20T, H20N, XT S) a GeoTIFF de temperatura (float32, grados Celsius) listos para construir ortomosaicos térmicos en **Agisoft Metashape** u otros programas de fotogrametría.

Cada píxel del TIFF resultante contiene la temperatura medida en grados Celsius. Los metadatos EXIF / GPS del R-JPEG original se copian al TIFF de salida para que Metashape pueda alinear las imágenes por geolocalización.

## Características

- Conversión masiva R-JPEG → TIFF float32 (temperatura en °C).
- Parámetros radiométricos configurables (distancia, humedad, emisividad, temperatura reflejada).
- Preservación de metadatos EXIF / GPS.
- Procesamiento paralelo multi-hilo.
- Interfaz gráfica (Tkinter) e interfaz de línea de comandos.
- Usa el **DJI Thermal SDK 1.4** oficial empaquetado.
- Implementación pura Python con **Pillow** (sin dependencias nativas pesadas).

## Dos formas de usarlo

### 1. Descargar el `.exe` (no necesita Python)

Descarga el ZIP desde la página [Releases](https://github.com/kincanek/R-JPG-to-TempMap/releases), descomprímelo y ejecuta **`RJPG-to-TempMap.exe`**. Funciona en cualquier Windows 10 / 11 x64 sin instalar nada más.

### 2. Ejecutar desde código fuente

```bash
git clone https://github.com/kincanek/R-JPG-to-TempMap.git
cd R-JPG-to-TempMap
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Requiere Python 3.9 o superior.

## Uso

### Interfaz gráfica

Doble clic en `RJPG-to-TempMap.exe` (o `python app.py`). Selecciona la carpeta con las imágenes R-JPEG (archivos `*_R.JPG` o `*_T.JPG`), la carpeta de salida, ajusta los parámetros radiométricos y pulsa **Convert**.

### Línea de comandos

```bash
# Convertir una carpeta completa
RJPG-to-TempMap.exe ruta\a\imagenes -o ruta\a\salida

# Con parámetros radiométricos personalizados
RJPG-to-TempMap.exe ruta\a\imagenes -o ruta\a\salida ^
    --distance 10 --humidity 65 --emissivity 0.96 --reflection 20

# Recursivo + 8 workers paralelos
RJPG-to-TempMap.exe ruta\a\imagenes -o ruta\a\salida --recursive --workers 8

# Sin copiar metadatos EXIF/GPS
RJPG-to-TempMap.exe ruta\a\imagenes -o ruta\a\salida --no-metadata
```

Si ejecutas desde fuente, reemplaza `RJPG-to-TempMap.exe` por `python app.py`.

## Parámetros radiométricos

| Parámetro    | Rango        | Por defecto | Descripción                                    |
|--------------|--------------|-------------|------------------------------------------------|
| `distance`   | 1 – 25 m     | 5.0         | Distancia aproximada del sensor al objetivo.   |
| `humidity`   | 20 – 100 %   | 70.0        | Humedad relativa ambiental.                    |
| `emissivity` | 0.10 – 1.00  | 0.95        | Emisividad de la superficie (0.95 = vegetación).|
| `reflection` | -40 – 500 °C | 23.0        | Temperatura reflejada del entorno.             |

## Flujo para ortomosaicos en Metashape

1. Convierte las imágenes con el `.exe` o la GUI.
2. Importa los `.tif` resultantes en Metashape **como si fueran fotos normales** — Metashape leerá las coordenadas GPS del EXIF copiado.
3. Alinea las cámaras, construye la nube densa y el ortomosaico.
4. El ortomosaico resultante está en grados Celsius por píxel, utilizable directamente para análisis térmico.

## Compilar el `.exe` desde código

```bash
pip install -r requirements.txt
pip install pyinstaller
build.bat
```

El ejecutable queda en `dist\RJPG-to-TempMap\RJPG-to-TempMap.exe` junto con las DLLs y `plugins\` necesarios. Puedes comprimir esa carpeta completa en un ZIP para distribuirla.

### Instalador Windows (opcional)

Si tienes [Inno Setup 6](https://jrsoftware.org/isinfo.php) instalado, puedes generar un instalador tipo "Next, Next, Finish" con desinstalador y accesos directos en el Menú Inicio:

```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\RJPG-to-TempMap.iss
```

El instalador queda en `installer\Output\RJPG-to-TempMap-v2.0.0-setup.exe`.

## Estructura del proyecto

```
R-JPG-to-TempMap/
├── app.py                       # Entrada (GUI por defecto, CLI si hay argumentos)
├── src/
│   ├── sdk.py                   # Wrapper del DJI Thermal SDK (dji_irp.exe)
│   ├── metadata.py              # Lector de EXIF vía Pillow
│   ├── converter.py             # Pipeline de conversión y batch
│   ├── cli.py                   # Interfaz de línea de comandos
│   └── gui.py                   # Interfaz Tkinter
├── plugins/
│   └── dji_thermal_sdk_v1.4_20220929/
├── build/
│   └── RJPG-to-TempMap.spec     # Spec de PyInstaller
├── installer/
│   └── RJPG-to-TempMap.iss      # Script de Inno Setup
├── build.bat                    # Script de build
├── requirements.txt
└── README.md
```

## Referencias

- **DJI Thermal SDK**: https://www.dji.com/downloads/softwares/dji-thermal-sdk
- **FLIR/DJI IR Camera Data Parser** (referencia Python): https://github.com/SanNianYiSi/thermal_parser
- **PyInstaller**: https://pyinstaller.org/
- **Inno Setup**: https://jrsoftware.org/isinfo.php

## Licencia

MIT — ver `LICENSE`. El DJI Thermal SDK conserva su propia licencia en `plugins/dji_thermal_sdk_v1.4_20220929/License.txt`.
