# Dibuja el ícono de Puente by Typers (un puente sobre una foto) y lo guarda en:
#   web/icono-180.png (iPhone), web/icono-512.png (manifest) y herramientas/puente.ico (acceso directo de Windows)
# Uso: python -I herramientas/iconos.py
import os
from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
N = 1024  # se dibuja grande y se reduce para que quede suave


def dibujar():
    im = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # Fondo: degradado azul, esquinas redondas
    fondo = Image.new("RGBA", (N, N))
    fd = ImageDraw.Draw(fondo)
    for y in range(N):
        t = y / N
        fd.line([(0, y), (N, y)], fill=(int(37 + 22 * t), int(99 - 40 * t), int(235 - 60 * t), 255))
    mascara = Image.new("L", (N, N), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, N - 1, N - 1], radius=230, fill=255)
    im.paste(fondo, (0, 0), mascara)
    blanco = (255, 255, 255, 255)
    # Foto (marco con montaña y sol)
    x0, y0, x1, y1 = 250, 190, 774, 560
    d.rounded_rectangle([x0, y0, x1, y1], radius=48, outline=blanco, width=44)
    d.polygon([(x0 + 60, y1 - 50), (430, 330), (560, 470), (630, 400), (x1 - 60, y1 - 50)], fill=blanco)
    d.ellipse([620, 250, 700, 330], fill=blanco)
    # Puente: arco y tablero
    d.arc([140, 600, 884, 1060], start=200, end=340, fill=blanco, width=48)
    d.rounded_rectangle([130, 700, 894, 748], radius=24, fill=blanco)
    for x in (300, 420, 604, 724):
        d.line([(x, 700), (x, 650 if x in (420, 604) else 680)], fill=blanco, width=30)
    return im


im = dibujar()
web = os.path.join(RAIZ, "web")
for lado in (180, 512):
    im.resize((lado, lado), Image.LANCZOS).save(os.path.join(web, f"icono-{lado}.png"), optimize=True)
im.resize((256, 256), Image.LANCZOS).save(os.path.join(AQUI, "puente.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("OK íconos en web/ y herramientas/puente.ico")
