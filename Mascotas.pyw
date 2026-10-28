# Doble clic en este archivo para abrir las mascotas SIN la ventana negra de consola.
# (Windows lo abre con pythonw.exe, que viene con Python.)
import os
import runpy
import sys

carpeta = os.path.dirname(os.path.abspath(__file__))
os.chdir(carpeta)
sys.path.insert(0, carpeta)
runpy.run_path(os.path.join(carpeta, "mascota_escritorio.py"), run_name="__main__")
