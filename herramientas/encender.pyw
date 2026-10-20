# Puente by Typers: lo enciende junto al reloj de Windows, sin ventanas negras (MIT).
# Lo usan el acceso directo del escritorio («--mostrar»: abre la pantalla del QR) y el de inicio de Windows.
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
orden = ["powershell.exe", "-NoProfile", "-STA", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
         "-File", os.path.join(AQUI, "bandeja.ps1")]
if "--mostrar" in sys.argv:
    orden.append("-Mostrar")
subprocess.Popen(orden, cwd=os.path.dirname(AQUI), creationflags=subprocess.CREATE_NO_WINDOW)
