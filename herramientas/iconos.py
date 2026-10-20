# Exporta la marca de Puente by Typers desde sus archivos maestros (docs/marca/):
#   puente-icono.svg  -> web/icono-180.png (iPhone), web/icono-512.png (manifest), herramientas/puente.ico (Windows)
#                        y docs/marca/puente-icono-1024.png
#   encabezado.html   -> docs/marca/encabezado.png (README, 1280 × 360) y docs/marca/compartir.png (GitHub, 1280 × 640)
# Usa Chrome o Edge sin ventana para dibujar el SVG y el HTML tal cual (con la letra Michroma), y Pillow para reducir.
# Uso: python herramientas/iconos.py
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
MARCA = os.path.join(RAIZ, "docs", "marca")


def navegador():
    for nombre in ("chrome", "msedge", "google-chrome", "chromium", "chromium-browser"):
        ruta = shutil.which(nombre)
        if ruta:
            return ruta
    for ruta in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                 r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if os.path.exists(ruta):
            return ruta
    sys.exit("Hace falta Chrome o Edge para exportar. / Chrome or Edge is needed.")


def foto(archivo, ancho, alto, salida, extra=""):
    """Captura de un archivo local tal como lo dibuja el navegador (fondo transparente)."""
    url = "file:///" + os.path.join(MARCA, archivo).replace(os.sep, "/") + extra
    with tempfile.TemporaryDirectory() as perfil:
        subprocess.run([navegador(), "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={perfil}",
                        "--default-background-color=00000000", f"--window-size={ancho},{alto}", "--virtual-time-budget=5000",
                        f"--screenshot={salida}", url], check=True, capture_output=True, timeout=120)
    return salida


with tempfile.TemporaryDirectory() as tmp:
    grande = Image.open(foto("puente-icono.svg", 1024, 1024, os.path.join(tmp, "icono.png"))).convert("RGBA")
    grande.save(os.path.join(MARCA, "puente-icono-1024.png"), optimize=True)
    for lado in (180, 512):
        grande.resize((lado, lado), Image.LANCZOS).save(os.path.join(RAIZ, "web", f"icono-{lado}.png"), optimize=True)
    grande.resize((256, 256), Image.LANCZOS).save(os.path.join(AQUI, "puente.ico"),
                                                  sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    for nombre, alto, extra in (("encabezado.png", 360, ""), ("compartir.png", 640, "?compartir")):
        Image.open(foto("encabezado.html", 1280, alto, os.path.join(tmp, nombre), extra)).convert("RGB").save(
            os.path.join(MARCA, nombre), optimize=True)
print("OK: web/icono-*.png, herramientas/puente.ico y docs/marca/*.png")
