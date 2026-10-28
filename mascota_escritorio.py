"""
Mascota de escritorio para Windows (Python + tkinter, sin librerías extra).

Uso:
    Doble clic en Mascotas.pyw                 -> inicia sin ventana de consola
    python mascota_escritorio.py               -> inicia (con consola, para ver avisos)
    python mascota_escritorio.py --ver-sheet   -> muestra las poses numeradas de pet.png

Controles:
    - Clic: la acaricias (reacciona contenta).
    - Arrastrar: la cargas; si la sueltas en movimiento, sale volando.
    - Clic derecho: menú (dormir, sentarse, saltar, jugar, galleta, recordatorios,
      tamaño, salir).

Comportamientos:
    - Camina, corre, se queda quieta, mira alrededor, se sienta y se duerme.
    - Salta de una ventana a otra, se baja de ellas y escala sus costados.
    - Camina sobre la barra de título de las ventanas y se mueve con ellas.
    - Solo se para en la parte visible de una ventana (si otra la tapa, se cae).
    - Pasa de un monitor a otro si están pegados.
    - Juega con el mouse: lo sigue con la mirada, a veces lo persigue y salta a atraparlo.
    - Galletas: dale una desde el menú (o arrástrala) y va corriendo a comérsela.
    - Recordatorios: te avisa con un globito de texto (descansar la vista, agua, los tuyos).
    - Travesuras: de vez en cuando empuja una ventana un poquito (se desactiva en el menú).
    - Vuela (en skins con "vuela": true en su .json) dejando brillitos.
    - Pelea por el mouse: lo agarra y se lo lleva; jálalo para que te lo suelte
      (se desactiva en el menú).
    - Varias mascotas a la vez (menú -> Mascotas): se saludan, juegan a las atrapadas
      y se echan peleas amistosas.
    - Cada personaje tiene su personalidad (frases) y habilidades propias en el .json
      de su skin: nieve, cristales, rayo, teletransporte, aura, súper salto...

Skins (hojas de sprites): pon pet.png junto al script y/o más imágenes en la
carpeta "skins". Se cambian desde el menú (clic derecho -> Skin). Aceptan
transparencia, fondo liso o fondo con degradado. La primera vez se procesan y
se guardan en un .cache para que los siguientes arranques sean rápidos.
    python mascota_escritorio.py --ver-sheet [imagen]   -> ver las poses numeradas
"""

import ctypes
import json
import math
import os
import pickle
import random
import sys
import time
import tkinter as tk
import zlib
from ctypes import wintypes

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------- Movimiento ----------
TICK_MS = 15               # ~60 cuadros por segundo
WALK_SPEED = 75            # px por segundo
RUN_SPEED = 180
CLIMB_SPEED = 85
GRAVITY = 2400             # px/s²
MAX_FALL_SPEED = 2400
HARD_LANDING = 1500        # caída más rápida que esto -> animación "aterriza"
JUMP_REACH_X = 700         # distancia horizontal máxima para saltar a otra ventana
JUMP_REACH_UP = 550        # altura máxima para saltar a otra ventana (más alto: trepa)
WALK_STRIDE = 7            # px recorridos por cuadro de la animación de caminar
ANIM_FPS = 9               # velocidad de las demás animaciones (cuadros/seg)
SLEEP_FPS = 2.5            # velocidad de la animación de dormir
ONESHOT_FPS = 6            # velocidad de las animaciones de una sola vez (feliz, despertar...)
EXTRA_SECONDS = (2.5, 4.5) # cuánto dura cada acción extra (regalo, música, saludo...)
LOOK_SECONDS = (1.2, 2.5)  # cuánto se queda mirando hacia un lado
TURN_TIME = 0.16           # al darse la vuelta pasa un momento de frente (sin "voltearse" de golpe)
CLICK_THROUGH = True       # el mouse "atraviesa" a la mascota salvo cuando está justo encima de ella
WINDOW_SCAN_MS = 250       # cada cuánto se revisan las ventanas abiertas
NUDGE_WINDOWS = False      # True: al caminar contra una ventana, la empuja

# Qué tan seguido elige cada acción (pesos relativos)
ACTIONS = {
    "caminar": 24, "correr": 7, "quieta": 14, "voltear": 6, "sentarse": 8,
    "dormir": 4, "saltito": 5, "saltar_ventana": 13, "bajarse": 5,
    "trepar": 16, "extra": 6, "perseguir": 5, "travesura": 4, "volar": 12, "pelear": 4,
    "cambiar_pantalla": 7,     # solo si tienes más de un monitor
    "jugar_juntas": 5, "saludar": 4,   # solo si hay más de una mascota
    "pelear_con": 7,           # pelea amistosa con otra mascota
    "disparar": 8,             # dispara su ataque (a otra mascota, al mouse o a una ventana)
    "habilidad": 12,           # habilidad especial del personaje (ver su .json)
    "hablar": 4,               # dice algo de su personalidad
}

# Habilidades que puede tener cada skin en su .json ("habilidades": [...]):
#   limpiar      camina limpiando con burbujitas
#   aura         modo furia: corre más rápido envuelta en un aura
#   nieve        hace nevar a su alrededor
#   cristales    lanza cristales/hielo (también es su ataque en las peleas)
#   congelar     al pelear por el mouse lo congela en su lugar en vez de llevárselo
#   teletransporte  desaparece y aparece en otra ventana o pantalla
#   rayo         dispara un rayo de luz (si "travesuras" está activo, sacude la ventana)
#   super_salto  salto altísimo dejando una estela
#   lucero       hace girar su bola de metal con picos alrededor (Rem)
#   te           se sienta a tomar té (sale vaporcito) e invita a otra a sentarse
#   lectura      se sienta a leer y flotan hojitas a su alrededor
#   curiosear    va con otra mascota (o hacia el mouse) a preguntarle cosas
#   sombra       se envuelve en sombras moradas (usa la pose "sombra" si existe)
#   manos        lanza una mano de sombra: jala a otra mascota hacia ella o atrapa el mouse
#   bendicion    aura dorada de protección divina: más rápido por un rato
#   minimizar    corte de espada a una ventana y la minimiza   (poder pesado)
#   golpe_mouse  le pega al cursor y lo manda volando          (poder pesado)
ABILITY_NAMES = {"limpiar", "aura", "nieve", "cristales", "teletransporte", "rayo",
                 "super_salto", "lucero", "te", "lectura", "curiosear", "sombra", "manos",
                 "bendicion", "minimizar", "golpe_mouse"}
HEAVY_ABILITIES = {"minimizar", "golpe_mouse"}
ELEMENT_COLORS = [["#fff3c4", "#ff9a3c", "#ff5a1f", "#b32400"],    # fuego
                  ["#e8f7ff", "#6ec6ff", "#2f8fe0", "#1a4f8f"],    # agua
                  ["#effff0", "#8ff0a4", "#3ccf6a", "#1e7a3c"],    # viento
                  ["#fff7d6", "#e0c070", "#b08a3a", "#6b4f1d"]]    # tierra
# Lo que dispara cada skin ("disparo" en su .json): lucero (bola de metal con cadena),
# cristal, hielo (tres carámbanos), rayo, bala (bolita de luz), elementos (cuatro
# esferas: fuego, agua, viento y tierra), mano (mano de sombra que jala) o corte
# (media luna de espada).
SHOT_RANGE = 750           # distancia máxima a la que apunta
LUCERO_REACH = 330         # largo de la cadena del lucero
DODGE_CHANCE = 0.25        # probabilidad de esquivar un disparo brincando
REVENGE_CHANCE = 0.5       # si le disparan sin estar peleando, a veces se enoja y responde
FIGHT_DISTANCE = 170       # distancia a la que se pelean (se disparan)

# ---------- Poder y relaciones (cada skin los define en su .json) ----------
# "poder": qué tan fuerte es (1 a 10). Decide quién gana, quién esquiva y qué tan
#          lejos sale volando la otra al recibir un golpe.
# "relaciones": {"Emilia": {"afinidad": -3, "frases": {"pelea": [...]}}, ...}
#          afinidad de -3 (la odia) a 3 (la adora): con quién se pelea, a quién
#          saluda, a quién invita al té... y frases especiales para esa persona.
DEFAULT_POWER = 3
ENEMY_NEAR = 260           # a esta distancia una enemiga la "molesta"
POWER_FLAG_DEFAULT = True  # poderes pesados (minimizar ventanas, lanzar el mouse...)
SKIN_ALIASES = {"pet": "Rem"}   # nombres viejos de skins -> nombre nuevo
FX_RATES = {"aura": 30, "burbujas": 14, "nieve": 18, "estela": 40, "hielo_cursor": 30,
            "sombra": 34, "vapor": 7, "paginas": 5}
FIGHT_SECONDS_MAX = 25     # duración máxima de una pelea entre mascotas
TAG_SECONDS = 30           # duración máxima de un juego de las atrapadas

# ---------- Volar (solo skins con "vuela": true en su .json) ----------
FLY_SPEED = 230            # px por segundo
FLY_SECONDS = (6, 14)      # cuánto vuela cada vez
PARTICLE_COLORS = ["#e2c6ff", "#c08bff", "#a064ff", "#7a3fe0"]   # el último es el más oscuro
PARTICLE_RATE = 26         # brillitos por segundo mientras vuela
PARTICLE_LIFE = (0.5, 1.1) # segundos que dura cada brillito
PARTICLES_MAX = 70

# ---------- Pelear por el mouse ----------
MOUSE_FIGHT = True         # valor inicial (se cambia desde el menú y se recuerda)
FIGHT_SECONDS = (1.5, 3.5) # cuánto se lleva el mouse si no la detienes
FIGHT_RESIST = 220         # cuánto tienes que jalar (px) para que te lo suelte

# ---------- Travesuras ----------
PRANKS = True              # valor inicial (se cambia desde el menú y se recuerda)
PRANK_DISTANCE = (50, 160) # cuántos px empuja la ventana
PUSH_SPEED = 45            # px por segundo mientras empuja
PRANK_ACTIVE_WINDOW = True # False: nunca empuja la ventana en la que estás trabajando

# ---------- Jugar con el mouse ----------
MOUSE_PLAY = True          # False: ni lo mira ni lo persigue
WATCH_MOUSE_DIST = 450     # a esta distancia (px) voltea a ver el cursor cuando está quieta
CHASE_SECONDS = (5, 10)    # cuánto dura una persecución
CATCH_HEIGHT = 260         # qué tan arriba puede estar el cursor para que salte a atraparlo

# ---------- Recordatorios ----------
# Se repiten cada "cada_min" minutos. Los que agregues desde el menú se guardan
# en mascota_ajustes.json.
RECORDATORIOS = [
    {"cada_min": 30, "texto": "Descansa la vista: mira algo lejano unos 20 segundos."},
    {"cada_min": 60, "texto": "¿Ya tomaste agua?"},
    {"cada_min": 90, "texto": "Párate y estírate un poquito."},
]
BUBBLE_SECONDS = 15        # cuánto se queda el globo (clic en la mascota para cerrarlo)
BUBBLE_WIDTH = 230         # ancho máximo del texto del globo
REMINDER_SOUND = True      # sonidito de Windows al avisar

# ---------- Hoja de sprites ----------
# Para ver la numeración:   python mascota_escritorio.py --ver-sheet
CUSTOM_FILES = ("pet.png", "pet.gif", "pet.jpg", "pet.jpeg")
SHEET_SCALE = 0.7          # tamaño (1 = original). También se cambia desde el menú.
SHEET_TOLERANCE = 40       # fondo liso: qué tan parecido al fondo debe ser un color para borrarlo
SHEET_LOOKS_LEFT = False   # True si tus poses de perfil miran hacia la izquierda
SHEET_BACKGROUND = "auto"  # "plano", "degradado" o "auto"
SHEET_STEP = 12            # fondo degradado: cambio máximo de color entre píxeles vecinos del fondo
SHEET_ALPHA_MIN = 0.85     # PNG con transparencia: opacidad mínima para que un píxel cuente
BIG_PART = 0.35            # tamaño mínimo (vs. la pose más alta) para contar como pose
ATTACH_DIST = 0.25         # distancia a la que zzz, ?, globos o sombras se pegan a su pose
LABEL_FILL = 0.3           # recuadros de títulos: piezas anchas casi de un solo color se ignoran

# Animación de cada estado. Cada entrada es (fila, pose) o (fila, desde, hasta).
# Las poses pueden ser negativas: -1 es la última de esa fila, -2 la penúltima...
# Cada skin puede tener sus propias animaciones en un .json con el mismo nombre
# que la imagen (ver skin_config más abajo); si no, usa estas.
# Estados: quieta, camina, corre, sentada, dormida, salta, cae, trepa, arrastrada.
# Opcionales:
#   "<estado>_inicio": se reproduce una vez al entrar al estado (p. ej. acostarse)
#   "feliz": al darle clic       "aterriza": tras una caída fuerte
#   "despierta": al despertar    "extra_<lo que sea>": se reproducen al azar
#   "<estado>_der" / "<estado>_izq": poses propias para cada lado (no se espejean)
# Los estados que falten usan uno parecido (corre -> camina -> quieta, etc.).
ANIMATIONS = {
    "quieta":         [(0, 0)],                 # parada de frente
    "mira":           [(0, 3)],                 # parada de perfil, mirando a un lado
    "gira":           [(0, 0)],                 # pose de frente al darse la vuelta
    "camina":         [(0, 4, 13)],             # ciclo de perfil
    "corre":          [(0, 4, 13)],
    "sentada":        [(2, 0, 3)],
    "dormida_inicio": [(8, 0, 2), (3, 0, -3)],  # cabecea, se acuesta
    "dormida":        [(3, -2), (3, -1)],       # las dos últimas: acostada con zzz
    "despierta":      [(8, 4)],                 # "Nyah"
    "salta":          [(5, 1)],
    "cae":            [(5, 2)],
    "aterriza":       [(5, 4), (5, 5)],
    "trepa":          [(4, 0, 4)],
    "arrastrada":     [(7, 1)],
    "feliz":          [(6, 0, 4)],
    "extra_regalo":   [(7, 2)],
    "extra_musica":   [(7, 4)],
    "extra_saluda":   [(6, 1), (6, 2), (6, 1), (6, 2)],
    # "empuja":       [(...)],                  # opcional: poses empujando (si no, usa camina)
}

# Animaciones de frente: NO se espejean (si se espejean, el moño o el peinado
# cambian de lado y se ve raro). Lo que termina en "_" aplica a todas las que
# empiezan así (p. ej. "extra_").
SIN_ESPEJO = ["quieta", "gira", "sentada", "feliz", "despierta", "arrastrada", "salta", "cae",
              "dormida_inicio", "dormida", "extra_"]

TRANSPARENT = "#010101"    # color clave que Windows vuelve transparente
SKIP_CLASSES = {"Shell_TrayWnd", "Shell_SecondaryTrayWnd", "Progman", "WorkerW",
                "Windows.UI.Core.CoreWindow", "ApplicationFrameWindow_Hidden"}
SETTINGS_FILE = os.path.join(BASE_DIR, "mascota_ajustes.json")
SKINS_DIR = os.path.join(BASE_DIR, "skins")
CACHE_VERSION = 4



# ---------- Win32 ----------
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # por monitor (DPI mixto)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

user32 = ctypes.windll.user32
try:
    dwmapi = ctypes.windll.dwmapi
except Exception:
    dwmapi = None
try:
    winmm = ctypes.windll.winmm
except Exception:
    winmm = None


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT),
                ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


MONITORENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HMONITOR, wintypes.HDC,
                                     ctypes.POINTER(RECT), wintypes.LPARAM)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumDisplayMonitors.argtypes = [wintypes.HDC, ctypes.c_void_p, MONITORENUMPROC,
                                       wintypes.LPARAM]
user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.IsZoomed.argtypes = [wintypes.HWND]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wintypes.HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
user32.MessageBeep.argtypes = [ctypes.c_uint]
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetForegroundWindow.restype = wintypes.HWND
if dwmapi:
    dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                             ctypes.c_void_p, wintypes.DWORD]

SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = wintypes.HWND(-1)
GA_ROOT = 2
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_APPWINDOW = 0x00040000
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14


def get_monitors():
    """Área útil (sin barra de tareas) de cada monitor: lista de (l, t, r, b)."""
    mons = []

    def callback(hmon, hdc, lprect, lparam):
        mi = MONITORINFO()
        mi.cbSize = ctypes.sizeof(MONITORINFO)
        if user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
            w = mi.rcWork
            mons.append((w.left, w.top, w.right, w.bottom))
        return True

    user32.EnumDisplayMonitors(None, None, MONITORENUMPROC(callback), 0)
    return mons or [(0, 0, 1920, 1080)]


def is_cloaked(hwnd):
    """Ventanas 'ocultas' por Windows (otros escritorios virtuales, apps UWP suspendidas)."""
    if not dwmapi:
        return False
    val = ctypes.c_int(0)
    try:
        dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        return False
    return val.value != 0


def visible_rect(hwnd):
    """Rectángulo visible de la ventana (sin los bordes invisibles de Windows 10/11)."""
    r = RECT()
    ok = False
    if dwmapi:
        try:
            ok = dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS,
                                              ctypes.byref(r), ctypes.sizeof(r)) == 0
        except Exception:
            ok = False
    if not ok:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return (r.left, r.top, r.right, r.bottom)


def list_windows(own_hwnd):
    """Ventanas visibles en orden de profundidad (la de más arriba primero):
    lista de (hwnd, l, t, r, b, se_puede_pisar)."""
    own_pid = os.getpid()
    result = []
    buf = ctypes.create_unicode_buffer(256)

    def callback(hwnd, _lparam):
        if hwnd == own_hwnd or not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == own_pid:
            return True
        ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if ex & WS_EX_TOOLWINDOW and not ex & WS_EX_APPWINDOW:
            return True
        if user32.GetWindowTextLengthW(hwnd) == 0:
            return True
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value in SKIP_CLASSES or is_cloaked(hwnd):
            return True
        l, t, r, b = visible_rect(hwnd)
        if (r - l) < 120 or (b - t) < 60:
            return True
        standable = not user32.IsZoomed(hwnd) and (r - l) >= 200
        result.append((hwnd, l, t, r, b, standable))
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return result


def window_ok(hwnd):
    """True si la ventana sigue existiendo, visible y en tamaño normal."""
    return bool(hwnd and user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd)
                and not user32.IsIconic(hwnd) and not user32.IsZoomed(hwnd)
                and not is_cloaked(hwnd))


def move_window_by(hwnd, dx, dy=0):
    """Mueve una ventana dx/dy píxeles sin activarla ni cambiar su tamaño."""
    r = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    user32.SetWindowPos(hwnd, None, r.left + int(dx), r.top + int(dy), 0, 0,
                        SWP_NOSIZE | SWP_NOACTIVATE | 0x0004)


def move_window(hwnd, x, y):
    user32.SetWindowPos(hwnd, None, int(x), int(y), 0, 0, SWP_NOSIZE | SWP_NOACTIVATE | 0x0004)


def mouse_down():
    """True si tienes presionado algún botón del mouse."""
    return bool((user32.GetAsyncKeyState(0x01) | user32.GetAsyncKeyState(0x02)) & 0x8000)


def cursor_pos():
    p = POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


# ---------- Hoja de sprites ----------
def read_sheet(path):
    """Lee la imagen y devuelve (imagen_tk, matriz de colores '#rrggbb' o None)."""
    root = tk._default_root
    if path.lower().endswith((".png", ".gif")):
        # formato explícito: algunos PNG traen miniaturas incrustadas que confunden a Tk
        img = tk.PhotoImage(file=path, format="gif" if path.lower().endswith(".gif") else "png")
    else:
        try:
            from PIL import Image, ImageTk
        except ImportError:
            raise SystemExit("Para usar %s instala Pillow (pip install pillow) "
                             "o guarda la imagen como .png" % os.path.basename(path))
        img = ImageTk.PhotoImage(Image.open(path).convert("RGBA"))

    def grab(color):
        raw = root.tk.call(str(img), "data", "-background", color)
        return [root.tk.splitlist(r) for r in root.tk.splitlist(raw)]

    # Tk no entrega la transparencia directamente: se pinta la imagen sobre negro
    # y sobre blanco; donde salen distintas, la diferencia indica qué tan
    # transparente es el píxel (y de ahí se recupera su color real).
    return img, merge_alpha(grab("#000000"), grab("#ffffff"))


def merge_alpha(dark, light):
    """Une las dos versiones (sobre negro / sobre blanco) en colores '#rrggbb'
    o None para los píxeles más transparentes que SHEET_ALPHA_MIN."""
    amin = SHEET_ALPHA_MIN * 255
    cache = {}
    out = []
    for rd, rl in zip(dark, light):
        row = []
        for cd, cl in zip(rd, rl):
            if cd == cl:                                  # opaco
                row.append(cd)
                continue
            r = cache.get((cd, cl))
            if r is None:
                vd, vl = int(cd[1:], 16), int(cl[1:], 16)
                d = (vd >> 16, vd >> 8 & 255, vd & 255)
                l = (vl >> 16, vl >> 8 & 255, vl & 255)
                a = 255 - sum(y - x for x, y in zip(d, l)) / 3
                if a < amin:
                    r = ""
                else:
                    r = "#%02x%02x%02x" % tuple(min(255, int(x * 255 / a + 0.5)) for x in d)
                cache[(cd, cl)] = r
            row.append(r or None)
        out.append(row)
    return out


def background_mode(pixels, tol):
    """'plano' si todo el borde de la hoja es del mismo color, si no 'degradado'."""
    if SHEET_BACKGROUND in ("plano", "degradado"):
        return SHEET_BACKGROUND
    h, w = len(pixels), len(pixels[0])
    border = pixels[0] + pixels[-1] + [r[0] for r in pixels] + [r[-1] for r in pixels]
    ref = pixels[0][0]
    if ref is None:
        return "plano"
    rc = int(ref[1:], 16)
    far = 0
    for c in border:
        if c is None:
            continue
        v = int(c[1:], 16)
        d = max(abs((v >> 16) - (rc >> 16)), abs((v >> 8 & 255) - (rc >> 8 & 255)),
                abs((v & 255) - (rc & 255)))
        if d > tol:
            far += 1
    return "degradado" if far > len(border) * 0.1 else "plano"


def flood_background(pixels, step):
    """Fondo con degradado o brillos: se 'inunda' desde los bordes avanzando
    solo entre píxeles vecinos de color parecido. Los contornos de las figuras
    (cambios bruscos de color) detienen la inundación."""
    h, w = len(pixels), len(pixels[0])
    R, G, B = [], [], []
    for row in pixels:
        for c in row:
            if c is None:
                R.append(-1000); G.append(-1000); B.append(-1000)
            else:
                v = int(c[1:], 16)
                R.append(v >> 16); G.append(v >> 8 & 255); B.append(v & 255)
    n = w * h
    bg = bytearray(n)
    stack = []
    for x in range(w):
        stack.append(x)
        stack.append((h - 1) * w + x)
    for y in range(h):
        stack.append(y * w)
        stack.append(y * w + w - 1)
    for p in stack:
        bg[p] = 1
    while stack:
        p = stack.pop()
        r, g, b = R[p], G[p], B[p]
        x = p % w
        for q in (p - w, p + w, p - 1 if x else -1, p + 1 if x < w - 1 else -1):
            if q < 0 or q >= n or bg[q]:
                continue
            if r < 0 or R[q] < 0 or (abs(R[q] - r) <= step and abs(G[q] - g) <= step
                                      and abs(B[q] - b) <= step):
                bg[q] = 1
                stack.append(q)
    return [bytearray(1 - bg[y * w + x] for x in range(w)) for y in range(h)]


def flat_mask(pixels, tol):
    bg = pixels[0][0]
    bgc = None if bg is None else (int(bg[1:3], 16), int(bg[3:5], 16), int(bg[5:7], 16))
    cache = {None: False}

    def solid_color(c):
        r = cache.get(c)
        if r is None:
            if bgc is None:
                r = True
            else:
                rgb = (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
                r = any(abs(a - b) > tol for a, b in zip(rgb, bgc))
            cache[c] = r
        return r

    return [bytearray(1 if solid_color(c) else 0 for c in row) for row in pixels]


def typical_height(boxes):
    """Altura "de referencia" de una pose. No usa la figura más alta (un retrato
    grande en la hoja lo arruinaría) sino la mediana de las piezas grandes."""
    hs = sorted(b[3] - b[1] + 1 for b in boxes)
    top = hs[-1]
    tall = [h for h in hs if h >= 40]
    if len(tall) >= 6:
        return min(top, int(tall[len(tall) // 2] * 1.35))
    return top


def detect_poses(pixels, tol, gap=4, min_part=4):
    """Encuentra las figuras de la hoja y las agrupa en filas.
    Devuelve (filas, mask): filas[f][p] = (x0, y0, x1, y1)."""
    h, w = len(pixels), len(pixels[0])
    if background_mode(pixels, tol) == "plano":
        mask = flat_mask(pixels, tol)
    else:
        mask = flood_background(pixels, SHEET_STEP)

    # componentes conectadas (8 vecinos)
    seen = [bytearray(w) for _ in range(h)]
    boxes = []
    for y in range(h):
        my, sy = mask[y], seen[y]
        for x in range(w):
            if not my[x] or sy[x]:
                continue
            sy[x] = 1
            stack = [(x, y)]
            x0 = x1 = x
            y0 = y1 = y
            n = 0
            while stack:
                cx, cy = stack.pop()
                n += 1
                if cx < x0: x0 = cx
                if cx > x1: x1 = cx
                if cy < y0: y0 = cy
                if cy > y1: y1 = cy
                for ny in (cy - 1, cy, cy + 1):
                    if 0 <= ny < h:
                        mrow, srow = mask[ny], seen[ny]
                        for nx in (cx - 1, cx, cx + 1):
                            if 0 <= nx < w and mrow[nx] and not srow[nx]:
                                srow[nx] = 1
                                stack.append((nx, ny))
            if n >= min_part:
                boxes.append([x0, y0, x1, y1])

    if not boxes:
        return [], mask
    tallest = typical_height(boxes)

    # fuera recuadros de títulos y logos: piezas anchas pintadas casi de un solo color
    def dominant(b):
        counts, tot = {}, 0
        for yy in range(b[1], b[3] + 1):
            mrow, prow = mask[yy], pixels[yy]
            for xx in range(b[0], b[2] + 1):
                if mrow[xx] and prow[xx]:
                    c = prow[xx]
                    k = c[1] + c[3] + c[5]
                    counts[k] = counts.get(k, 0) + 1
                    tot += 1
        return max(counts.values()) / tot if tot else 0

    panels = [b for b in boxes
              if b[2] - b[0] + 1 >= tallest * 0.5 and b[3] - b[1] + 1 < tallest * 0.6
              and dominant(b) >= LABEL_FILL]
    boxes = [b for b in boxes if b not in panels]
    if not boxes:
        return [], mask
    tallest = typical_height(boxes)
    big = [b for b in boxes if b[3] - b[1] + 1 >= tallest * BIG_PART]
    small = [b for b in boxes if b[3] - b[1] + 1 < tallest * BIG_PART]

    # 1) textos: 5 o más piezas chicas de altura parecida, alineadas y seguidas
    n = len(small)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    order = sorted(range(n), key=lambda i: small[i][0])
    for ii, i in enumerate(order):
        a = small[i]
        ha = a[3] - a[1] + 1
        for j in order[ii + 1:]:
            c = small[j]
            hc = c[3] - c[1] + 1
            if c[0] - a[2] > max(ha, hc) * 1.2:
                break
            overlap = min(a[3], c[3]) - max(a[1], c[1]) + 1
            if overlap >= 0.5 * min(ha, hc) and 0.4 <= ha / hc <= 2.5:
                parent[find(i)] = find(j)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    lines = []
    for g in groups.values():
        if len(g) >= 5:
            lines.append([min(small[i][0] for i in g), min(small[i][1] for i in g),
                          max(small[i][2] for i in g), max(small[i][3] for i in g)])
    text_ids = {i for g in groups.values() if len(g) >= 5 for i in g}

    def in_text(b, k=0.6):
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        for l in lines:
            m = (l[3] - l[1] + 1) * k
            if l[0] - m <= cx <= l[2] + m and l[1] - m <= cy <= l[3] + m:
                return True
        return False

    extras = [b for i, b in enumerate(small) if i not in text_ids and not in_text(b)]
    big = [b for b in big if not in_text(b, 0.5)]      # letras grandes pegadas (g, paréntesis)

    # 2) une piezas grandes que se tocan o casi (partes de la misma figura)
    merged = True
    while merged:
        merged = False
        out = []
        for b in big:
            for o in out:
                if (b[0] - gap <= o[2] and o[0] - gap <= b[2] and
                        b[1] - gap <= o[3] and o[1] - gap <= b[3]):
                    o[0], o[1] = min(o[0], b[0]), min(o[1], b[1])
                    o[2], o[3] = max(o[2], b[2]), max(o[3], b[3])
                    merged = True
                    break
            else:
                out.append(b)
        big = out
    if not big:
        return [], mask

    # 2b) poses pegadas entre sí (pelo o vestido que se tocan): si una caja es mucho
    #     más ancha que lo normal, se parte por la columna más "vacía" siempre que
    #     de los dos lados quede algo con altura de pose.
    widths = sorted(b[2] - b[0] + 1 for b in big)
    med_w = widths[len(widths) // 2]

    def column_profile(b):
        return [sum(1 for y in range(b[1], b[3] + 1) if mask[y][x]) for x in range(b[0], b[2] + 1)]

    def height_of(b, x0, x1):
        rows_ = [y for y in range(b[1], b[3] + 1) if any(mask[y][x0:x1 + 1])]
        return (rows_[-1] - rows_[0] + 1) if rows_ else 0

    hs = sorted(b[3] - b[1] + 1 for b in big)
    med_h = hs[len(hs) // 2]

    def trim(part):
        ys = [y for y in range(part[1], part[3] + 1) if any(mask[y][part[0]:part[2] + 1])]
        if not ys:
            return None
        xs = [xx for xx in range(part[0], part[2] + 1)
              if any(mask[y][xx] for y in range(ys[0], ys[-1] + 1))]
        return [xs[0], ys[0], xs[-1], ys[-1]]

    def split(b, depth=0):
        bw, bh = b[2] - b[0] + 1, b[3] - b[1] + 1
        if depth > 5:
            return [b]
        if bw >= med_w * 1.6:                       # dos poses lado a lado
            prof = column_profile(b)
            lo, hi = int(bw * 0.25), int(bw * 0.75)
            cut = min(range(lo, hi + 1), key=lambda i: (prof[i], abs(i - bw / 2)))
            peak = min(max(prof[:cut + 1]), max(prof[cut:]))
            deep = prof[cut] <= 0.3 * peak
            if prof[cut] <= bh * 0.25 or prof[cut] <= 0.45 * peak:
                x = b[0] + cut
                left, right = trim([b[0], b[1], x - 1, b[3]]), trim([x + 1, b[1], b[2], b[3]])
                if left and right:
                    hl, hr = left[3] - left[1] + 1, right[3] - right[1] + 1
                    wl, wr = left[2] - left[0] + 1, right[2] - right[0] + 1
                    if min(hl, hr) >= bh * 0.6 or (deep and min(hl, hr) >= bh * 0.5
                                                   and min(wl, wr) >= med_w * 0.4):
                        return split(left, depth + 1) + split(right, depth + 1)
        if bh >= med_h * 1.6:                       # dos poses una arriba de la otra
            rprof = [sum(mask[y][b[0]:b[2] + 1]) for y in range(b[1], b[3] + 1)]
            lo, hi = int(bh * 0.25), int(bh * 0.75)
            cut = min(range(lo, hi + 1), key=lambda i: (rprof[i], abs(i - bh / 2)))
            peak = min(max(rprof[:cut + 1]), max(rprof[cut:]))
            if rprof[cut] <= 0.3 * peak:
                y = b[1] + cut
                top, bot = trim([b[0], b[1], b[2], y - 1]), trim([b[0], y + 1, b[2], b[3]])
                if top and bot and min(top[3] - top[1], bot[3] - bot[1]) >= med_h * 0.35 \
                        and min(top[2] - top[0], bot[2] - bot[0]) >= med_w * 0.4:
                    return split(top, depth + 1) + split(bot, depth + 1)
        return [b]

    big = [p for b in big for p in split(b)]
    # logos o letreros muy alargados
    big = [b for b in big if (b[2] - b[0] + 1) <= 2.8 * (b[3] - b[1] + 1)]
    if not big:
        return [], mask

    # 3) cada pieza chica (zzz, ?, globos, sombras, polvo...) se une a la figura
    #    más cercana si está a menos de ATTACH_DIST de su altura máxima
    limit = tallest * ATTACH_DIST
    grown = [list(b) for b in big]
    attached, pending = [], []
    for e in extras:
        # elige la pose más cercana al CENTRO de la pieza (así el polvo o la
        # sombra bajo los pies no se va con la pose de la fila de abajo)
        ex, ey = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
        best, score = None, None
        for k, b in enumerate(big):
            dx = max(b[0] - ex, ex - b[2], 0)
            dy = max(b[1] - ey, ey - b[3], 0)
            d = dx * dx + dy * dy
            if score is None or d < score:
                best, score = k, d
        if best is None:
            continue
        b = big[best]
        dx = max(b[0] - e[2], e[0] - b[2], 0)
        dy = max(b[1] - e[3], e[1] - b[3], 0)
        dist = (dx * dx + dy * dy) ** 0.5
        if dist <= limit:
            g = grown[best]
            g[0], g[1] = min(g[0], e[0]), min(g[1], e[1])
            g[2], g[3] = max(g[2], e[2]), max(g[3], e[3])
            attached.append((e, best))
        else:
            pending.append(e)

    # piezas en cadena (la segunda z junto a la primera, etc.)
    changed = True
    while changed and pending:
        changed = False
        for e in list(pending):
            for a, k in attached:
                dx = max(a[0] - e[2], e[0] - a[2], 0)
                dy = max(a[1] - e[3], e[1] - a[3], 0)
                if (dx * dx + dy * dy) ** 0.5 <= limit:
                    g = grown[k]
                    g[0], g[1] = min(g[0], e[0]), min(g[1], e[1])
                    g[2], g[3] = max(g[2], e[2]), max(g[3], e[3])
                    attached.append((e, k))
                    pending.remove(e)
                    changed = True
                    break
    # recuadros lisos: si están justo arriba de una pose son un globo de diálogo
    # ("Nyah", "Zzz..."); si no, son títulos y se ignoran
    for e in panels:
        ecy = (e[1] + e[3]) / 2
        best, dist = None, None
        for k, b in enumerate(grown):
            dx = max(b[0] - e[2], e[0] - b[2], 0)
            dy = max(b[1] - e[3], e[1] - b[3], 0)
            d = (dx * dx + dy * dy) ** 0.5
            if dist is None or d < dist:
                best, dist = k, d
        if best is not None and dist <= limit:
            g = grown[best]
            gw = g[2] - g[0] + 1
            ecx = (e[0] + e[2]) / 2
            if (e[3] <= g[1] + (g[3] - g[1]) * 0.25 and ecy < g[1]
                    and e[2] - e[0] + 1 <= gw * 1.5
                    and g[0] - gw * 0.6 <= ecx <= g[2] + gw * 0.6):
                g[0], g[1] = min(g[0], e[0]), min(g[1], e[1])
                g[2], g[3] = max(g[2], e[2]), max(g[3], e[3])
    boxes = grown

    # agrupa en filas: poses vecinas que se enciman bastante en vertical
    widths = sorted(b[2] - b[0] + 1 for b in boxes)
    near = widths[len(widths) // 2] * 1.5
    k = len(boxes)
    link = list(range(k))

    def root(i):
        while link[i] != i:
            link[i] = link[link[i]]
            i = link[i]
        return i

    for i in range(k):
        a = boxes[i]
        for j in range(i + 1, k):
            c = boxes[j]
            gapx = max(a[0] - c[2], c[0] - a[2], 0)
            overlap = min(a[3], c[3]) - max(a[1], c[1]) + 1
            if gapx <= near and overlap >= 0.6 * min(a[3] - a[1] + 1, c[3] - c[1] + 1):
                link[root(i)] = root(j)
    rows = {}
    for i in range(k):
        rows.setdefault(root(i), []).append(boxes[i])
    # orden de arriba hacia abajo según la parte más alta de cada fila
    rows = sorted(rows.values(), key=lambda r: (min(b[1] for b in r), min(b[0] for b in r)))
    return [sorted(r, key=lambda b: b[0]) for r in rows], mask


def parse_anim(spec):
    """[(fila, pose), (fila, desde, hasta), ...] -> [(fila, pose), ...]"""
    out = []
    for item in spec:
        if len(item) == 3:
            f, a, b = item
            step = 1 if b >= a else -1
            out += [(f, p) for p in range(a, b + step, step)]
        else:
            out.append(tuple(item))
    return out


# ---------- Skins (varias hojas de sprites) ----------
IMAGE_EXTS = (".png", ".gif", ".jpg", ".jpeg")


def list_skins():
    """[(nombre, ruta)] de las hojas disponibles: pet.png junto al script y
    cualquier imagen dentro de la carpeta 'skins'."""
    skins = []
    for n in CUSTOM_FILES:
        path = os.path.join(BASE_DIR, n)
        if os.path.exists(path):
            skins.append((os.path.splitext(n)[0], path))
            break
    if os.path.isdir(SKINS_DIR):
        for n in sorted(os.listdir(SKINS_DIR), key=str.lower):
            if n.lower().endswith(IMAGE_EXTS):
                skins.append((os.path.splitext(n)[0], os.path.join(SKINS_DIR, n)))
    return skins


def resolve_skin_name(name, skins):
    """Busca la skin por nombre sin importar mayúsculas (y nombres viejos como 'pet')."""
    names = [n for n, _p in skins]
    if not names:
        return None
    for cand in (name, SKIN_ALIASES.get(name or "")):
        if cand:
            for n in names:
                if n.lower() == cand.lower():
                    return n
    return names[0]


def skin_config(path):
    """Ajustes propios de una skin: <misma ruta>.json (opcional). Ejemplo:
    {"animaciones": {"camina": [[0, 4, 13]]}, "mira_izquierda": false,
     "sin_espejo": ["quieta", "extra_"], "vuela": true,
     "particulas": ["#e2c6ff", "#c08bff", "#a064ff", "#7a3fe0"]}"""
    cfg = {"animaciones": ANIMATIONS, "mira_izquierda": SHEET_LOOKS_LEFT,
           "sin_espejo": SIN_ESPEJO, "vuela": False, "particulas": PARTICLE_COLORS}
    jpath = os.path.splitext(path)[0] + ".json"
    try:
        with open(jpath, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data.get("animaciones"), dict):
            anims = dict(ANIMATIONS) if data.get("combinar_con_default", True) else {}
            anims.update({k: [tuple(x) for x in v] for k, v in data["animaciones"].items()})
            cfg["animaciones"] = anims
        for k, v in data.items():                     # personaje, frases, habilidades...
            if k not in ("animaciones", "combinar_con_default"):
                cfg[k] = v
    except FileNotFoundError:
        pass
    except Exception as e:
        print("Aviso: no pude leer %s: %s" % (os.path.basename(jpath), e))
    return cfg


def resolve_poses(spec, rows):
    """Convierte [(fila, pose), (fila, desde, hasta)] en [(fila, pose)] válidos.
    Las poses pueden ser negativas: -1 es la última de la fila, -2 la penúltima...
    También acepta ["@", x, y]: la pose que está en ese punto (en píxeles) de la imagen,
    útil cuando una fila trae logos o adornos que mueven la numeración."""
    out = []
    for item in spec:
        if item and item[0] == "@":                   # ["@", x, y]: la pose en ese punto de la imagen
            px_, py_ = float(item[1]), float(item[2])
            best = None
            for fi, row in enumerate(rows):
                for pi, b in enumerate(row):
                    inside = b[0] <= px_ <= b[2] and b[1] <= py_ <= b[3]
                    d = 0 if inside else math.hypot((b[0] + b[2]) / 2 - px_, (b[1] + b[3]) / 2 - py_)
                    if best is None or d < best[0]:
                        best = (d, fi, pi)
            if best:
                out.append((best[1], best[2]))
            continue
        f = item[0]
        if not 0 <= f < len(rows):
            continue
        n = len(rows[f])
        idx = [p + n if p < 0 else p for p in item[1:]]
        if len(idx) == 2:
            a, b = idx
            step = 1 if b >= a else -1
            idx = list(range(a, b + step, step))
        out += [(f, p) for p in idx if 0 <= p < n]
    return out


def show_sheet(path=None):
    """Ventana que muestra la hoja con cada pose numerada como fila,pose."""
    if path is None:
        skins = list_skins()
        chosen = load_settings().get("skin")
        path = next((p for n, p in skins if n == chosen), skins[0][1] if skins else None)
    root = tk.Tk()
    if not path or not os.path.exists(path):
        raise SystemExit("No encontré la hoja de sprites (pet.png o la carpeta skins).")
    root.title("Poses detectadas (fila,pose) - " + os.path.basename(path))
    sheet, pixels = read_sheet(path)
    rows, _ = detect_poses(pixels, SHEET_TOLERANCE)
    c = tk.Canvas(root, width=sheet.width(), height=sheet.height(), highlightthickness=0)
    c.pack()
    c.create_image(0, 0, anchor="nw", image=sheet)
    for f, row in enumerate(rows):
        for p, (x0, y0, x1, y1) in enumerate(row):
            c.create_rectangle(x0, y0, x1, y1, outline="#ff2d55")
            c.create_text(x0 + 2, y0 + 1, anchor="nw", text="%d,%d" % (f, p),
                          fill="#ffffff", font=("Consolas", 9, "bold"))
    root.mainloop()


def sheet_grids(path, animations):
    """Recorta las poses de la hoja: {nombre: [matriz de colores o None]}.
    Todas las matrices miden lo mismo y están alineadas por los pies."""
    _sheet, pixels = read_sheet(path)
    rows, mask = detect_poses(pixels, SHEET_TOLERANCE)
    if not rows:
        return None
    specs = animations or {"quieta": [(0, 0)], "camina": [(0, 0), (0, 1)]}
    wanted = {}
    for name, spec in specs.items():
        poses = resolve_poses(spec, rows)
        if poses:
            wanted[name] = poses
        else:
            print("Aviso: la animación '%s' no tiene poses válidas en %s; se ignora."
                  % (name, os.path.basename(path)))
    if not wanted:
        return None

    used = {fp for poses in wanted.values() for fp in poses}
    fw = max(rows[f][p][2] - rows[f][p][0] + 1 for f, p in used)
    fh = max(rows[f][p][3] - rows[f][p][1] + 1 for f, p in used)

    def make(f, p):
        x0, y0, x1, y1 = rows[f][p]
        bw, bh = x1 - x0 + 1, y1 - y0 + 1
        ox, oy = (fw - bw) // 2, fh - bh            # centrada y apoyada abajo
        grid = [[None] * fw for _ in range(fh)]
        for yy in range(bh):
            mrow, prow = mask[y0 + yy], pixels[y0 + yy]
            for xx in range(bw):
                if mrow[x0 + xx]:
                    grid[oy + yy][ox + xx] = prow[x0 + xx]
        return grid

    made = {}
    return {name: [made.setdefault(fp, make(*fp)) for fp in poses]
            for name, poses in wanted.items()}


def cache_key(path, animations):
    st = os.stat(path)
    return repr((CACHE_VERSION, os.path.basename(path), st.st_size, int(st.st_mtime),
                 sorted((k, [list(x) for x in v]) for k, v in animations.items()),
                 SHEET_TOLERANCE, SHEET_BACKGROUND, SHEET_STEP, SHEET_ALPHA_MIN, BIG_PART,
                 ATTACH_DIST, LABEL_FILL))


def load_grids(path):
    """Matrices de una hoja (usando su .cache si la hoja no cambió).
    Devuelve (grids, es_hoja, config_de_la_skin)."""
    if path and os.path.exists(path):
        cfg = skin_config(path)
        cache_file = os.path.splitext(path)[0] + ".cache"
        key = cache_key(path, cfg["animaciones"])
        try:
            with open(cache_file, "rb") as fh:
                ckey, grids = pickle.loads(zlib.decompress(fh.read()))
            if ckey == key:
                return grids, True, cfg
        except Exception:
            pass
        grids = sheet_grids(path, cfg["animaciones"])
        if grids:
            try:
                with open(cache_file, "wb") as fh:
                    fh.write(zlib.compress(pickle.dumps((key, grids)), 6))
            except Exception:
                pass
            return grids, True, cfg
    raise SystemExit("No pude leer ninguna hoja de sprites. Pon pet.png junto al script "
                     "o imágenes en la carpeta 'skins'.")


def scale_grid(grid, s):
    """Cambia el tamaño de una matriz. Al reducir promedia los colores de cada
    bloque (se ve más limpio que saltarse píxeles)."""
    h, w = len(grid), len(grid[0])
    tw, th = max(1, int(round(w * s))), max(1, int(round(h * s)))
    if (tw, th) == (w, h):
        return grid
    if s >= 1:
        return [[grid[min(h - 1, int(ty / s))][min(w - 1, int(tx / s))] for tx in range(tw)]
                for ty in range(th)]
    xs = [(int(tx * w / tw), max(int(tx * w / tw) + 1, int((tx + 1) * w / tw)))
          for tx in range(tw)]
    out = []
    for ty in range(th):
        y0 = int(ty * h / th)
        y1 = max(y0 + 1, int((ty + 1) * h / th))
        rows = grid[y0:y1]
        line = []
        for x0, x1 in xs:
            n = r = g = b = 0
            for row in rows:
                for c in row[x0:x1]:
                    if c:
                        v = int(c[1:], 16)
                        r += v >> 16
                        g += v >> 8 & 255
                        b += v & 255
                        n += 1
            if n * 2 >= (x1 - x0) * (y1 - y0):
                line.append("#%02x%02x%02x" % (r // n, g // n, b // n))
            else:
                line.append(None)
        out.append(line)
    return out


def grid_to_image(grid, flip=False):
    img = tk.PhotoImage(width=len(grid[0]), height=len(grid))
    for y, row in enumerate(grid):
        cols = [TRANSPARENT if c is None else ("#020202" if c == TRANSPARENT else c)
                for c in (row[::-1] if flip else row)]
        img.put("{" + " ".join(cols) + "}", to=(0, y))
    return img


def build_animations(grids, scale, looks_left=False, sin_espejo=()):
    """{nombre: {1: [img...], -1: [img...]}} ya escaladas, más el tamaño del
    cuerpo (ancho y alto de la pose 'quieta') para calcular choques."""
    cache = {}
    anims = {}
    hit = {}                       # imagen -> (matriz, volteada) para saber si el mouse está encima
    mirrored = set()
    for name, frames in grids.items():
        fixed = name.endswith("_der") or name.endswith("_izq") or any(
            name == n or (n.endswith("_") and name.startswith(n)) for n in sin_espejo)
        normal, espejo = [], []
        for g in frames:
            gid = id(g)
            if gid not in cache:
                sg = scale_grid(g, scale)
                cache[gid] = [grid_to_image(sg), None, sg]
                hit[str(cache[gid][0])] = (sg, False)
            if not fixed and cache[gid][1] is None:
                cache[gid][1] = grid_to_image(cache[gid][2], True)
                hit[str(cache[gid][1])] = (cache[gid][2], True)
            img, flip, _ = cache[gid]
            normal.append(img)
            espejo.append(img if fixed else flip)
        if not fixed:
            mirrored.add(name)
        if fixed:
            anims[name] = {1: normal, -1: normal}
        elif looks_left:
            anims[name] = {1: espejo, -1: normal}
        else:
            anims[name] = {1: normal, -1: espejo}

    base = grids.get("quieta") or next(iter(grids.values()))
    sg = cache[id(base[0])][2]
    cols = [x for row in sg for x, c in enumerate(row) if c]
    rws = [y for y, row in enumerate(sg) if any(row)]
    body_w = (max(cols) - min(cols) + 1) if cols else len(sg[0])
    body_h = (max(rws) - min(rws) + 1) if rws else len(sg)
    return anims, body_w, body_h, hit, mirrored


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except Exception:
        pass


# ---------- Globo de texto ----------
class Bubble:
    """Globito de texto que flota sobre la cabeza de la mascota."""

    def __init__(self, root):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.win.config(bg=TRANSPARENT)
        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT, highlightthickness=0, bd=0)
        self.canvas.pack()
        self.win.withdraw()
        self.win.update_idletasks()
        try:                                   # que el globo no estorbe al mouse
            h = user32.GetAncestor(self.win.winfo_id(), GA_ROOT) or self.win.winfo_id()
            ex = user32.GetWindowLongW(h, GWL_EXSTYLE)
            user32.SetWindowLongW(h, GWL_EXSTYLE, ex | WS_EX_TRANSPARENT | WS_EX_LAYERED
                                  | WS_EX_TOOLWINDOW)
        except Exception:
            pass
        self.visible = False
        self.until = 0.0
        self.w = self.h = 0
        self.pos = None

    def show(self, text, seconds):
        c = self.canvas
        c.delete("all")
        pad, tail = 10, 10
        tid = c.create_text(pad, pad, anchor="nw", text=text, width=BUBBLE_WIDTH,
                            font=("Segoe UI", 10), fill="#1f2333")
        x0, y0, x1, y1 = c.bbox(tid)
        w, h = x1 + pad, y1 + pad
        r = 10
        pts = [r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h, w - r, h,
               w / 2 + 8, h, w / 2, h + tail, w / 2 - 8, h, r, h, 0, h, 0, h - r, 0, r, 0, 0]
        poly = c.create_polygon(pts, smooth=True, fill="#fffdf6", outline="#3a3f58", width=2)
        c.tag_lower(poly)
        self.w, self.h = int(w) + 3, int(h + tail) + 3
        c.config(width=self.w, height=self.h)
        c.move("all", 1, 1)
        self.until = time.perf_counter() + seconds
        self.pos = None
        if not self.visible:
            self.win.deiconify()
            self.visible = True

    def hide(self):
        if self.visible:
            self.win.withdraw()
            self.visible = False

    def follow(self, cx, top, monitor, now):
        if not self.visible:
            return
        if now >= self.until:
            self.hide()
            return
        l, t, r, b = monitor
        x = int(min(max(cx - self.w / 2, l + 2), r - self.w - 2))
        y = int(top - self.h - 2)
        if y < t:
            y = t + 2
        if (x, y) != self.pos:
            self.win.geometry("+%d+%d" % (x, y))
            self.pos = (x, y)


# ---------- Galleta ----------
class Treat:
    """Galleta que cae al piso (o sobre una ventana). Se puede arrastrar."""

    SIZE = 26

    def __init__(self, root, x, y):
        s = self.SIZE
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        c = tk.Canvas(self.win, width=s, height=s, bg=TRANSPARENT, highlightthickness=0, bd=0)
        c.pack()
        c.create_oval(1, 1, s - 2, s - 2, fill="#d9a05b", outline="#7a4a1d", width=2)
        for cx, cy in ((8, 8), (16, 7), (11, 15), (18, 16), (7, 17)):
            c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill="#4a2a12", outline="")
        c.bind("<ButtonPress-1>", self.on_press)
        c.bind("<B1-Motion>", self.on_drag)
        c.bind("<ButtonRelease-1>", self.on_release)
        self.x, self.y = float(x), float(y)          # centro abajo
        self.vy = 0.0
        self.landed = False
        self.dragging = False
        self.drag_off = (0, 0)
        self.pos = None

    def on_press(self, e):
        self.dragging = True
        self.landed = False
        self.drag_off = (self.x - e.x_root, self.y - e.y_root)

    def on_drag(self, e):
        self.x = e.x_root + self.drag_off[0]
        self.y = e.y_root + self.drag_off[1]
        self.place()

    def on_release(self, e):
        self.dragging = False
        self.vy = 0.0

    def update(self, dt, pet):
        if self.dragging or self.landed:
            self.place()
            return
        prev = self.y
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL_SPEED)
        self.y += self.vy * dt
        m = pet.monitor_at(self.x, self.y - 5)
        self.x = min(max(self.x, m[0] + self.SIZE), m[2] - self.SIZE)
        for i, (hwnd, l, t, r, b, standable) in enumerate(pet.windows):
            if standable and l + 6 <= self.x <= r - 6 and prev <= t <= self.y \
                    and pet.point_visible(self.x, t + 3, i) and t - pet.BH >= m[1]:
                self.y = float(t)
                self.landed = True
                self.surface = hwnd
                break
        else:
            if self.y >= m[3]:
                self.y = float(m[3])
                self.landed = True
                self.surface = None
        self.place()

    def place(self):
        pos = (int(self.x - self.SIZE / 2), int(self.y - self.SIZE))
        if pos != self.pos:
            self.win.geometry("+%d+%d" % pos)
            self.pos = pos

    def still_there(self):
        """Si cayó sobre una ventana que ya se movió o cerró, vuelve a caer."""
        if self.landed and getattr(self, "surface", None) is not None:
            if not window_ok(self.surface) or abs(visible_rect(self.surface)[1] - self.y) > 2:
                self.landed = False
                self.vy = 0.0

    def destroy(self):
        self.win.destroy()


# ---------- Ventana para crear un recordatorio ----------
class ReminderDialog:
    def __init__(self, root, on_save):
        self.on_save = on_save
        w = self.win = tk.Toplevel(root)
        w.title("Nuevo recordatorio")
        w.attributes("-topmost", True)
        w.resizable(False, False)
        frm = tk.Frame(w, padx=14, pady=12)
        frm.pack()
        tk.Label(frm, text="¿Qué te recuerdo?").grid(row=0, column=0, columnspan=3, sticky="w")
        self.text = tk.Entry(frm, width=40)
        self.text.grid(row=1, column=0, columnspan=3, pady=(2, 10), sticky="we")
        tk.Label(frm, text="En / cada").grid(row=2, column=0, sticky="w")
        self.mins = tk.Spinbox(frm, from_=1, to=720, width=6)
        self.mins.delete(0, "end")
        self.mins.insert(0, "30")
        self.mins.grid(row=2, column=1, sticky="w", padx=6)
        tk.Label(frm, text="minutos").grid(row=2, column=2, sticky="w")
        self.repeat = tk.BooleanVar(value=False)
        tk.Checkbutton(frm, text="Repetir siempre (se guarda)", variable=self.repeat) \
            .grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))
        btns = tk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, sticky="e", pady=(12, 0))
        tk.Button(btns, text="Cancelar", width=10, command=w.destroy).pack(side="right")
        tk.Button(btns, text="Guardar", width=10, command=self.save).pack(side="right", padx=6)
        w.bind("<Return>", lambda e: self.save())
        w.bind("<Escape>", lambda e: w.destroy())
        w.update_idletasks()
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        w.geometry("+%d+%d" % ((sw - w.winfo_width()) // 2, (sh - w.winfo_height()) // 3))
        w.focus_force()
        self.text.focus_set()

    def save(self):
        text = self.text.get().strip()
        try:
            mins = max(1, int(float(self.mins.get())))
        except ValueError:
            mins = 30
        if text:
            self.on_save(text, mins, self.repeat.get())
        self.win.destroy()


# ---------- Partículas (brillitos al volar) ----------
class Particles:
    """Ventana transparente que se mueve con la mascota y dibuja brillitos."""

    def __init__(self, root, size=320):
        self.size = size
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.win.config(bg=TRANSPARENT)
        self.canvas = tk.Canvas(self.win, width=size, height=size, bg=TRANSPARENT,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.win.withdraw()
        self.win.update_idletasks()
        self.hwnd = user32.GetAncestor(self.win.winfo_id(), GA_ROOT) or self.win.winfo_id()
        try:                                   # que no estorbe al mouse
            ex = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE,
                                  ex | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW)
        except Exception:
            pass
        self.items = []
        self.parts = []        # [x, y, vx, vy, edad, vida, tamaño, color, forma]
        self.visible = False
        self.colors = list(PARTICLE_COLORS)
        self.origin = None

    def resize(self, size):
        if size != self.size:
            self.size = size
            self.canvas.config(width=size, height=size)
            self.origin = None

    def emit(self, n, cx, cy, spread_x, spread_y, up=40.0, colors=None, speed=(10, 55),
             life=None, size=(2.0, 4.5), star=0.35, g=-8.0, drag=0.96, angle=None, cone=0.5):
        """Lanza n partículas alrededor de (cx, cy).
        angle: dirección en radianes (0 = derecha) para disparos; cone: apertura."""
        colors = colors or self.colors
        for _ in range(n):
            if len(self.parts) >= PARTICLES_MAX:
                break
            ang = random.uniform(0, 6.283) if angle is None else angle + random.uniform(-cone, cone)
            spd = random.uniform(*speed)
            self.parts.append([cx + random.uniform(-spread_x, spread_x),
                               cy + random.uniform(-spread_y, spread_y),
                               spd * math.cos(ang), spd * math.sin(ang) - up,
                               0.0, random.uniform(*(life or PARTICLE_LIFE)),
                               random.uniform(*size), random.choice(colors[:-1] or colors),
                               random.random() < star, colors[-1], g, drag])

    def update(self, dt, cx, cy):
        """Mueve las partículas y redibuja. (cx, cy) = centro de la ventana."""
        alive = []
        for p in self.parts:
            p[4] += dt
            if p[4] < p[5]:
                p[0] += p[2] * dt
                p[1] += p[3] * dt
                p[2] *= p[11]
                p[3] = p[3] * p[11] - p[10] * dt
                alive.append(p)
        self.parts = alive
        if not alive:
            if self.visible:
                self.win.withdraw()
                self.visible = False
            return
        if not self.visible:
            self.win.deiconify()
            self.visible = True
        ox, oy = int(cx - self.size / 2), int(cy - self.size / 2)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, ox, oy, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE)
        c = self.canvas
        while len(self.items) < len(alive):
            self.items.append([c.create_oval(0, 0, 0, 0, outline="", state="hidden"),
                               c.create_polygon(0, 0, 0, 0, 0, 0, outline="", state="hidden"),
                               0, None])               # [óvalo, estrella, forma visible, color]
        for i, p in enumerate(alive):
            it = self.items[i]
            oval, star = it[0], it[1]
            k = 1.0 - p[4] / p[5]                          # se encoge al apagarse
            r = max(0.6, p[6] * (0.4 + 0.6 * k))
            x, y = p[0] - ox, p[1] - oy
            color = p[7] if k > 0.35 else p[9]
            shape = 2 if p[8] else 1
            if shape == 2:                                 # destellito de 4 puntas
                R, q = r * 2.0, r * 0.45
                c.coords(star, x, y - R, x + q, y - q, x + R, y, x + q, y + q,
                         x, y + R, x - q, y + q, x - R, y, x - q, y - q)
            else:
                c.coords(oval, x - r, y - r, x + r, y + r)
            if shape != it[2] or color != it[3]:          # solo cambia lo necesario
                show, hide = (star, oval) if shape == 2 else (oval, star)
                c.itemconfig(show, fill=color, state="normal")
                if it[2] != 0 and shape != it[2]:
                    c.itemconfig(hide, state="hidden")
                it[2], it[3] = shape, color
        for it in self.items[len(alive):]:
            if it[2]:
                c.itemconfig(it[0], state="hidden")
                c.itemconfig(it[1], state="hidden")
                it[2] = 0

    def clear(self):
        self.parts = []
        if self.visible:
            self.win.withdraw()
            self.visible = False


# ---------- Rayo (ventana temporal que dibuja una línea brillante) ----------
class Beam:
    """Rayo de luz de (x0, y0) a (x1, y1) que dura 'seconds' y se desvanece."""

    def __init__(self, root, x0, y0, x1, y1, colors, width=12, seconds=0.45):
        pad = width * 2 + 20
        self.left = int(min(x0, x1) - pad)
        self.top = int(min(y0, y1) - pad)
        w = int(abs(x1 - x0) + pad * 2)
        h = int(abs(y1 - y0) + pad * 2)
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.win.config(bg=TRANSPARENT)
        self.win.geometry("%dx%d+%d+%d" % (w, h, self.left, self.top))
        self.canvas = c = tk.Canvas(self.win, width=w, height=h, bg=TRANSPARENT,
                                    highlightthickness=0, bd=0)
        c.pack()
        ax, ay, bx, by = x0 - self.left, y0 - self.top, x1 - self.left, y1 - self.top
        self.lines = []
        for frac, col in ((1.0, colors[-1]), (0.6, colors[min(1, len(colors) - 1)]),
                          (0.25, colors[0])):
            self.lines.append((c.create_line(ax, ay, bx, by, width=max(1, int(width * frac)),
                                             fill=col, capstyle="round"), frac))
        r = width * 1.6                                     # destello donde pega
        self.flash = c.create_oval(bx - r, by - r, bx + r, by + r, fill=colors[0], outline="")
        self.width = width
        self.born = time.perf_counter()
        self.seconds = seconds
        self.alive = True
        self.win.update_idletasks()
        try:
            hwnd = user32.GetAncestor(self.win.winfo_id(), GA_ROOT) or self.win.winfo_id()
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                  ex | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW)
        except Exception:
            pass

    def update(self, now):
        if not self.alive:
            return False
        k = (now - self.born) / self.seconds
        if k >= 1:
            self.destroy()
            return False
        shrink = 1.0 - k * k
        for item, frac in self.lines:
            self.canvas.itemconfig(item, width=max(1, int(self.width * frac * shrink)))
        return True

    def destroy(self):
        if self.alive:
            self.alive = False
            try:
                self.win.destroy()
            except Exception:
                pass


# ---------- Proyectiles (lucero de Rem, cristales, carámbanos...) ----------
class Projectile:
    """Ventanita transparente que dibuja un proyectil y lo mueve por la pantalla.
    kind: "lucero" (bola con picos y cadena que va y regresa), "giro" (el lucero
    girando alrededor de la dueña), "cristal", "hielo" o "bala" (bolita de luz)."""

    MARGIN = 26

    def __init__(self, app, owner, kind, tx, ty, colors, target=None, delay=0.0,
                 grab_cursor=False, on_reach=None, big=False):
        self.app, self.owner, self.kind = app, owner, kind
        self.colors = colors
        self.target = target
        self.hit_done = False
        self.grab_cursor = grab_cursor
        self.on_reach = on_reach
        self.big = big
        self.cursor_goal = (tx, ty)
        self.carrying = False
        hx, hy = owner.hand_front()
        self.x, self.y = float(hx), float(hy)
        self.start = time.perf_counter() + delay
        ang = math.atan2(ty - hy, tx - hx)
        self.dx, self.dy = math.cos(ang), math.sin(ang)
        self.angle = ang
        dist = math.hypot(tx - hx, ty - hy)
        if kind == "corte":
            self.MARGIN = 44
        if kind == "lucero":
            self.reach = min(max(dist + 20, 120), LUCERO_REACH)
            self.speed = 950
        elif kind == "mano":
            self.reach = min(max(dist + 10, 120), SHOT_RANGE)
            self.speed = 800
        elif kind == "corte":
            self.reach = dist if on_reach else min(dist + 200, 1800)
            self.speed = 1300
        else:
            self.reach = min(dist + 120, 1600)
            self.speed = {"cristal": 760, "hielo": 820, "bala": 900}.get(kind, 800)
        self.travel = 0.0
        self.phase = "go"
        self.boom_t = 0.0
        self.spin = 0.0
        self.alive = True
        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.win.config(bg=TRANSPARENT)
        self.canvas = tk.Canvas(self.win, width=10, height=10, bg=TRANSPARENT,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.win.withdraw()
        self.shown = False
        self.geom = None
        self.win.update_idletasks()
        try:
            hwnd = user32.GetAncestor(self.win.winfo_id(), GA_ROOT) or self.win.winfo_id()
            ex = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                                  ex | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW)
        except Exception:
            pass

    # --- lógica ---
    def target_center(self):
        t = self.target
        return t.x, t.y + t.y_off - t.BH * 0.5

    def check_hit(self):
        t = self.target
        if self.hit_done or t is None or t not in self.app.pets or t.hidden:
            return False
        cx, cy = self.target_center()
        if abs(self.x - cx) < t.BW * 0.55 + 8 and abs(self.y - cy) < t.BH * 0.5 + 8:
            self.hit_done = True
            self.owner.projectile_hit(t, self)
            return True
        return False

    def update(self, now, dt):
        if not self.alive:
            return False
        if now < self.start:
            return True
        owner = self.owner
        if owner not in self.app.pets:
            self.destroy()
            return False
        if self.kind == "giro":                       # gira alrededor de la dueña
            self.spin += dt * 11
            cx, cy = owner.x, owner.y + owner.y_off - owner.BH * 0.5
            r = owner.BW * 0.55 + 40
            self.x, self.y = cx + math.cos(self.spin) * r, cy + math.sin(self.spin) * r * 0.55
            for p in self.app.others(owner):
                if p.state not in ("air", "drag", "tp") and \
                        abs(p.x - self.x) < p.BW * 0.5 + 8 and \
                        abs((p.y - p.BH * 0.5) - self.y) < p.BH * 0.5 and \
                        p not in getattr(self, "hit_set", set()):
                    self.hit_set = getattr(self, "hit_set", set()) | {p}
                    owner.projectile_hit(p, self)
            if now - self.start > 1.8:
                self.destroy()
                return False
        elif self.phase == "go":
            step = self.speed * dt
            self.x += self.dx * step
            self.y += self.dy * step
            self.travel += step
            self.spin += dt * 14
            hit = self.check_hit()
            if self.grab_cursor and math.hypot(self.x - self.cursor_goal[0],
                                               self.y - self.cursor_goal[1]) < 16:
                self.carrying = not mouse_down()          # atrapó el mouse
                hit = True
            if self.on_reach and self.travel >= self.reach - 4:
                cb, self.on_reach = self.on_reach, None
                try:
                    cb(self)
                except Exception as e:
                    print("Aviso:", e)
            if hit or self.travel >= self.reach or self.off_screen():
                if self.kind in ("lucero", "mano"):
                    self.phase = "back"
                else:
                    self.phase = "boom"
                    self.boom_t = now
        elif self.phase == "back":                    # el lucero regresa a su mano
            hx, hy = owner.hand_front()
            ddx, ddy = hx - self.x, hy - self.y
            d = math.hypot(ddx, ddy)
            step = 1150 * dt
            self.spin += dt * 14
            if d <= step + 4:
                self.destroy()
                return False
            self.x += ddx / d * step
            self.y += ddy / d * step
            if self.carrying:                              # se trae el mouse
                if mouse_down():
                    self.carrying = False
                else:
                    user32.SetCursorPos(int(self.x), int(self.y))
        elif self.phase == "boom":
            if now - self.boom_t > 0.28:
                self.destroy()
                return False
        self.draw(now)
        return True

    def off_screen(self):
        vs = self.owner.virtual_screen()
        return not (vs[0] - 50 <= self.x <= vs[2] + 50 and vs[1] - 50 <= self.y <= vs[3] + 50)

    # --- dibujo ---
    def draw(self, now):
        c = self.canvas
        c.delete("all")
        pts = [(self.x, self.y)]
        anchor = None
        if self.kind in ("lucero", "giro", "mano"):
            hx, hy = self.owner.hand_front() if self.kind in ("lucero", "mano") else \
                (self.owner.x, self.owner.y + self.owner.y_off - self.owner.BH * 0.5)
            anchor = (hx, hy)
            pts.append(anchor)
        left = int(min(p[0] for p in pts) - self.MARGIN)
        top = int(min(p[1] for p in pts) - self.MARGIN)
        w = int(max(p[0] for p in pts) - left + self.MARGIN)
        h = int(max(p[1] for p in pts) - top + self.MARGIN)
        geom = (w, h, left, top)
        if geom != self.geom:
            self.win.geometry("%dx%d+%d+%d" % geom)
            c.config(width=w, height=h)
            self.geom = geom
        x, y = self.x - left, self.y - top
        col = self.colors
        if anchor and self.kind == "mano":               # brazo de sombra
            ax, ay = anchor[0] - left, anchor[1] - top
            c.create_line(ax, ay, x, y, fill=col[-1], width=7, smooth=True, capstyle="round")
            c.create_line(ax, ay, x, y, fill=col[1], width=3, capstyle="round")
        elif anchor:                                     # cadena
            ax, ay = anchor[0] - left, anchor[1] - top
            c.create_line(ax, ay, x, y, fill="#5b6068", width=3, dash=(4, 2))
        if self.phase == "boom":
            k = min(1.0, (now - self.boom_t) / 0.28)
            r = 5 + 20 * k
            c.create_oval(x - r, y - r, x + r, y + r, outline=col[1], width=3)
            c.create_oval(x - r * 0.5, y - r * 0.5, x + r * 0.5, y + r * 0.5,
                          fill=col[0], outline="")
        elif self.kind in ("lucero", "giro"):           # bola de metal con picos
            r = 9
            for i in range(8):
                a = self.spin + i * math.pi / 4
                c.create_line(x + math.cos(a) * r * 0.6, y + math.sin(a) * r * 0.6,
                              x + math.cos(a) * (r + 7), y + math.sin(a) * (r + 7),
                              fill="#3b3f46", width=3)
            c.create_oval(x - r, y - r, x + r, y + r, fill="#9aa1ab", outline="#2f3338", width=2)
            c.create_oval(x - r * 0.5, y - r * 0.6, x - r * 0.05, y - r * 0.15, fill="#e8ecf2",
                          outline="")
        elif self.kind == "mano":                        # mano de sombra
            a = self.angle if self.phase == "go" else self.angle + math.pi
            r = 8
            for i in range(4):
                fa = a + (i - 1.5) * 0.38
                c.create_line(x, y, x + math.cos(fa) * (r + 9), y + math.sin(fa) * (r + 9),
                              fill=col[-1], width=4, capstyle="round")
            c.create_oval(x - r, y - r, x + r, y + r, fill=col[-1], outline=col[1], width=2)
            c.create_oval(x - 2, y - 2, x + 2, y + 2, fill=col[0], outline="")
        elif self.kind == "corte":                       # media luna de espada
            r = 30 if self.big else 20
            deg = -math.degrees(self.angle)
            for wdt, cc in ((9, col[-1]), (5, col[1]), (2, col[0])):
                c.create_arc(x - r, y - r, x + r, y + r, start=deg - 70, extent=140,
                             style="arc", outline=cc, width=wdt)
        elif self.kind in ("cristal", "hielo"):          # punta alargada
            L, W = (26, 8) if self.kind == "cristal" else (32, 6)
            ca, sa = math.cos(self.angle), math.sin(self.angle)
            tip = (x + ca * L / 2, y + sa * L / 2)
            back = (x - ca * L / 2, y - sa * L / 2)
            side1 = (x - sa * W / 2 - ca * L * 0.1, y + ca * W / 2 - sa * L * 0.1)
            side2 = (x + sa * W / 2 - ca * L * 0.1, y - ca * W / 2 - sa * L * 0.1)
            c.create_polygon(*tip, *side1, *back, *side2, fill=col[1], outline=col[-1], width=2)
            c.create_line(back[0], back[1], tip[0], tip[1], fill=col[0], width=1)
        else:                                            # bolita de luz
            r = 7
            c.create_oval(x - r * 1.8, y - r * 1.8, x + r * 1.8, y + r * 1.8, fill=col[-1],
                          outline="")
            c.create_oval(x - r, y - r, x + r, y + r, fill=col[1], outline="")
            c.create_oval(x - r * 0.5, y - r * 0.5, x + r * 0.5, y + r * 0.5, fill=col[0],
                          outline="")
        if not self.shown:
            self.win.deiconify()
            self.shown = True

    def destroy(self):
        if self.alive:
            self.alive = False
            try:
                self.win.destroy()
            except Exception:
                pass


# ---------- La mascota ----------
# Posición: (x, y) es el punto entre los pies (centro abajo) en coordenadas de pantalla.
FALLBACK = {"corre": "camina", "camina": "quieta", "sentada": "quieta", "dormida": "quieta",
            "trepa": "camina", "salta": "cae", "cae": "quieta", "arrastrada": "cae",
            "empuja": "camina", "vuela": "salta"}
WALKING_ANIMS = {"camina", "corre", "empuja"}
SIZES = [0.4, 0.5, 0.6, 0.7, 0.85, 1.0, 1.25, 1.5]


class Pet:
    def __init__(self, app, cfg):
        self.app = app
        self.root = root = app.root
        self.cfg = cfg                                   # {"skin": ..., "escala": ...}
        self.scale = float(cfg.get("escala") or SHEET_SCALE)
        self.skins = list_skins()
        if not self.skins:
            raise SystemExit("No encontré skins: pon pet.png junto al script o imágenes "
                             "en la carpeta 'skins'.")
        self.skin = resolve_skin_name(cfg.get("skin"), self.skins)
        cfg["skin"] = self.skin or ""
        cfg["escala"] = self.scale
        self.grids, self.is_sheet, self.skin_cfg = load_grids(self.skin_path())

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        try:
            self.win.attributes("-transparentcolor", TRANSPARENT)
        except tk.TclError:
            pass
        self.win.config(bg=TRANSPARENT)
        self.canvas = tk.Canvas(self.win, width=10, height=10, bg=TRANSPARENT,
                                highlightthickness=0, bd=0)
        self.canvas.pack()
        self.canvas.config(cursor="hand2")
        self.item = self.canvas.create_image(0, 0, anchor="nw")
        self.cur_img = None
        self.apply_scale(self.scale)

        self.win.update_idletasks()
        self.hwnd = user32.GetAncestor(self.win.winfo_id(), GA_ROOT) or self.win.winfo_id()
        ex = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, (ex | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW)

        self.next_topmost = 0.0

        m = random.choice(self.monitors)
        self.x = float(random.randint(m[0] + self.BW, max(m[0] + self.BW, m[2] - self.BW)))
        self.y = float(m[1] + self.BH)
        self.vx = 0.0
        self.vy = 0.0
        self.facing = 1
        self.surface = None          # None = piso del monitor, o hwnd de la ventana pisada
        self.surf_rect = None
        self.ignore = None           # ventana de la que se acaba de bajar
        self.state = "air"           # idle walk sit sleep goto air climb drag oneshot
        self.timer = 0.0
        self.paused = False
        self.climb = None            # (hwnd, lado)
        self.goto_x = None
        self.goto_cb = None
        self.edge_choice = None
        self.after_oneshot = None
        self.anim_name = "cae"
        self.anim_t = 0.0
        self.anim_loop = True
        self.walk_dist = 0.0
        self.press = None
        self.drag_samples = []
        self.win_pos = None
        self.last = time.perf_counter()
        self.shown_facing = 1
        self.turn_until = None
        self.oneshot_end = 0.0
        self.click_through = False
        self.grab = None
        self.bubble = Bubble(root)
        self.particles = Particles(root, self.particle_size())
        self.particles.colors = list(self.skin_cfg.get("particulas") or PARTICLE_COLORS)
        self.fly_until = 0.0
        self.fly_mode = "wander"
        self.fly_target = None
        self.fly_land = None
        self.fly_phase = 0.0
        self.fly_catch = False
        self.p_acc = 0.0
        self.y_off = 0.0
        self.fight = False
        self.mgrab = None
        self.last_dt = 0.016
        self.treat_tries = 0
        self.chase_until = 0.0
        self.jump_cd = 0.0
        self.tag_cd = 0.0
        self.push = None
        self.fx = []
        self.buff_until = 0.0
        self.hidden = False
        self.tp_until = 0.0
        self.tp_dest = None
        self.beam = None
        self.pose_until = 0.0

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_menu)
        self.build_menu()

    # ---------- lo que comparten todas las mascotas ----------
    @property
    def windows(self):
        return self.app.windows

    @property
    def monitors(self):
        return self.app.monitors

    @property
    def treat(self):
        return self.app.treat

    @treat.setter
    def treat(self, value):
        self.app.treat = value

    @property
    def fly_on(self):
        return self.app.flag("volar")

    @property
    def fight_on(self):
        return self.app.flag("pelear_mouse")

    @property
    def pranks(self):
        return self.app.flag("travesuras")

    def in_game(self):
        return self.role() is not None

    def mouse_taken(self):
        return any(p.mgrab for p in self.app.others(self))

    # ---------- imágenes ----------
    def apply_scale(self, scale):
        eff = scale
        self.anims, self.BW, self.BH, self.hit, self.mirrored = build_animations(
            self.grids, eff, self.skin_cfg.get("mira_izquierda", False),
            self.skin_cfg.get("sin_espejo", []))
        first = next(iter(self.anims.values()))[1][0]
        self.W, self.H = first.width(), first.height()
        self.canvas.config(width=self.W, height=self.H)
        self.cur_img = None
        self.win_pos = None
        self.scale = scale
        if hasattr(self, "particles"):
            self.particles.resize(self.particle_size())

    def particle_size(self):
        return int(max(self.BW, self.BH) * 2.4) + 60

    def can_fly(self):
        return bool(self.skin_cfg.get("vuela")) and self.fly_on and self.is_sheet
    def skin_path(self):
        return next((p for n, p in self.skins if n == self.skin), None)

    def set_skin(self, name):
        self.skins = list_skins()
        if name not in [n for n, _p in self.skins]:
            return
        self.skin = name
        self.say("Cambiando de skin...", 2)
        self.win.update_idletasks()
        self.grids, self.is_sheet, self.skin_cfg = load_grids(self.skin_path())
        self.apply_scale(self.scale)
        self.particles.colors = list(self.skin_cfg.get("particulas") or PARTICLE_COLORS)
        self.cfg["skin"] = self.skin or ""
        self.app.save()
        self.bubble.hide()
        if self.state == "fly" and not self.can_fly():
            self.to_air(0)

    def frames(self, name):
        side = "_der" if self.facing == 1 else "_izq"
        n = name
        for _ in range(10):
            if n + side in self.anims:
                return self.anims[n + side][self.facing]
            if n in self.anims:
                return self.anims[n][self.facing]
            n = FALLBACK.get(n, "quieta")
        return next(iter(self.anims.values()))[self.facing]

    def has_anim(self, name):
        return name in self.anims or name + "_der" in self.anims or name + "_izq" in self.anims

    def set_anim(self, name, loop=True):
        if name != self.anim_name or loop != self.anim_loop:
            self.anim_name = name
            self.anim_t = 0.0
            self.anim_loop = loop

    def current_image(self):
        frames = self.frames(self.anim_name)
        n = len(frames)
        if self.anim_name in WALKING_ANIMS or (self.anim_name == "trepa" and self.state == "climb"):
            idx = int(self.walk_dist / WALK_STRIDE)
        else:
            if self.anim_name == "dormida":
                fps = SLEEP_FPS
            elif self.state == "oneshot":
                fps = ONESHOT_FPS
            else:
                fps = ANIM_FPS
            idx = int(self.anim_t * fps)
        return frames[idx % n] if self.anim_loop else frames[min(idx, n - 1)]

    def oneshot_done(self):
        return time.perf_counter() >= self.oneshot_end

    # ---------- ciclo principal ----------
    def tick(self, dt, now):
        try:
            self.update(dt, now)
            self.draw(now)
        except Exception as e:                     # que un error raro no la congele
            print("Aviso:", e)
            self.to_air(0)

    def update(self, dt, now):
        self.anim_t += dt
        self.last_dt = dt
        self.react_treat()
        self.update_fx(dt, now)
        s = self.state
        if s == "drag":
            return
        if s == "tp":
            self.update_tp(now)
            return
        if s == "air":
            self.update_air(dt)
        elif s == "climb":
            self.update_climb(dt)
        elif s == "fly":
            self.update_fly(dt, now)
        else:
            self.update_ground(dt)

    def draw(self, now):
        if self.anim_name in self.mirrored and self.state != "drag":
            if self.facing != self.shown_facing:
                if self.turn_until is None:
                    self.turn_until = now + TURN_TIME
                if now < self.turn_until:
                    img = self.frames("gira")[0]
                else:
                    self.shown_facing = self.facing
                    self.turn_until = None
                    img = self.current_image()
            else:
                img = self.current_image()
        else:
            self.shown_facing = self.facing
            self.turn_until = None
            img = self.current_image()
        self.show_image(img, now)

    def update_click_through(self, img):
        """Si el mouse no está justo sobre la mascota, la ventana se vuelve 'transparente'
        al mouse: así el cursor no parpadea cuando ella pasa por debajo."""
        if not CLICK_THROUGH:
            return
        want = True
        if self.press or self.state == "drag":
            want = False
        elif self.win_pos:
            cx, cy = cursor_pos()
            lx, ly = cx - self.win_pos[0], cy - self.win_pos[1]
            info = self.hit.get(str(img))
            if info and 0 <= lx < self.W and 0 <= ly < self.H:
                grid, flip = info
                w = len(grid[0])
                for dy in (-2, 0, 2):
                    row = grid[min(max(ly + dy, 0), len(grid) - 1)]
                    for dx in (-2, 0, 2):
                        x = min(max(lx + dx, 0), w - 1)
                        if row[w - 1 - x if flip else x]:
                            want = False
                            break
                    if not want:
                        break
        if want != self.click_through:
            ex = user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
            ex = (ex | WS_EX_TRANSPARENT) if want else (ex & ~WS_EX_TRANSPARENT)
            user32.SetWindowLongW(self.hwnd, GWL_EXSTYLE, ex)
            self.click_through = want

    def show_image(self, img, now):
        if self.hidden:
            if self.particles.parts or self.particles.visible:
                self.particles.update(self.last_dt, self.x, self.y - self.BH / 2)
            return
        if img is not self.cur_img:
            self.canvas.itemconfig(self.item, image=img)
            self.cur_img = img
        if self.particles.parts or self.particles.visible:
            self.particles.update(self.last_dt, self.x, self.y + self.y_off - self.BH / 2)
        pos = (int(round(self.x - self.W / 2)), int(round(self.y + self.y_off - self.H)))
        if pos != self.win_pos or now >= self.next_topmost or self.particles.visible:
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, pos[0], pos[1], 0, 0,
                                SWP_NOSIZE | SWP_NOACTIVATE)
            self.win_pos = pos
            if now >= self.next_topmost:
                self.next_topmost = now + 2.0
        self.update_click_through(img)
        if self.bubble.visible:
            self.bubble.follow(self.x, self.y - self.BH, self.monitor_at(self.x), now)

    # ---------- monitores ----------
    def monitor_at(self, x, y=None):
        y = self.y - self.BH / 2 if y is None else y
        for m in self.monitors:
            if m[0] <= x < m[2] and m[1] <= y < m[3]:
                return m
        return min(self.monitors, key=lambda m: max(m[0] - x, 0, x - m[2]) +
                   max(m[1] - y, 0, y - m[3]))

    def neighbor(self, m, side):
        l, t, r, b = m
        for n in self.monitors:
            if n == m:
                continue
            if side > 0 and n[0] == r and n[1] < b and n[3] > t:
                return n
            if side < 0 and n[2] == l and n[1] < b and n[3] > t:
                return n
        return None

    def clamp_to_monitor(self, m, bounce=False):
        half = self.BW / 2
        if self.x - half < m[0] and self.neighbor(m, -1) is None:
            self.x = m[0] + half
            return -1
        if self.x + half > m[2] and self.neighbor(m, 1) is None:
            self.x = m[2] - half
            return 1
        return 0

    # ---------- ventanas ----------
    def index_of(self, hwnd):
        for i, w in enumerate(self.windows):
            if w[0] == hwnd:
                return i
        return None

    def point_visible(self, px, py, idx):
        """True si el punto no está tapado por una ventana que esté encima de la idx."""
        for w in self.windows[:idx]:
            if w[1] <= px < w[3] and w[2] <= py < w[4]:
                return False
        return True

    def top_visible(self, hwnd, px, top):
        idx = self.index_of(hwnd)
        if idx is None:
            return True
        return self.point_visible(px, top + 3, idx)

    # ---------- cambios de estado ----------
    def start_idle(self, t=None):
        self.state = "idle"
        self.vx = 0
        self.timer = random.uniform(1.5, 4.0) if t is None else t
        self.set_anim("quieta")

    def start_walk(self, speed, t):
        self.vx = speed * self.spd() * random.choice([-1, 1])
        self.facing = 1 if self.vx > 0 else -1
        self.state = "walk"
        self.timer = t
        self.edge_choice = None
        self.set_anim("corre" if speed > WALK_SPEED else "camina")

    def play_once(self, name, then=None, seconds=None, loop=False):
        """Reproduce una animación (una vez, o en ciclo durante 'seconds') y luego
        llama a then() (o se queda quieta)."""
        self.state = "oneshot"
        self.vx = 0
        self.anim_name = None
        self.set_anim(name, loop=loop)
        n = len(self.frames(name))
        dur = n / ONESHOT_FPS + 0.2
        self.oneshot_end = time.perf_counter() + max(dur, seconds or 0)
        self.after_oneshot = then

    def with_intro(self, name, enter):
        if self.has_anim(name + "_inicio"):
            self.play_once(name + "_inicio", enter)
        else:
            enter()

    def start_sit(self, t=None):
        def enter():
            self.state = "sit"
            self.timer = random.uniform(6, 16) if t is None else t
            self.set_anim("sentada")
        self.vx = 0
        self.with_intro("sentada", enter)

    def start_sleep(self, t=None):
        def enter():
            self.state = "sleep"
            self.timer = random.uniform(20, 50) if t is None else t
            self.set_anim("dormida")
        self.vx = 0
        self.with_intro("dormida", enter)

    def wake(self):
        if random.random() < 0.6:
            self.speak("despierta", ["Mmm... ¿qué pasó?"], 2)
        if self.has_anim("despierta"):
            self.play_once("despierta", lambda: self.start_idle(1.0), seconds=1.6)
        else:
            self.start_idle(1.0)

    def to_air(self, vy, vx=None, leave=True):
        """Pasa al aire. leave=True: se está bajando de la ventana (no vuelve a caer en ella)."""
        if vx is not None:
            self.vx = vx
        self.ignore = self.surface if leave else None
        self.state = "air"
        self.vy = vy
        self.grab = None
        self.y_off = 0.0
        self.mgrab = None
        self.surface = None
        self.surf_rect = None
        self.climb = None
        if abs(self.vx) > 20:
            self.facing = 1 if self.vx > 0 else -1

    def jump_to(self, tx, ty):
        """Salto en arco que cae justo en (tx, ty)."""
        dy = ty - self.y
        if dy < 0:
            t = max(0.45, (2 * -dy / GRAVITY) ** 0.5 * 1.3)
        else:
            t = max(0.45, min(1.0, abs(tx - self.x) / 600))
        vx = (tx - self.x) / t
        vy = (dy - 0.5 * GRAVITY * t * t) / t
        self.to_air(vy, vx)

    def land(self, hwnd, top, rect=None):
        impact = self.vy
        self.y_off = 0.0
        self.fly_catch = False
        self.y = float(top)
        self.vy = 0
        self.vx = 0
        self.surface = hwnd
        self.surf_rect = rect
        self.ignore = None
        if self.in_game():                               # sigue jugando a las atrapadas
            self.state = "tag"
            self.set_anim("quieta")
        elif self.fight_role():                          # sigue peleando
            self.join_fight()
        elif impact > HARD_LANDING and self.has_anim("aterriza"):
            self.play_once("aterriza", lambda: self.start_idle(random.uniform(0.6, 1.5)), seconds=0.6)
        elif time.perf_counter() < self.chase_until:
            self.start_chase(None)
        else:
            self.start_idle(random.uniform(0.4, 1.8))

    # ---------- en el aire ----------
    def update_air(self, dt):
        prev_y = self.y
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL_SPEED)
        self.x += self.vx * dt
        self.y += self.vy * dt
        if abs(self.vx) > 20:
            self.facing = 1 if self.vx > 0 else -1
        self.set_anim("salta" if self.vy < 0 else "cae")
        if self.role() == "chaser":                      # la atrapó en el aire
            g = self.app.game
            if time.perf_counter() >= g["pause_until"] and self.touching(g["runner"]):
                self.app.caught()
        if self.fly_catch and self.vy > 250 and self.can_fly():   # se "atrapa" y sale volando
            self.fly_catch = False
            self.start_fly(random.uniform(3, 7))
            return
        if self.grab:                                    # brincó para agarrarse de una ventana
            hwnd, side = self.grab
            if self.vy >= -60:
                self.grab = None
                if window_ok(hwnd):
                    l, t, r, b = visible_rect(hwnd)
                    if t < self.y - self.BH * 0.3 and b > self.y - self.BH:
                        self.start_climb(hwnd, side)
                        return
            else:
                self.facing = -side

        m = self.monitor_at(self.x)
        if self.clamp_to_monitor(m):
            self.vx = -self.vx * 0.3
        if self.y - self.BH < m[1]:                      # techo de la pantalla
            self.y = m[1] + self.BH
            self.vy = max(self.vy, 0)

        if self.vy > 0:
            best = None
            for i, (hwnd, l, t, r, b, standable) in enumerate(self.windows):
                if not standable or hwnd == self.ignore:
                    continue
                if l + 4 <= self.x <= r - 4 and prev_y <= t <= self.y and t - self.BH >= m[1]:
                    if self.point_visible(self.x, t + 3, i) and (best is None or t < best[1]):
                        best = (hwnd, t, (l, t, r, b))
            if best:
                self.land(*best)
                return
            if self.y >= m[3]:
                self.land(None, m[3])

    # ---------- en el piso o sobre una ventana ----------
    def update_ground(self, dt):
        m = self.monitor_at(self.x)
        if self.surface is not None:
            if not window_ok(self.surface):
                self.to_air(0)
                return
            l, t, r, b = visible_rect(self.surface)
            if self.surf_rect:                                # la ventana se movió: la sigue
                self.x += l - self.surf_rect[0]
            self.surf_rect = (l, t, r, b)
            self.y = float(t)
            if not (l <= self.x <= r) or not self.top_visible(self.surface, self.x, t):
                self.to_air(0)
                return
            if t - self.BH < m[1]:                            # se salió por arriba
                self.to_air(0)
                return
        else:
            fl = m[3]
            if self.y < fl - 1:
                self.to_air(0)
                return
            if self.y > fl + 1:                               # piso más alto: brinca
                self.to_air(-(2 * GRAVITY * (self.y - fl + 30)) ** 0.5)
                return
            self.y = float(fl)

        s = self.state
        if s == "chase":
            self.update_chase(dt, m)
            return
        if s == "push":
            self.update_push(dt, m)
            return
        if s == "mgrab":
            self.update_mouse_grab(dt, m)
            return
        if s == "tag":
            self.update_tag(dt, m)
            return
        if s == "fight":
            self.update_fight(dt, m)
            return
        if s == "beam":
            self.update_beam(dt, time.perf_counter())
            return
        if s == "idle" and MOUSE_PLAY:
            cx, cy = cursor_pos()
            if abs(cx - self.x) > self.BW * 0.6 and abs(cx - self.x) < WATCH_MOUSE_DIST \
                    and abs(cy - (self.y - self.BH / 2)) < WATCH_MOUSE_DIST:
                self.facing = 1 if cx > self.x else -1
        if s in ("walk", "goto"):
            step = self.vx * dt
            self.x += step
            self.walk_dist += abs(step)
            if s == "goto" and abs(self.goto_x - self.x) <= abs(step) + 1:
                self.x = self.goto_x
                cb, self.goto_cb = self.goto_cb, None
                self.start_idle(0.3)
                if cb:
                    cb()
                return
            if self.surface is not None:
                l, t, r, b = self.surf_rect
                near = (self.vx < 0 and self.x - l < self.BW * 0.6) or \
                       (self.vx > 0 and r - self.x < self.BW * 0.6)
                if near:
                    if self.edge_choice is None:
                        self.edge_choice = "turn" if random.random() < 0.6 or s == "goto" else "off"
                    if self.edge_choice == "turn":
                        self.vx = -self.vx
                        self.facing = 1 if self.vx > 0 else -1
                        self.edge_choice = None
                else:
                    self.edge_choice = None
                if not (l <= self.x <= r):
                    self.to_air(-150)
                    return
            else:
                hit = self.clamp_to_monitor(m)
                if hit:
                    if s == "goto":
                        self.start_idle()
                        return
                    self.vx = -self.vx
                    self.facing = 1 if self.vx > 0 else -1
                if NUDGE_WINDOWS:
                    self.nudge(m, step)
        elif s == "oneshot":
            if self.oneshot_done():
                cb, self.after_oneshot = self.after_oneshot, None
                self.start_idle()
                if cb:
                    cb()
            return

        if s in ("idle", "walk", "sit", "sleep"):
            self.timer -= dt
            if self.timer <= 0:
                if s == "sleep":
                    self.wake()
                else:
                    self.choose_next()

    def nudge(self, m, step):
        for i, (hwnd, l, t, r, b, _st) in enumerate(self.windows):
            if not (self.y - self.BH < b and self.y > t):
                continue
            half = self.BW / 2
            if step > 0 and 0 <= l - (self.x + half) <= step + 1 and r + step <= m[2]:
                move_window(hwnd, l + step, t)
                return
            if step < 0 and 0 <= (self.x - half) - r <= -step + 1 and l + step >= m[0]:
                move_window(hwnd, l + step, t)
                return

    # ---------- trepar ----------
    def start_climb(self, hwnd, side):
        if not window_ok(hwnd):
            self.start_idle()
            return
        self.state = "climb"
        self.climb = (hwnd, side)
        self.vx = 0
        self.facing = -side                     # mira hacia la pared
        l, t, r, b = visible_rect(hwnd)
        self.timer = (self.y - t) / CLIMB_SPEED + random.uniform(1.5, 4)
        if random.random() < 0.2:                # a veces se cansa a medio camino
            self.timer *= random.uniform(0.4, 0.8)
        self.set_anim("trepa")

    def update_climb(self, dt):
        hwnd, side = self.climb
        if not window_ok(hwnd):
            self.to_air(0)
            return
        l, t, r, b = visible_rect(hwnd)
        self.x = (l - self.BW / 2) if side < 0 else (r + self.BW / 2)
        self.facing = -side
        self.y -= CLIMB_SPEED * dt
        self.walk_dist += CLIMB_SPEED * dt
        self.y = min(self.y, float(self.monitor_at(self.x)[3]))
        if self.y <= t:                                   # llegó arriba: se sube
            self.climb = None
            self.x = (l + self.BW * 0.7) if side < 0 else (r - self.BW * 0.7)
            self.facing = 1 if side < 0 else -1
            self.surface = hwnd
            self.surf_rect = (l, t, r, b)
            self.y = float(t)
            self.start_idle(random.uniform(0.8, 2.0))
            return
        self.timer -= dt
        if self.timer <= 0:                               # se cansa y se suelta
            self.climb = None
            self.ignore = hwnd
            self.to_air(-350, side * RUN_SPEED)

    # ---------- decidir qué hacer ----------
    def choose_next(self):
        if self.treat and self.treat.landed and self.go_eat():
            return
        if self.paused:
            self.start_idle(3.0)
            return
        if self.make_room():
            return
        if self.react_to_others():
            return
        acts = dict(ACTIONS)
        hostility = sum(max(0.0, -self.affinity(p)) for p in self.app.others(self))
        if "pelear_con" in acts:
            acts["pelear_con"] *= 1 + hostility * 0.6
        if len(self.app.pets) < 2 or self.app.game or self.app.fight:
            acts.pop("pelear_con", None)
            acts.pop("jugar_juntas", None)
            acts.pop("saludar", None)
            acts.pop("pelear_con", None)
        if not [h for h in self.abilities() if h in ABILITY_NAMES]:
            acts.pop("habilidad", None)
        if not MOUSE_PLAY:
            acts.pop("perseguir", None)
        if not MOUSE_PLAY or not self.fight_on:
            acts.pop("pelear", None)
        if not self.can_fly():
            acts.pop("volar", None)
        if len(self.monitors) < 2:
            acts.pop("cambiar_pantalla", None)
        if self.surface is None:
            acts.pop("bajarse", None)
        else:
            acts.pop("trepar", None)
            acts.pop("travesura", None)
        if not self.pranks:
            acts.pop("travesura", None)
        extras = [n for n in self.anims if n.startswith("extra_")]
        if not extras:
            acts.pop("extra", None)
        for _ in range(4):
            act = random.choices(list(acts), weights=list(acts.values()))[0]
            if self.do_action(act, extras):
                return
            acts.pop(act, None)
            if not acts:
                break
        self.start_idle()

    def do_action(self, act, extras):
        if act == "caminar":
            self.start_walk(WALK_SPEED, random.uniform(2, 7))
        elif act == "correr":
            self.start_walk(RUN_SPEED, random.uniform(1.2, 3.5))
        elif act == "quieta":
            self.start_idle(random.uniform(2, 5))
        elif act == "voltear":                               # mira hacia un lado un ratito
            self.facing = random.choice([-1, 1])
            if self.has_anim("mira"):
                self.play_once("mira", lambda: self.start_idle(random.uniform(1, 3)),
                               seconds=random.uniform(*LOOK_SECONDS), loop=True)
            else:
                self.start_idle(random.uniform(0.8, 2))
        elif act == "sentarse":
            self.start_sit()
        elif act == "dormir":
            self.start_sleep()
        elif act == "saltito":
            self.to_air(-650, random.choice([-1, 0, 1]) * 140, leave=False)
        elif act == "extra":
            name = random.choice(extras)
            self.play_once(name, seconds=random.uniform(*EXTRA_SECONDS),
                           loop=len(self.frames(name)) > 1)
        elif act == "bajarse":
            l, t, r, b = self.surf_rect
            side = -1 if self.x - l < r - self.x else 1
            self.facing = side
            self.to_air(-420, side * 220)
        elif act == "volar":
            self.start_fly(random.uniform(*FLY_SECONDS))
        elif act == "pelear":
            self.start_chase(random.uniform(5, 9))
            self.fight = True
        elif act == "cambiar_pantalla":
            return self.try_change_monitor()
        elif act == "jugar_juntas":
            free = [p for p in self.app.others(self)
                    if p.state in ("idle", "walk", "sit", "oneshot", "chase")]
            if not free:
                return False
            self.app.start_game(self, self.pick_partner(free, "amiga"))
        elif act == "saludar":
            return self.try_greet()
        elif act == "habilidad":
            return self.try_ability()
        elif act == "hablar":
            self.speak("aleatorio", ["..."], 3)
            self.start_idle(random.uniform(2, 4))
        elif act == "pelear_con":
            free = [p for p in self.app.others(self)
                    if p.state not in ("drag", "tp", "climb", "mgrab") and not p.hidden
                    and math.hypot(p.x - self.x, p.y - self.y) < 1400]
            if not free:
                return False
            return self.app.start_fight(self, self.pick_partner(free, "pelea"))
        elif act == "disparar":
            return self.try_shoot()
        elif act == "perseguir":
            self.start_chase(random.uniform(*CHASE_SECONDS))
        elif act == "saltar_ventana":
            return self.try_window_jump()
        elif act == "trepar":
            return self.try_climb()
        elif act == "travesura":
            return self.try_prank()
        return True

    def try_change_monitor(self):
        """Se va a otra pantalla: volando, caminando si está pegada, o de un saltote."""
        m = self.monitor_at(self.x)
        others = [n for n in self.monitors if n != m]
        if not others:
            return False
        if self.can_fly():
            self.start_fly(random.uniform(*FLY_SECONDS), target=self.pick_fly_target(True))
            return True
        if self.surface is not None:                      # primero se baja de la ventana
            return False
        for side in (-1, 1):
            n = self.neighbor(m, side)
            if n and random.random() < 0.8:
                tx = (n[2] - random.uniform(self.BW, min(400, (n[2] - n[0]) / 2)) if side < 0
                      else n[0] + random.uniform(self.BW, min(400, (n[2] - n[0]) / 2)))
                self.go_to(tx, None)
                return True
        n = random.choice(others)
        self.jump_to(random.uniform(n[0] + self.BW, n[2] - self.BW), n[3])
        return True

    def try_window_jump(self):
        m = self.monitor_at(self.x)
        options = []
        for i, (hwnd, l, t, r, b, standable) in enumerate(self.windows):
            if not standable or hwnd == self.surface or r - l < self.BW * 3:
                continue
            wm = self.monitor_at((l + r) / 2, t + 5)       # también ventanas de otra pantalla
            if t - self.BH < wm[1]:
                continue
            dy = t - self.y
            if dy < -JUMP_REACH_UP or dy > 500:
                continue
            for _ in range(3):
                tx = random.uniform(l + self.BW, r - self.BW)
                if abs(tx - self.x) <= JUMP_REACH_X and self.point_visible(tx, t + 3, i):
                    options.append((tx, t))
                    break
        if not options:
            return False
        self.jump_to(*random.choice(options))
        return True

    def try_climb(self):
        m = self.monitor_at(self.x)
        fl = m[3]
        options = []
        for i, (hwnd, l, t, r, b, standable) in enumerate(self.windows):
            # la ventana debe ser más alta que ella y su parte de abajo quedarle a
            # una altura que alcance de un brinco
            if not standable or t > fl - self.BH * 1.5 or b < fl - JUMP_REACH_UP * 0.8:
                continue
            if t - self.BH < m[1]:
                continue
            for side, edge in ((-1, l), (1, r)):
                gx = edge - self.BW / 2 if side < 0 else edge + self.BW / 2
                if not (m[0] + self.BW / 2 <= gx <= m[2] - self.BW / 2):
                    continue
                if abs(gx - self.x) > JUMP_REACH_X * 1.5:
                    continue
                if self.point_visible(edge + side * 2, (t + min(b, fl)) / 2, i):
                    options.append((hwnd, side, gx))
        if not options:
            return False
        hwnd, side, gx = random.choice(options)
        self.go_to(gx, lambda: self.reach_climb(hwnd, side))
        return True

    def reach_climb(self, hwnd, side):
        """Llega al costado: si la ventana toca el piso empieza a trepar; si no,
        brinca para agarrarse de su orilla."""
        if not window_ok(hwnd):
            self.start_idle()
            return
        l, t, r, b = visible_rect(hwnd)
        if b >= self.y - self.BH * 0.5:
            self.start_climb(hwnd, side)
            return
        h = self.y - (b + self.BH * 0.4)           # que los pies queden un poco abajo del borde
        self.facing = -side
        self.to_air(-(2 * GRAVITY * max(h, 10)) ** 0.5, 0, leave=False)
        self.grab = (hwnd, side)

    def go_to(self, x, cb):
        self.state = "goto"
        self.goto_x = x
        self.goto_cb = cb
        self.vx = (RUN_SPEED if x > self.x else -RUN_SPEED) * self.spd()
        self.facing = 1 if self.vx > 0 else -1
        self.set_anim("corre")

    # ---------- mouse ----------
    def on_press(self, e):
        self.press = (e.x_root, e.y_root, time.perf_counter(), self.x - e.x_root,
                      self.y - e.y_root)
        self.drag_samples = []

    def on_drag(self, e):
        if not self.press:
            return
        px, py, _t, ox, oy = self.press
        if self.state != "drag":
            if abs(e.x_root - px) + abs(e.y_root - py) < 5:
                return
            self.state = "drag"
            self.y_off = 0.0
            self.mgrab = None
            self.surface = None
            self.surf_rect = None
            self.climb = None
            self.vx = self.vy = 0
            self.set_anim("arrastrada")
        self.x = e.x_root + ox
        self.y = e.y_root + oy
        now = time.perf_counter()
        self.drag_samples.append((now, self.x, self.y))
        self.drag_samples = [s for s in self.drag_samples if now - s[0] < 0.1]

    def on_release(self, e):
        if self.state == "drag":
            vx = vy = 0.0
            if len(self.drag_samples) >= 2:
                t0, x0, y0 = self.drag_samples[0]
                t1, x1, y1 = self.drag_samples[-1]
                if t1 - t0 > 0.005:
                    vx = max(-2200, min(2200, (x1 - x0) / (t1 - t0)))
                    vy = max(-2200, min(2200, (y1 - y0) / (t1 - t0)))
            self.ignore = None
            self.to_air(vy, vx)
            self.fly_catch = self.can_fly() and random.random() < 0.7
        elif self.press:
            self.on_click()
        self.press = None

    def on_click(self):
        if self.bubble.visible:
            self.bubble.hide()
        if self.state == "fly":
            self.particles.emit(25, self.x, self.y + self.y_off - self.BH * 0.5,
                                self.BW * 0.6, self.BH * 0.5, up=80)
            return
        if self.state in ("air", "climb"):
            return
        if self.state == "sleep":
            self.wake()
        elif self.has_anim("feliz"):
            self.play_once("feliz", lambda: self.start_idle(random.uniform(1, 2.5)), seconds=1.5)
        else:
            self.to_air(-600, 0, leave=False)

    # ---------- travesura: empujar una ventana ----------
    def try_prank(self):
        m = self.monitor_at(self.x)
        fg = user32.GetForegroundWindow()
        options = []
        for i, (hwnd, l, t, r, b, standable) in enumerate(self.windows):
            if not standable or (hwnd == fg and not PRANK_ACTIVE_WINDOW):
                continue
            body_top, body_mid = self.y - self.BH, self.y - self.BH / 2
            if not (t < body_mid and b > self.y - self.BH * 0.25):  # su costado no le queda a la altura
                continue
            for side, edge in ((-1, l), (1, r)):
                gx = edge - self.BW / 2 if side < 0 else edge + self.BW / 2
                if not (m[0] + self.BW / 2 <= gx <= m[2] - self.BW / 2):
                    continue
                if abs(gx - self.x) > JUMP_REACH_X:
                    continue
                if not self.point_visible(edge + side * 2, body_mid, i):
                    continue
                dist = random.uniform(*PRANK_DISTANCE)
                room = (m[2] - r) if side < 0 else (l - m[0])     # espacio hacia donde la empuja
                dist = min(dist, room - 10)
                if dist >= 30:
                    options.append((hwnd, side, gx, dist))
        if not options:
            return False
        hwnd, side, gx, dist = random.choice(options)
        self.go_to(gx, lambda: self.start_push(hwnd, side, dist))
        return True

    def start_push(self, hwnd, side, dist):
        if not window_ok(hwnd):
            self.start_idle()
            return
        self.state = "push"
        self.push = {"hwnd": hwnd, "side": side, "left": dist, "acc": 0.0,
                     "rect": visible_rect(hwnd), "stuck": 0.0}
        self.vx = 0
        self.facing = -side
        self.set_anim("empuja")

    def end_push(self, ok):
        self.push = None
        if ok:
            self.say(self.phrase("travesura", ["Jiji", "¡Ups!", "Así queda mejor", "Yo no fui...", "¡Listo!"]), 2.5)
            for name in ("feliz", "extra_saluda"):
                if self.has_anim(name):
                    self.play_once(name, lambda: self.start_idle(random.uniform(1.5, 3)),
                                   seconds=1.8, loop=name.startswith("extra_"))
                    return
        self.start_idle(random.uniform(1, 2))

    def update_push(self, dt, m):
        p = self.push
        hwnd, side = p["hwnd"], p["side"]
        if not window_ok(hwnd) or user32.GetAsyncKeyState(0x01) & 0x8000:
            self.end_push(False)                          # la cerraste o estás usando el mouse
            return
        rect = visible_rect(hwnd)
        if abs(rect[0] - p["rect"][0]) > 2 or abs(rect[1] - p["rect"][1]) > 2:
            self.end_push(False)                          # alguien más la movió
            return
        p["acc"] += PUSH_SPEED * dt
        step = int(p["acc"])
        if step:
            p["acc"] -= step
            delta = -side * step                          # lado izquierdo -> empuja a la derecha
            move_window_by(hwnd, delta)
            new = visible_rect(hwnd)
            if new[0] == rect[0]:                         # Windows no la dejó mover
                p["stuck"] += dt
                if p["stuck"] > 0.4:
                    self.end_push(False)
                    return
            else:
                p["left"] -= step
                self.walk_dist += step
            rect = new
            p["rect"] = rect
        l, t, r, b = rect
        self.x = (l - self.BW / 2) if side < 0 else (r + self.BW / 2)
        if p["left"] <= 0 or (side < 0 and r >= m[2] - 4) or (side > 0 and l <= m[0] + 4):
            self.end_push(True)

    # ---------- volar ----------
    def start_fly(self, seconds, mode="wander", target=None):
        """mode: 'wander' (pasea), 'follow' (persigue el mouse), 'carry' (se lleva el mouse)."""
        now = time.perf_counter()
        if self.state not in ("air", "fly"):
            self.particles.emit(18, self.x, self.y - 4, self.BW * 0.5, 6, up=60)
        self.state = "fly"
        self.surface = None
        self.surf_rect = None
        self.climb = None
        self.grab = None
        self.ignore = None
        self.fly_mode = mode
        self.fly_until = now + seconds
        self.fly_land = None
        self.fly_target = target or self.pick_fly_target()
        self.set_anim("vuela")

    def virtual_screen(self):
        return (min(m[0] for m in self.monitors), min(m[1] for m in self.monitors),
                max(m[2] for m in self.monitors), max(m[3] for m in self.monitors))

    def pick_fly_target(self, other_monitor=False):
        here = self.monitor_at(self.x)
        others = [m for m in self.monitors if m != here]
        if others and (other_monitor or random.random() < 0.35):
            m = random.choice(others)                     # a veces se va a otra pantalla
        else:
            m = here
        return (random.uniform(m[0] + self.BW, m[2] - self.BW),
                random.uniform(m[1] + self.BH + 30, max(m[1] + self.BH + 31, m[3] - 60)))

    def pick_landing(self, m):
        options = []
        for i, (hwnd, l, t, r, b, standable) in enumerate(self.windows):
            if not standable or r - l < self.BW * 3 or t - self.BH < m[1]:
                continue
            if not (m[0] <= (l + r) / 2 < m[2]):
                continue
            tx = random.uniform(l + self.BW, r - self.BW)
            if self.point_visible(tx, t + 3, i):
                options.append((hwnd, tx))
        if options and random.random() < 0.6:
            return random.choice(options)
        tx = min(max(self.x + random.uniform(-300, 300), m[0] + self.BW), m[2] - self.BW)
        return (None, tx)

    def end_follow(self, now):
        self.fly_mode = "wander"
        self.fight = False
        self.chase_until = 0.0
        self.fly_until = now + random.uniform(1.0, 3.0)
        self.fly_target = self.pick_fly_target()

    def update_fly(self, dt, now):
        m = self.monitor_at(self.x)
        mode = self.fly_mode
        landing = False
        cx = cy = None
        top = FLY_SPEED

        if mode == "follow":                                  # persigue el mouse volando
            cx, cy = cursor_pos()
            if now >= self.chase_until:
                self.end_follow(now)
                return
            side = 1 if self.x >= cx else -1
            tx, ty = cx + side * self.BW * 0.55, cy + self.BH * 0.5
            top = FLY_SPEED * 1.5
        elif mode == "carry":                                 # se lleva el mouse volando
            g = self.mgrab
            if not g or mouse_down():
                self.mgrab = None
                self.end_follow(now)
                return
            cx, cy = cursor_pos()
            ux, uy = cx - g["last"][0], cy - g["last"][1]
            g["resist"] = g["resist"] * 0.97 + (ux * ux + uy * uy) ** 0.5
            if g["resist"] > FIGHT_RESIST:                    # la jalaste: lo suelta y se cae
                self.mgrab = None
                self.fight = False
                self.say(self.phrase("mouse_pierde", ["¡Hmph!", "¡Oye!", "¡No es justo!"]), 2.2)
                self.to_air(-200, (1 if ux > 0 else -1) * 220, leave=False)
                self.fly_catch = self.can_fly()
                return
            self.x += ux * 0.3
            self.y += uy * 0.3
            if now >= g["until"]:
                self.mgrab = None
                self.say(self.phrase("mouse_gana", ["¡Toma, ahí está!", "Jiji", "¡Gané!"]), 2.2)
                self.end_follow(now)
                return
            tx, ty = g["target"]
            top = FLY_SPEED * 0.9
        elif mode in ("tagc", "tagr"):                        # atrapadas volando
            game = self.app.game
            r = self.role()
            if not game or r is None:
                self.end_follow(now)
                return
            if (r == "chaser") != (mode == "tagc"):           # se cambiaron los papeles
                self.fly_mode = mode = "tagc" if r == "chaser" else "tagr"
                self.fly_until = now + (TAG_SECONDS if mode == "tagc" else random.uniform(2.5, 4.5))
            other = game["runner"] if r == "chaser" else game["chaser"]
            if mode == "tagc":
                if now < game["pause_until"]:
                    tx, ty = self.x, self.y
                else:
                    tx, ty = other.x, other.y + other.y_off
                    if self.touching(other):
                        self.app.caught()
                        return
                top = FLY_SPEED * 1.35
            else:
                if now >= self.fly_until:                     # ya voló un rato: baja
                    self.fly_mode = "wander"
                    self.fly_until = now
                    return
                ddx, ddy = self.x - other.x, self.y - other.y
                d0 = (ddx * ddx + ddy * ddy) ** 0.5 or 1.0
                vs = self.virtual_screen()
                tx = min(max(self.x + ddx / d0 * 350, vs[0] + self.BW), vs[2] - self.BW)
                ty = min(max(self.y + ddy / d0 * 250 - 60, vs[1] + self.BH + 20), vs[3] - 20)
                top = FLY_SPEED * 1.15
        else:
            if now >= self.fly_until and self.fly_land is None:
                self.fly_land = self.pick_landing(m)
            landing = self.fly_land is not None
            if landing:
                hwnd, tx = self.fly_land
                lm = self.monitor_at(tx, m[3] - 5)
                if hwnd is not None:
                    if not window_ok(hwnd):
                        self.fly_land = self.pick_landing(m)
                        return
                    l, t, r, b = visible_rect(hwnd)
                    idx = self.index_of(hwnd)
                    if not (l <= tx <= r) or (idx is not None and
                                              not self.point_visible(tx, t + 3, idx)):
                        self.fly_land = self.pick_landing(m)
                        return
                    ty = float(t)
                else:
                    ty = float(lm[3])
                top = FLY_SPEED * 0.55
            else:
                tx, ty = self.fly_target

        dx, dy = tx - self.x, ty - self.y
        dist = (dx * dx + dy * dy) ** 0.5
        if mode == "wander" and not landing and dist < 30:
            self.fly_target = self.pick_fly_target()
        if mode == "carry" and dist < 30:
            self.mgrab["target"] = self.pick_fly_target()
        speed = top * min(1.0, dist / 150.0)
        dvx, dvy = (dx / dist * speed, dy / dist * speed) if dist > 0.01 else (0.0, 0.0)
        k = min(1.0, (4.0 if mode == "follow" else 2.5) * dt)
        self.vx += (dvx - self.vx) * k
        self.vy += (dvy - self.vy) * k
        self.x += self.vx * dt
        self.y += self.vy * dt
        vs = self.virtual_screen()                        # puede cruzar de una pantalla a otra
        self.x = min(max(self.x, vs[0] + self.BW / 2), vs[2] - self.BW / 2)
        self.y = min(max(self.y, vs[1] + self.BH), float(vs[3]))
        if mode == "follow":
            self.facing = 1 if cx > self.x else -1
        elif mode == "carry":
            self.facing = 1 if self.vx >= 0 else -1
        elif abs(self.vx) > 25:
            self.facing = 1 if self.vx > 0 else -1
        self.fly_phase += dt
        bob = 5.0 if not landing else 5.0 * min(1.0, dist / 60.0)
        if mode != "wander":
            bob = 2.5
        self.y_off = math.sin(self.fly_phase * 2.4) * bob
        self.set_anim("vuela")
        self.p_acc += PARTICLE_RATE * dt * (1.4 if mode != "wander" else 1.0)
        n = int(self.p_acc)
        if n:
            self.p_acc -= n
            self.particles.emit(n, self.x, self.y + self.y_off - self.BH * 0.45,
                                self.BW * 0.55, self.BH * 0.45)

        if mode == "follow" and self.fight and not mouse_down() and not self.mouse_taken():
            hx, hy = self.hand_point()
            if abs(hx - cx) < self.BW * 0.45 and abs(hy - cy) < self.BH * 0.3:
                self.mgrab = {"until": now + random.uniform(*FIGHT_SECONDS), "resist": 0.0,
                              "last": None, "target": self.pick_fly_target()}
                self.fly_mode = "carry"
                self.say(self.phrase("mouse_agarra", ["¡Es mío!", "¡Atrapado!", "¡Mi mouse!", "Jeje"]), 1.6)
        if self.fly_mode == "carry" and self.mgrab:
            hx, hy = self.hand_point()
            user32.SetCursorPos(hx, hy)
            self.mgrab["last"] = (hx, hy)

        if landing and dist < 6:
            self.x, self.y = tx, ty
            self.vx = self.vy = 0.0
            self.particles.emit(14, self.x, self.y - 4, self.BW * 0.5, 4, up=50)
            hwnd = self.fly_land[0]
            self.fly_land = None
            self.land(hwnd, ty, visible_rect(hwnd) if hwnd else None)

    # ---------- personaje: nombre, frases y habilidades ----------
    def name(self):
        return self.skin_cfg.get("personaje") or (self.skin or "Mascota").capitalize()

    def power(self):
        try:
            return float(self.skin_cfg.get("poder", DEFAULT_POWER))
        except (TypeError, ValueError):
            return float(DEFAULT_POWER)

    def relation(self, other):
        rels = self.skin_cfg.get("relaciones") or {}
        name = other.name() if hasattr(other, "name") else str(other)
        for k, v in rels.items():
            if k.lower() == name.lower():
                return v or {}
        return {}

    def affinity(self, other):
        try:
            return float(self.relation(other).get("afinidad", 0))
        except (TypeError, ValueError):
            return 0.0

    def pick_partner(self, candidates, mode):
        """Elige con quién: 'pelea' prefiere enemigas, 'amiga' prefiere amigas."""
        if not candidates:
            return None
        weights = []
        for p in candidates:
            a = self.affinity(p)
            if mode == "pelea":
                w = 1 + max(0.0, -a) * 2.5
                if p.power() - self.power() >= 4 and a > -2:
                    w *= 0.3                          # no se mete con alguien tan fuerte
            else:
                w = max(0.15, 1 + a * 0.8)
            weights.append(w)
        return random.choices(candidates, weights=weights)[0]

    def phrase(self, cat, default=None, **kw):
        lst = None
        otra = kw.get("otra")
        if otra:                                      # frases especiales para esa persona
            for nm in str(otra).split(" y "):
                rel = (self.skin_cfg.get("relaciones") or {})
                for k, v in rel.items():
                    if k.lower() == nm.strip().lower():
                        lst = ((v or {}).get("frases") or {}).get(cat) or lst
        lst = lst or (self.skin_cfg.get("frases") or {}).get(cat) or default or ["..."]
        txt = random.choice(lst)
        try:
            return txt.format(**kw)
        except Exception:
            return txt

    def speak(self, cat, default=None, seconds=2.2, **kw):
        self.say(self.phrase(cat, default, **kw), seconds)

    def abilities(self):
        return list(self.skin_cfg.get("habilidades") or [])

    def acolors(self, name, default=None):
        return (self.skin_cfg.get("colores") or {}).get(name) or default or self.particles.colors

    def buffed(self):
        return time.perf_counter() < self.buff_until

    def spd(self):
        """Multiplicador de velocidad del personaje (y del modo 'aura')."""
        return float(self.skin_cfg.get("velocidad", 1.0)) * (1.7 if self.buffed() else 1.0)

    def add_fx(self, kind, seconds, colors, rate=None):
        self.fx.append({"kind": kind, "until": time.perf_counter() + seconds, "colors": colors,
                        "rate": rate or FX_RATES.get(kind, 25), "acc": 0.0})

    def update_fx(self, dt, now):
        """Emisores de partículas que duran un rato (aura, burbujas, nieve, estela...)."""
        if not self.fx:
            return
        keep = []
        for f in self.fx:
            if now >= f["until"]:
                continue
            keep.append(f)
            f["acc"] += f["rate"] * dt
            n = int(f["acc"])
            if not n:
                continue
            f["acc"] -= n
            k, c = f["kind"], f["colors"]
            x, y, bw, bh = self.x, self.y + self.y_off, self.BW, self.BH
            if k == "aura":
                self.particles.emit(n, x, y - bh * 0.5, bw * 0.55, bh * 0.45, up=70, colors=c,
                                    speed=(5, 25), life=(0.4, 0.8), size=(1.5, 3.5), star=0.25,
                                    g=-30)
            elif k == "burbujas":
                self.particles.emit(n, x, y - 8, bw * 0.7, 5, up=30, colors=c, speed=(5, 20),
                                    life=(0.8, 1.5), size=(2.5, 5.5), star=0.0, g=-12)
            elif k == "nieve":
                half = self.particles.size * 0.42
                self.particles.emit(n, x, y - bh * 1.15, half, 8, up=-35, colors=c,
                                    speed=(0, 12), life=(1.4, 2.2), size=(1.5, 3.5), star=0.55,
                                    g=10, drag=0.99)
            elif k == "estela":
                self.particles.emit(n, x, y - bh * 0.4, bw * 0.35, bh * 0.35, up=0, colors=c,
                                    speed=(0, 15), life=(0.3, 0.6), size=(2, 4), star=0.5, g=0)
            elif k == "sombra":
                self.particles.emit(n, x, y - bh * 0.5, bw * 0.7, bh * 0.55, up=45, colors=c,
                                    speed=(10, 45), life=(0.5, 1.1), size=(2, 4.5), star=0.45,
                                    g=-15)
            elif k == "vapor":
                hx, hy = self.hand_front()
                self.particles.emit(n, hx, hy - 6, 4, 2, up=28, colors=c, speed=(0, 6),
                                    life=(0.9, 1.5), size=(2, 3.5), star=0.0, g=-6, drag=0.99)
            elif k == "paginas":
                self.particles.emit(n, x, y - bh * 0.35, bw * 0.9, bh * 0.3, up=22, colors=c,
                                    speed=(5, 20), life=(1.2, 2.0), size=(2.5, 4), star=0.0,
                                    g=-4, drag=0.99)
            elif k == "hielo_cursor" and self.mgrab and self.mgrab.get("freeze"):
                fx_, fy_ = self.mgrab["freeze"]
                self.particles.emit(n, fx_, fy_, 10, 10, up=0, colors=c, speed=(20, 70),
                                    life=(0.3, 0.6), size=(1.5, 3.5), star=0.7, g=0)
        self.fx = keep

    def try_ability(self):
        habs = [h for h in self.abilities() if h in ABILITY_NAMES]
        if not self.app.flag("poderes_pesados"):
            habs = [h for h in habs if h not in HEAVY_ABILITIES]
        if not habs:
            return False
        if not self.pranks and "rayo" in habs and len(habs) > 1 and random.random() < 0.5:
            habs.remove("rayo")
        random.shuffle(habs)
        for h in habs:
            if self.do_ability(h):
                return True
        return False

    def do_ability(self, h):
        now = time.perf_counter()
        if h == "limpiar":
            self.add_fx("burbujas", 7, self.acolors("limpiar", ["#ffffff", "#d6f1ff", "#a9dcff",
                                                                "#7fb8e0"]))
            self.speak("limpiar", ["Hora de limpiar."])
            self.start_walk(WALK_SPEED * 0.7, 7)
        elif h == "aura":
            self.buff_until = now + 6
            self.add_fx("aura", 6, self.acolors("aura", ["#ffffff", "#dff3ff", "#b9e0ff",
                                                          "#8fb7d9"]))
            self.speak("aura", ["¡Con todo!"])
            self.start_walk(RUN_SPEED, 6)
        elif h == "nieve":
            self.add_fx("nieve", 8, self.acolors("nieve", ["#ffffff", "#eef8ff", "#cfeaff",
                                                            "#a7cde8"]))
            self.speak("nieve", ["¡Mira, nieve!"])
            self.start_sit(8)
        elif h == "cristales":
            others = [p for p in self.app.others(self) if abs(p.y - self.y) < 60
                      and abs(p.x - self.x) < 400]
            if others:
                self.facing = 1 if others[0].x > self.x else -1
            self.cast_shards(self.acolors("cristales"))
            self.speak("cristales", ["¡Toma!"], 1.6)
            self.play_once("mira" if self.has_anim("mira") else "quieta",
                           lambda: self.start_idle(random.uniform(1, 2)), seconds=1.2)
        elif h == "teletransporte":
            return self.start_teleport()
        elif h == "rayo":
            return self.start_beam()
        elif h == "super_salto":
            return self.super_jump()
        elif h == "lucero":
            return self.spin_attack()
        elif h == "te":
            return self.tea_party()
        elif h == "lectura":
            self.add_fx("paginas", 9, self.acolors("lectura", ["#ffffff", "#fff8e6", "#f0e2c0",
                                                                "#c9b48a"]))
            self.speak("lectura", ["Qué libro tan interesante..."], 2.5)
            self.start_sit(9)
        elif h == "curiosear":
            return self.curious()
        elif h == "sombra":
            self.add_fx("sombra", 4.5, self.acolors("sombra", ["#c9a8ff", "#7b4bd6", "#3d1f6e",
                                                               "#140a24"]))
            self.speak("sombra", ["..."], 2.2)
            name = "sombra" if self.has_anim("sombra") else ("feliz" if self.has_anim("feliz")
                                                             else "quieta")
            self.play_once(name, lambda: self.start_idle(random.uniform(1, 2)), seconds=4.5,
                           loop=True)
        elif h == "manos":
            return self.shadow_hands()
        elif h == "bendicion":
            self.buff_until = now + 7
            self.add_fx("aura", 7, self.acolors("bendicion", ["#fffbe6", "#ffe58a", "#ffc93c",
                                                               "#c98a00"]), rate=40)
            self.speak("bendicion", ["Que la bendición me acompañe."], 2.2)
            self.start_walk(RUN_SPEED, 6)
        elif h == "minimizar":
            return self.slash_window()
        elif h == "golpe_mouse":
            return self.smash_mouse()
        else:
            return False
        return True

    def hand_front(self):
        return (self.x + self.facing * self.BW * 0.42, self.y + self.y_off - self.BH * 0.58)

    def cast_shards(self, colors, n=24, toward=None):
        hx, hy = self.hand_front()
        if toward is not None:
            ang = math.atan2(toward[1] - hy, toward[0] - hx)
        else:
            ang = 0.0 if self.facing > 0 else math.pi
        self.particles.emit(n, hx, hy, 4, 6, up=0, colors=colors, speed=(200, 360),
                            life=(0.3, 0.55), size=(2, 4.5), star=0.85, g=0, drag=0.985,
                            angle=ang, cone=0.3)

    # --- teletransporte (Beatrice: "paso de puerta") ---
    def pick_tp_dest(self):
        options = []
        for i, (hwnd, l, t, r, b, standable) in enumerate(self.windows):
            if not standable or hwnd == self.surface or r - l < self.BW * 3:
                continue
            wm = self.monitor_at((l + r) / 2, t + 5)
            if t - self.BH < wm[1]:
                continue
            tx = random.uniform(l + self.BW, r - self.BW)
            if self.point_visible(tx, t + 3, i):
                options.append((hwnd, tx, float(t)))
        for m in self.monitors:
            options.append((None, random.uniform(m[0] + self.BW, m[2] - self.BW), float(m[3])))
        return random.choice(options)

    def start_teleport(self, dest=None):
        if self.state not in ("idle", "walk", "sit", "oneshot", "chase", "tag", "fight"):
            return False
        cols = self.acolors("teletransporte")
        self.particles.emit(32, self.x, self.y - self.BH / 2, self.BW * 0.5, self.BH * 0.5,
                            up=20, colors=cols, speed=(40, 150), life=(0.4, 0.9), star=0.6)
        self.speak("teletransporte", ["¡Puerta!"], 1.5)
        self.state = "tp"
        self.vx = 0
        self.tp_until = time.perf_counter() + 0.6
        self.tp_dest = dest or self.pick_tp_dest()
        self.win.withdraw()
        self.hidden = True
        return True

    def update_tp(self, now):
        if now < self.tp_until:
            return
        hwnd, tx, ty = self.tp_dest
        if hwnd is not None and not window_ok(hwnd):
            hwnd, m = None, self.monitor_at(tx, ty - 5)
            ty = float(m[3])
        self.x, self.y = tx, ty
        self.hidden = False
        self.win_pos = None
        self.win.deiconify()
        cols = self.acolors("teletransporte")
        self.particles.clear()
        self.particles.emit(32, self.x, self.y - self.BH / 2, self.BW * 0.5, self.BH * 0.5,
                            up=20, colors=cols, speed=(40, 150), life=(0.4, 0.9), star=0.6)
        self.vy = 0
        self.land(hwnd, ty, visible_rect(hwnd) if hwnd else None)

    # --- rayo (Shaula) ---
    def start_beam(self, target=None, then=None, width=12):
        if self.state not in ("idle", "walk", "sit", "oneshot", "fight", "chase"):
            return False
        hwnd = None
        if target is None:
            opts = []
            for i, (h, l, t, r, b, standable) in enumerate(self.windows):
                if not standable:
                    continue
                px, py = random.uniform(l + 40, r - 40), random.uniform(t + 30, min(b, t + 300))
                if self.point_visible(px, py, i) and abs(px - self.x) < 1400:
                    opts.append((px, py, h))
            if opts and random.random() < 0.75:
                tx, ty, hwnd = random.choice(opts)
            else:                                         # al cielo
                m = self.monitor_at(self.x)
                tx = self.x + random.choice([-1, 1]) * random.uniform(200, 500)
                ty = float(m[1] + 5)
        else:
            tx, ty = target
        self.facing = 1 if tx > self.x else -1
        self.beam = {"target": (tx, ty), "hwnd": hwnd, "phase": "charge",
                     "t": time.perf_counter() + (0.5 if target is None else 0.25),
                     "then": then, "width": width, "acc": 0.0}
        if target is None:
            self.speak("rayo", ["¡Allá va!"], 1.6)
        self.state = "beam"
        self.vx = 0
        self.set_anim("mira" if self.has_anim("mira") else "quieta")
        return True

    def update_beam(self, dt, now):
        b = self.beam
        if not b:
            self.start_idle(random.uniform(0.5, 1.5))
            return
        cols = self.acolors("rayo", ["#ffffff", "#ffe9a8", "#ffb347", "#ff7a1a"])
        hx, hy = self.hand_front()
        if b["phase"] == "charge":
            b["acc"] += 40 * dt
            n = int(b["acc"])
            if n:
                b["acc"] -= n
                self.particles.emit(n, hx, hy, 14, 14, up=0, colors=cols, speed=(5, 30),
                                    life=(0.2, 0.4), size=(1.5, 3), star=0.6, g=0)
            if now >= b["t"]:
                tx, ty = b["target"]
                self.app.beams.append(Beam(self.root, hx, hy, tx, ty, cols, width=b["width"]))
                if b["hwnd"] is not None and self.pranks:
                    self.app.shake(b["hwnd"])
                b["phase"] = "fire"
                b["t"] = now + 0.5
        elif now >= b["t"]:
            then = b["then"]
            self.beam = None
            if then:
                then()
            else:
                self.start_idle(random.uniform(1, 2.5))

    # --- súper salto (Shaula) ---
    def super_jump(self):
        if self.state not in ("idle", "walk", "sit", "oneshot"):
            return False
        m = self.monitor_at(self.x)
        best = None
        for i, (hwnd, l, t, r, b, standable) in enumerate(self.windows):
            if not standable or hwnd == self.surface or t - self.BH < m[1]:
                continue
            tx = min(max(self.x, l + self.BW), r - self.BW)
            if abs(tx - self.x) > 900 or not self.point_visible(tx, t + 3, i):
                continue
            if best is None or t < best[1]:
                best = (tx, t)
        self.add_fx("estela", 1.4, self.acolors("super_salto", ["#ffffff", "#ffe9a8", "#ffb347",
                                                                 "#ff7a1a"]), rate=45)
        self.speak("super_salto", ["¡Hiyaaa!"], 1.6)
        if best and best[1] < self.y - 120:
            self.jump_to(*best)
        else:
            self.to_air(-1400, self.facing * 150, leave=False)
        return True

    # ---------- poderes pesados (Reinhard) ----------
    def slash_window(self):
        """Lanza un corte a una ventana y la minimiza."""
        if not self.app.flag("poderes_pesados"):
            return False
        if self.state not in ("idle", "walk", "sit", "oneshot", "chase"):
            return False
        fg = user32.GetForegroundWindow()
        opts = []
        for i, (h, l, t, r, b, standable) in enumerate(self.windows):
            if h == self.surface:
                continue
            px, py = (l + r) / 2, t + min(120, (b - t) / 2)
            if self.point_visible(px, py, i):
                opts.append((h, px, py, h == fg))
        if not opts:
            return False
        calm = [o for o in opts if not o[3]]          # mejor una en la que no estés trabajando
        h, px, py, _fg = random.choice(calm if calm and random.random() < 0.75 else opts)
        self.speak("minimizar", ["¡Corte!"], 1.8)

        def cut(_proj, hwnd=h):
            if user32.IsWindow(hwnd) and self.app.flag("poderes_pesados"):
                user32.ShowWindow(hwnd, 6)            # SW_MINIMIZE
        self.shoot(px, py, None, kind="corte", on_reach=cut, big=True)
        self.state = "beam"
        self.vx = 0
        self.beam = {"phase": "fire", "t": time.perf_counter() + 1.2, "then": None,
                     "target": (px, py), "hwnd": None, "width": 7, "acc": 0.0}
        return True

    def smash_mouse(self):
        """Le pega al cursor y lo manda volando."""
        if not self.app.flag("poderes_pesados") or not MOUSE_PLAY or mouse_down():
            return False
        if self.state not in ("idle", "walk", "sit", "oneshot", "chase"):
            return False
        cx, cy = cursor_pos()
        if math.hypot(cx - self.x, cy - self.y) > SHOT_RANGE * 1.3:
            return False
        self.speak("golpe_mouse", ["¡Fuera!"], 1.6)
        direction = 1 if cx >= self.x else -1

        def launch(_proj):
            if not mouse_down():
                self.app.fling_cursor(direction * random.uniform(1400, 2200),
                                      -random.uniform(900, 1500))
        self.shoot(cx, cy, None, kind="corte", on_reach=launch)
        self.state = "beam"
        self.vx = 0
        self.beam = {"phase": "fire", "t": time.perf_counter() + 1.0, "then": None,
                     "target": (cx, cy), "hwnd": None, "width": 7, "acc": 0.0}
        return True

    def react_to_others(self):
        """Si una enemiga anda cerca, la molesta (y a veces se pelean)."""
        if self.app.fight or self.app.game:
            return False
        near = [p for p in self.app.others(self) if p.state in ("idle", "walk", "sit")
                and abs(p.y - self.y) < 10 and abs(p.x - self.x) < ENEMY_NEAR]
        for p in near:
            a = self.affinity(p)
            if a <= -2 and random.random() < 0.5:
                self.facing = 1 if p.x > self.x else -1
                self.speak("molesta", ["¿Qué haces aquí?"], 2.4, otra=p.name())
                if random.random() < 0.5:
                    self.root.after(1500, lambda q=p: self.app.start_fight(self, q))
                self.start_idle(random.uniform(1.5, 3))
                return True
            if a >= 2 and random.random() < 0.25:
                self.facing = 1 if p.x > self.x else -1
                self.speak("cariño", ["¡Me da gusto verte!"], 2.4, otra=p.name())
                self.start_idle(random.uniform(1.5, 3))
                return True
        return False

    def intervene(self, a, b):
        """Se mete a separar una pelea."""
        burst = self.acolors("bendicion", ["#fffbe6", "#ffe58a", "#ffc93c", "#c98a00"])
        self.particles.emit(24, self.x, self.y - self.BH / 2, self.BW * 0.5, self.BH * 0.5,
                            up=30, colors=burst, speed=(40, 160), star=0.7)
        self.x = (a.x + b.x) / 2
        self.y = a.y
        self.surface, self.surf_rect = a.surface, a.surf_rect
        self.vx = self.vy = 0
        self.win_pos = None
        self.particles.clear()
        self.particles.emit(30, self.x, self.y - self.BH / 2, self.BW * 0.6, self.BH * 0.5,
                            up=40, colors=burst, speed=(60, 220), star=0.7)
        self.speak("interviene", ["¡Basta las dos!"], 2.6, otra="%s y %s" % (a.name(), b.name()))
        self.app.end_fight(None)
        for p in (a, b):
            p.speak("regañada", ["Perdón...", "Está bien..."], 2.2, otra=self.name())
            p.facing = 1 if self.x > p.x else -1
        self.start_idle(random.uniform(2, 3))

    # ---------- habilidades de Echidna y Satella ----------
    def tea_party(self):
        if self.state not in ("idle", "walk", "sit", "oneshot", "chase"):
            return False
        self.add_fx("vapor", 10, self.acolors("te", ["#ffffff", "#f4f4f4", "#e2e2e2", "#c8c8c8"]))
        self.speak("te", ["¿Gustas una taza de té?"], 2.6)
        self.start_sit(10)
        guests = [p for p in self.app.others(self) if p.state in ("idle", "walk", "sit")
                  and abs(p.y - self.y) < 5 and p.surface == self.surface
                  and abs(p.x - self.x) < 800]
        if guests:
            g = self.pick_partner(guests, "amiga")
            side = 1 if g.x > self.x else -1
            tx = self.x + side * (self.BW + g.BW) * 0.6
            if g.affinity(self) <= -2:                    # no acepta el té de alguien que odia
                self.root.after(1500, lambda: g.speak("rechaza_te", ["No, gracias."], 2.4,
                                                      otra=self.name()))
                return True

            def sit_down():
                if g.state in ("idle",) and abs(g.y - self.y) < 5:
                    g.facing = -side
                    g.speak("te_invitada", ["¡Gracias por el té!"], 2.2, otra=self.name())
                    g.start_sit(8)
            g.go_to(tx, sit_down)
        return True

    def curious(self):
        others = [p for p in self.app.others(self) if p.state in ("idle", "walk", "sit", "sleep")
                  and abs(p.y - self.y) < 5 and p.surface == self.surface
                  and abs(p.x - self.x) < 900]
        if others:
            o = random.choice(others)
            side = 1 if self.x < o.x else -1
            tx = o.x - side * (self.BW + o.BW) * 0.55

            def ask():
                if o in self.app.pets:
                    self.facing = 1 if o.x > self.x else -1
                    self.speak("curiosidad", ["Dime, ¿qué se siente ser tú?"], 3, otra=o.name())
                    if o.state in ("idle", "sit"):
                        o.facing = -self.facing
                        self.root.after(1600, lambda: o.speak("respuesta_curiosa",
                                                              ["¿Eh? ¿Y eso qué?", "..."], 2.2,
                                                              otra=self.name()))
            self.go_to(tx, ask)
            return True
        cx, cy = cursor_pos()
        m = self.monitor_at(self.x)
        if m[0] <= cx < m[2] and self.surface is None:
            def ask_mouse():
                self.facing = 1 if cx > self.x else -1
                self.speak("curiosidad_mouse", ["¿Qué estás haciendo? Cuéntame todo."], 3)
            self.go_to(min(max(cx, m[0] + self.BW), m[2] - self.BW), ask_mouse)
            return True
        return False

    def shadow_hands(self):
        if self.state not in ("idle", "walk", "sit", "oneshot", "chase", "fight"):
            return False
        pets = [p for p in self.app.others(self) if p.state not in ("drag", "tp")
                and not p.hidden and math.hypot(p.x - self.x, p.y - self.y) < SHOT_RANGE]
        self.speak("manos", ["Ven aquí..."], 2)
        if pets:
            p = min(pets, key=lambda q: abs(q.x - self.x) + abs(q.y - self.y))
            self.shoot(p.x, p.y + p.y_off - p.BH * 0.5, p, kind="mano")
        elif self.fight_on and MOUSE_PLAY:
            cx, cy = cursor_pos()
            if math.hypot(cx - self.x, cy - self.y) > SHOT_RANGE:
                return False
            self.shoot(cx, cy, None, kind="mano", grab_cursor=True)
        else:
            return False
        if self.state != "fight":
            self.state = "beam"
            self.vx = 0
            self.beam = {"phase": "fire", "t": time.perf_counter() + 1.3, "then": None,
                         "target": (self.x, self.y), "hwnd": None, "width": 7, "acc": 0.0}
        return True

    # ---------- disparar ----------
    def shot_kind(self):
        """Qué dispara: lo define "disparo" en el .json de la skin."""
        k = self.skin_cfg.get("disparo")
        if k in ("lucero", "cristal", "hielo", "rayo", "bala", "elementos", "mano", "corte"):
            return k
        habs = self.abilities()
        if "rayo" in habs:
            return "rayo"
        if "cristales" in habs:
            return "cristal"
        return "bala"

    def shot_colors(self, kind):
        defaults = {"rayo": ["#ffffff", "#ffe9a8", "#ffb347", "#ff6a00"],
                    "cristal": ["#f3e6ff", "#c592ff", "#9b5cff", "#6a2fd0"],
                    "hielo": ["#ffffff", "#dff4ff", "#9fd6ff", "#5f9bd0"],
                    "lucero": ["#ffffff", "#c9ced6", "#8b929c", "#4b5058"],
                    "mano": ["#b48cff", "#3d1f6e", "#1b0f2e", "#08040f"],
                    "elementos": ELEMENT_COLORS[0],
                    "corte": ["#ffffff", "#fff2b3", "#ffcc33", "#d48a00"]}
        return (self.skin_cfg.get("colores") or {}).get("disparo") or \
            defaults.get(kind) or self.particles.colors

    def shoot(self, tx, ty, target=None, big=False, kind=None, grab_cursor=False, on_reach=None):
        """Dispara hacia (tx, ty). target: mascota a la que le apunta (para el golpe)."""
        kind = kind or self.shot_kind()
        cols = self.shot_colors(kind)
        self.facing = 1 if tx > self.x else -1
        self.pose_until = time.perf_counter() + 0.5
        self.set_anim("mira" if self.has_anim("mira") else "quieta")
        hx, hy = self.hand_front()
        self.particles.emit(8, hx, hy, 4, 4, up=0, colors=cols, speed=(30, 90),
                            life=(0.15, 0.35), star=0.7, g=0)
        if kind == "rayo":
            self.app.beams.append(Beam(self.root, hx, hy, tx, ty, cols,
                                       width=12 if big else 7, seconds=0.35))
            if target is not None and target in self.app.pets:
                cx, cy = target.x, target.y + target.y_off - target.BH * 0.5
                if abs(cx - tx) < target.BW and abs(cy - ty) < target.BH:
                    self.projectile_hit(target, None)
            return
        if kind == "elementos":                       # cuatro esferas de colores
            order = random.sample(range(4), 4)
            for i, e in enumerate(order[:3 if not big else 4]):
                spread = (i - 1) * 24
                self.app.projectiles.append(
                    Projectile(self.app, self, "bala", tx, ty + spread, ELEMENT_COLORS[e],
                               target=target, delay=i * 0.12))
        else:
            n = 3 if kind == "hielo" else (2 if kind == "cristal" and big else 1)
            for i in range(n):
                spread = (i - (n - 1) / 2) * 26
                self.app.projectiles.append(
                    Projectile(self.app, self, kind, tx, ty + spread, cols, target=target,
                               delay=i * 0.09, grab_cursor=grab_cursor,
                               on_reach=on_reach if i == 0 else None, big=big))
        if target is not None and target in self.app.pets:
            target.maybe_dodge(self)

    def maybe_dodge(self, shooter):
        """A veces esquiva brincando."""
        ratio = max(0.3, min(3.5, self.power() / max(0.5, shooter.power())))
        if self.state in ("idle", "walk", "sit", "fight", "tag", "chase") and \
                random.random() < min(0.9, DODGE_CHANCE * ratio):
            delay = int(random.uniform(0.12, 0.25) * 1000)

            def jump():
                if self.state in ("idle", "walk", "sit", "fight", "tag", "chase"):
                    self.to_air(-720, 0, leave=False)
                    if random.random() < 0.6:
                        self.speak("esquiva", ["¡Fallaste!", "¡Ja, ni cerca!"], 1.4,
                                   otra=shooter.name())
            self.root.after(delay, jump)

    def projectile_hit(self, other, proj):
        """Uno de mis disparos le pegó a 'other'."""
        f = self.app.fight
        if f and other in (f["a"], f["b"]) and self in (f["a"], f["b"]):
            f["hits"][self] = f["hits"].get(self, 0) + self.power()   # cada golpe vale su poder
        away = 1 if other.x > self.x else -1
        strength = max(0.5, min(4.0, 1 + (self.power() - other.power()) / 3.0))
        cols = proj.colors if proj is not None else self.shot_colors(self.shot_kind())
        if proj is not None and proj.kind == "mano":    # la mano de sombra la jala
            other.get_hit(-away, cols, pull=True, strength=strength)
        else:
            other.get_hit(away, cols, strength=strength)
        if not f and not self.app.game and random.random() < REVENGE_CHANCE:
            # si le disparan sin estar peleando, a veces se enoja y responde
            self.root.after(900, lambda: self.app.start_fight(other, self))

    def pick_shot_target(self):
        """Mascota cercana > cursor > una ventana > al aire."""
        pets = [p for p in self.app.others(self)
                if p.state not in ("drag", "tp") and not p.hidden
                and math.hypot(p.x - self.x, p.y - self.y) < SHOT_RANGE]
        if pets and random.random() < 0.7:
            p = random.choice(pets)
            return p.x, p.y + p.y_off - p.BH * 0.5, p, None
        if MOUSE_PLAY:
            cx, cy = cursor_pos()
            if math.hypot(cx - self.x, cy - self.y) < SHOT_RANGE and random.random() < 0.6:
                return cx, cy, None, None
        opts = []
        for i, (h, l, t, r, b, standable) in enumerate(self.windows):
            if not standable:
                continue
            px, py = random.uniform(l + 40, r - 40), random.uniform(t + 20, min(b, t + 250))
            if self.point_visible(px, py, i) and math.hypot(px - self.x, py - self.y) < 1200:
                opts.append((px, py, None, h))
        if opts and random.random() < 0.6:
            return random.choice(opts)
        return (self.x + self.facing * random.uniform(250, 500),
                self.y - random.uniform(120, 400), None, None)

    def try_shoot(self):
        if self.state not in ("idle", "walk", "sit", "oneshot", "chase"):
            return False
        tx, ty, target, hwnd = self.pick_shot_target()
        self.state = "beam"                           # se queda quieta mientras dispara
        self.vx = 0
        self.beam = {"phase": "fire", "t": time.perf_counter() + 0.9, "then": None,
                     "target": (tx, ty), "hwnd": None, "width": 7, "acc": 0.0}
        self.speak("disparo", ["¡Toma!"], 1.3, otra=target.name() if target else "")
        self.shoot(tx, ty, target)
        if hwnd is not None and self.pranks:
            self.root.after(200, lambda: self.app.shake(hwnd))
        return True

    # ---------- habilidad: lucero girando (Rem) ----------
    def spin_attack(self):
        if self.state not in ("idle", "walk", "sit", "oneshot", "fight", "chase"):
            return False
        cols = self.shot_colors("lucero")
        self.app.projectiles.append(Projectile(self.app, self, "giro", self.x, self.y, cols))
        self.speak("lucero", ["¡Gira!"], 1.6)
        if self.state != "fight":
            self.state = "beam"
            self.vx = 0
            self.beam = {"phase": "fire", "t": time.perf_counter() + 1.9, "then": None,
                         "target": (self.x, self.y), "hwnd": None, "width": 7, "acc": 0.0}
        self.pose_until = time.perf_counter() + 1.8
        self.set_anim("quieta")
        return True

    # ---------- peleas entre mascotas ----------
    def join_fight(self):
        self.state = "fight"
        self.vx = 0
        self.pose_until = 0.0
        self.set_anim("quieta")

    def leave_fight(self, result):
        if result == "gana":
            self.particles.emit(20, self.x, self.y - self.BH * 0.6, self.BW * 0.5, self.BH * 0.3,
                                up=90, speed=(20, 80), life=(0.5, 1.0), star=0.8)
            for name in ("feliz", "extra_saluda"):
                if self.has_anim(name):
                    self.play_once(name, lambda: self.start_idle(random.uniform(1.5, 3)),
                                   seconds=1.8, loop=name.startswith("extra_"))
                    return
        elif result == "pierde" and self.has_anim("aterriza"):
            self.play_once("aterriza", lambda: self.start_idle(random.uniform(1.5, 3)), seconds=1.6)
            return
        self.start_idle(random.uniform(1, 2))

    def fight_role(self):
        f = self.app.fight
        if not f:
            return None
        if f["a"] is self:
            return "a"
        if f["b"] is self:
            return "b"
        return None

    def update_fight(self, dt, m):
        f = self.app.fight
        r = self.fight_role()
        if r is None:
            self.start_idle(random.uniform(1, 2))
            return
        now = time.perf_counter()
        other = f["b"] if r == "a" else f["a"]
        dx = other.x - self.x
        dy = (other.y - other.BH * 0.5) - (self.y - self.BH * 0.5)
        dist = math.hypot(dx, dy)
        if other.state not in ("air", "fly"):
            self.facing = 1 if dx > 0 else -1
        if now < self.pose_until:
            return
        if other.state != "fight":                       # la otra va volando del golpe
            self.set_anim("quieta")
            return
        want = FIGHT_DISTANCE + (self.BW + other.BW) * 0.3
        same_level = abs(other.y - self.y) < 8
        if dist > want + 140:                            # muy lejos: acercarse
            if same_level:
                self.fight_walk(other.x - (1 if dx > 0 else -1) * want, dt, m)
                return
            if now >= self.tag_cd:
                self.tag_cd = now + 1.6
                ddy = other.y - self.y
                tx = other.x - (1 if dx > 0 else -1) * want * 0.7
                if "teletransporte" in self.abilities() and random.random() < 0.5:
                    self.start_teleport(dest=(other.surface, tx, other.y))
                elif -JUMP_REACH_UP * 1.3 <= ddy <= 700 and abs(dx) < JUMP_REACH_X * 1.6:
                    self.jump_to(tx, other.y)
                elif not self.app.fight.get("reached"):
                    self.app.end_fight(None)
            return
        f["reached"] = True
        if same_level and dist < want * 0.45:            # muy encima: se hace para atrás
            self.fight_walk(self.x - (1 if dx > 0 else -1) * want * 0.5, dt, m)
            return
        if f["turn"] is self and now >= f["next"] and not f["resolve_at"]:
            if "lucero" in self.abilities() and random.random() < 0.3 and dist < 170:
                self.spin_attack()
            else:
                big = random.random() < 0.3
                self.shoot(other.x, other.y + other.y_off - other.BH * 0.5, other, big=big)
                if random.random() < 0.4:
                    self.speak("ataque", ["¡Toma!", "¡Ja!"], 1.2, otra=other.name())
            f["exchanges"] += 1
            f["turn"] = other
            f["next"] = now + random.uniform(1.0, 1.5)
            if f["exchanges"] >= f["max"]:
                f["resolve_at"] = now + 1.4
        else:
            self.set_anim("quieta")

    def fight_walk(self, tx, dt, m):
        lo, hi = self.surface_bounds(m)
        tx = min(max(tx, lo), hi)
        step = tx - self.x
        if abs(step) > 3:
            st = max(-abs(step), min(abs(step), RUN_SPEED * self.spd() * dt)) * (1 if step > 0 else -1)
            self.x += st
            self.walk_dist += abs(st)
            self.facing = 1 if step > 0 else -1
            self.set_anim("corre")
        else:
            self.set_anim("quieta")

    def get_hit(self, direction, colors, pull=False, strength=1.0):
        self.particles.emit(int(14 + 6 * strength), self.x, self.y + self.y_off - self.BH * 0.5,
                            self.BW * 0.3, self.BH * 0.3, up=30, colors=colors,
                            speed=(40, 150 * strength), life=(0.3, 0.6), star=0.6)
        if strength <= 0.55 and self.state not in ("drag", "tp"):
            if random.random() < 0.5:                     # mucho más fuerte: ni se mueve
                self.speak("resiste", ["¿Eso fue todo?", "Ni lo sentí."], 1.6)
            return
        if strength >= 2.2:
            self.speak("vuela_lejos", ["¡Waaaah!", "¡Aaaay!"], 1.6)
        elif random.random() < 0.45:
            self.speak("golpe", ["¡Ay!", "¡Oye!"], 1.2)
        if self.state in ("fly",):
            self.vx += direction * 300                   # volando solo se tambalea
            return
        if self.state in ("drag", "tp", "climb"):
            return
        if self.state == "sleep":
            self.wake()
            return
        k = max(1.0, strength)
        if pull:
            self.to_air(-380 * min(k, 1.6), direction * 340 * k, leave=False)
        else:
            self.to_air(-330 * min(k, 2.4), direction * 230 * k, leave=False)

    # ---------- con otras mascotas ----------
    def role(self):
        g = self.app.game
        if not g:
            return None
        if g["chaser"] is self:
            return "chaser"
        if g["runner"] is self:
            return "runner"
        return None

    def join_game(self):
        if self.state == "sleep" or self.state in ("idle", "walk", "sit", "goto", "oneshot",
                                                   "chase", "push", "mgrab"):
            self.state = "tag"
            self.set_anim("quieta")
        self.tag_cd = 0.0

    def leave_game(self, quiet=False):
        if self.state == "fly" and self.fly_mode in ("tagc", "tagr"):
            self.end_follow(time.perf_counter())
            return
        if self.state != "tag":
            return
        if quiet:
            self.start_idle(random.uniform(1, 2))
            return
        self.say(self.phrase("fin_juego", ["¡Otra vez!", "Jajaja", "¡Gané yo!", "Uf, me cansé"]), 2.2)
        for name in ("feliz", "extra_saluda"):
            if self.has_anim(name):
                self.play_once(name, lambda: self.start_idle(random.uniform(1.5, 3)),
                               seconds=1.6, loop=name.startswith("extra_"))
                return
        self.start_idle(random.uniform(1, 2))

    def touching(self, other):
        return (abs(other.x - self.x) < (self.BW + other.BW) * 0.4 and
                abs((other.y + other.y_off - other.BH / 2) - (self.y + self.y_off - self.BH / 2))
                < (self.BH + other.BH) * 0.3)

    def surface_bounds(self, m):
        if self.surface is not None:
            l, t, r, b = self.surf_rect
            return l + self.BW * 0.5, r - self.BW * 0.5
        lo = -10 ** 9 if self.neighbor(m, -1) else m[0] + self.BW * 0.5
        hi = 10 ** 9 if self.neighbor(m, 1) else m[2] - self.BW * 0.5
        return lo, hi

    def update_tag(self, dt, m):
        g = self.app.game
        r = self.role()
        if r is None:
            self.start_idle(random.uniform(1, 2))
            return
        now = time.perf_counter()
        other = g["runner"] if r == "chaser" else g["chaser"]
        lo, hi = self.surface_bounds(m)
        if r == "chaser":
            if now < g["pause_until"]:                     # contando hasta tres...
                self.facing = 1 if other.x > self.x else -1
                self.set_anim("quieta")
                return
            if self.touching(other):
                self.app.caught()
                return
            if self.can_fly() and (other.state in ("fly", "air", "climb") or
                                   abs(other.y - self.y) > 40):
                self.start_fly(TAG_SECONDS, mode="tagc")
                return
            head = self.y - self.BH
            ocy = other.y + other.y_off - other.BH * 0.5
            if other.state in ("fly", "air") and abs(other.x - self.x) < 160 and \
                    0 < head - ocy < CATCH_HEIGHT * 1.6 and now >= self.tag_cd:
                self.tag_cd = now + 1.0                    # brinca para alcanzarla
                h = head - ocy + self.BH * 0.6
                self.to_air(-(2 * GRAVITY * h) ** 0.5, (other.x - self.x) * 2, leave=False)
                return
            dy = other.y - self.y
            if abs(dy) > 12 and other.state in ("tag", "idle", "oneshot") and now >= self.tag_cd:
                self.tag_cd = now + 1.2                    # está en otra ventana/piso: brinca
                if -JUMP_REACH_UP <= dy <= 600 and abs(other.x - self.x) <= JUMP_REACH_X:
                    self.jump_to(other.x + random.uniform(-20, 20), other.y)
                    return
            tx = min(max(other.x, lo), hi)
            speed = RUN_SPEED * 1.25
        else:
            chaser = other
            away = 1 if self.x >= chaser.x else -1
            if abs(chaser.x - self.x) > 700 and now >= g["pause_until"]:
                self.facing = 1 if chaser.x > self.x else -1
                self.set_anim("quieta")                    # la tiene lejos: la espera
                return
            if self.can_fly() and abs(chaser.x - self.x) < 220 and random.random() < 0.02:
                self.start_fly(random.uniform(2.5, 4.5), mode="tagr")   # se escapa volando
                return
            tx = self.x + away * 200
            if (away < 0 and self.x - lo < self.BW * 0.3) or (away > 0 and hi - self.x < self.BW * 0.3):
                if now >= self.tag_cd:
                    self.tag_cd = now + 1.5
                    if random.random() < 0.5:
                        if self.surface is not None and random.random() < 0.5:
                            self.to_air(-250, away * RUN_SPEED)        # se avienta de la ventana
                        else:
                            self.to_air(-780, -away * 260, leave=False)  # salta por encima
                        return
                tx = self.x
            speed = RUN_SPEED * 0.95
        dx = tx - self.x
        speed *= self.spd()
        if abs(dx) > 3:
            step = max(-abs(dx), min(abs(dx), speed * dt)) * (1 if dx > 0 else -1)
            self.x += step
            self.walk_dist += abs(step)
            self.facing = 1 if dx > 0 else -1
            self.set_anim("corre")
        else:
            self.set_anim("quieta")

    def try_greet(self):
        """Va con otra mascota que esté cerca y se saludan."""
        options = [p for p in self.app.others(self) if p.state in ("idle", "walk", "sit")
                   and abs(p.y - self.y) < 5 and abs(p.x - self.x) < 900 and p.surface == self.surface]
        if not options:
            return False
        other = self.pick_partner(options, "amiga")
        side = 1 if self.x < other.x else -1
        tx = other.x - side * (self.BW + other.BW) * 0.55

        def arrive():
            if other in self.app.pets and other.grounded() and abs(other.y - self.y) < 5:
                self.facing = 1 if other.x > self.x else -1
                other.facing = -self.facing
                for p, q, words in ((self, other, ["¡Hola!", "¡Holi!", "¿Qué haces?"]),
                                    (other, self, ["¡Hola!", "¡Hey!", "Hmm, ¿qué quieres?"])):
                    p.say(p.phrase("saludo_otra", words, otra=q.name()), 2.2)
                    for name in ("extra_saluda", "feliz"):
                        if p.has_anim(name):
                            p.play_once(name, lambda p=p: p.start_idle(random.uniform(1, 3)),
                                        seconds=1.8, loop=name.startswith("extra_"))
                            break
        self.go_to(tx, arrive)
        return True

    def make_room(self):
        """Si está encimada con otra, se hace a un lado."""
        for p in self.app.others(self):
            if p.surface == self.surface and abs(p.y - self.y) < 5 and \
                    abs(p.x - self.x) < (self.BW + p.BW) * 0.3 and p.state not in ("drag", "air"):
                side = 1 if self.x >= p.x else -1
                m = self.monitor_at(self.x)
                lo, hi = self.surface_bounds(m)
                tx = min(max(self.x + side * self.BW * 1.1, lo), hi)
                if abs(tx - self.x) > 10:
                    self.go_to(tx, None)
                    return True
        return False

    def destroy(self):
        for w in (self.win, self.bubble.win, self.particles.win):
            try:
                w.destroy()
            except Exception:
                pass
        try:
            self.menu.destroy()
        except Exception:
            pass

    # ---------- pelear por el mouse ----------
    def hand_point(self):
        if self.state == "fly" and self.fly_mode in ("follow", "carry"):
            # volando lleva el mouse por delante, como si lo tuviera agarrado
            return (int(self.x + self.facing * self.BW * 0.45),
                    int(self.y + self.y_off - self.BH * 0.5))
        return (int(self.x - self.facing * self.BW * 0.45), int(self.y + self.y_off - self.BH * 0.5))

    def start_mouse_grab(self):
        if "congelar" in self.abilities():             # lo congela en su lugar
            cx, cy = cursor_pos()
            self.mgrab = {"until": time.perf_counter() + random.uniform(*FIGHT_SECONDS),
                          "dir": self.facing, "resist": 0.0, "last": (cx, cy), "freeze": (cx, cy)}
            self.state = "mgrab"
            self.fight = False
            self.chase_until = 0.0
            self.facing = 1 if cx > self.x else -1
            self.set_anim("mira" if self.has_anim("mira") else "quieta")
            self.add_fx("hielo_cursor", FIGHT_SECONDS[1] + 0.5,
                        self.acolors("cristales", ["#ffffff", "#e3f6ff", "#a9dcff", "#6fa8d6"]))
            self.say(self.phrase("congelar", ["¡Congelado!"]), 1.8)
            return
        m = self.monitor_at(self.x)
        room_r, room_l = m[2] - self.x, self.x - m[0]
        self.mgrab = {"until": time.perf_counter() + random.uniform(*FIGHT_SECONDS),
                      "dir": 1 if room_r > room_l else -1, "resist": 0.0, "last": None}
        self.state = "mgrab"
        self.fight = False
        self.chase_until = 0.0
        self.facing = self.mgrab["dir"]
        self.set_anim("corre")
        hx, hy = self.hand_point()
        user32.SetCursorPos(hx, hy)
        self.mgrab["last"] = (hx, hy)
        self.say(self.phrase("mouse_agarra", ["¡Es mío!", "¡Atrapado!", "¡Mi mouse!", "Jeje"]), 1.6)

    def release_mouse(self, won):
        self.mgrab = None
        self.fx = [f for f in self.fx if f["kind"] != "hielo_cursor"]
        if won is True:
            self.say(self.phrase("mouse_gana", ["¡Toma, ahí está!", "Jiji", "¡Gané!"]), 2.2)
            for name in ("feliz", "extra_saluda"):
                if self.has_anim(name):
                    self.play_once(name, lambda: self.start_idle(random.uniform(1.5, 3)),
                                   seconds=1.5, loop=name.startswith("extra_"))
                    return
        elif won is False:
            self.say(self.phrase("mouse_pierde", ["¡Hmph!", "¡Oye!", "Ya, ya...", "¡No es justo!"]), 2.2)
            if self.has_anim("aterriza"):
                self.play_once("aterriza", lambda: self.start_idle(random.uniform(1, 2)),
                               seconds=1.2)
                return
        self.start_idle(random.uniform(1, 2))

    def update_mouse_grab(self, dt, m):
        g = self.mgrab
        if not g or mouse_down():
            self.release_mouse(None)                 # estás haciendo clic: lo suelta ya
            return
        cx, cy = cursor_pos()
        ux, uy = cx - g["last"][0], cy - g["last"][1]
        pull = (ux * ux + uy * uy) ** 0.5
        g["resist"] = g["resist"] * 0.97 + pull       # cuánto la estás jalando
        if g["resist"] > FIGHT_RESIST:
            self.release_mouse(False)
            return
        if g.get("freeze"):                           # hielo: el mouse se queda quieto
            user32.SetCursorPos(*g["freeze"])
            g["last"] = g["freeze"]
            self.set_anim("mira" if self.has_anim("mira") else "quieta")
            if time.perf_counter() >= g["until"]:
                self.fx = [f for f in self.fx if f["kind"] != "hielo_cursor"]
                self.release_mouse(True)
            return
        self.x += ux * 0.35                           # el jalón también la mueve a ella
        step = WALK_SPEED * 1.3 * g["dir"] * dt
        self.x += step
        self.walk_dist += abs(step)
        if self.surface is not None:
            l, t, r, b = self.surf_rect
            lo, hi = l + self.BW * 0.5, r - self.BW * 0.5
        else:
            lo, hi = m[0] + self.BW * 0.5, m[2] - self.BW * 0.5
        if self.x < lo or self.x > hi:
            self.x = min(max(self.x, lo), hi)
            g["dir"] = -g["dir"]
        self.facing = g["dir"]
        self.set_anim("corre")
        hx, hy = self.hand_point()
        user32.SetCursorPos(hx, hy)
        g["last"] = (hx, hy)
        if time.perf_counter() >= g["until"]:
            self.release_mouse(True)

    # ---------- jugar con el mouse ----------
    def start_chase(self, seconds):
        if seconds is not None:
            self.chase_until = time.perf_counter() + seconds
        self.state = "chase"
        self.vx = 0
        self.set_anim("quieta")

    def update_chase(self, dt, m):
        now = time.perf_counter()
        cx, cy = cursor_pos()
        if now >= self.chase_until:
            self.chase_until = 0.0
            self.fight = False
            self.start_idle(random.uniform(1, 2.5))
            return
        other_mon = not (m[0] <= cx < m[2] and m[1] <= cy < m[3])
        far_up = (self.y - self.BH) - cy > CATCH_HEIGHT * 0.8
        if self.can_fly() and (other_mon or far_up or abs(cx - self.x) > 450):
            self.start_fly(self.chase_until - now, mode="follow")   # lo sigue volando
            return
        if other_mon and self.surface is None and not (
                (cx < m[0] and self.neighbor(m, -1)) or (cx >= m[2] and self.neighbor(m, 1))):
            self.chase_until = 0.0                    # no hay cómo llegar a esa pantalla
            self.fight = False
            self.start_idle(random.uniform(1, 2.5))
            return
        if self.surface is not None:
            l, t, r, b = self.surf_rect
            lo, hi = l + self.BW * 0.5, r - self.BW * 0.5
        else:                                         # si hay pantalla al lado, puede cruzar
            lo = -10 ** 9 if self.neighbor(m, -1) else m[0] + self.BW * 0.5
            hi = 10 ** 9 if self.neighbor(m, 1) else m[2] - self.BW * 0.5
        tx = min(max(cx, lo), hi)
        dx = tx - self.x
        if abs(dx) > self.BW * 0.3:
            speed = (RUN_SPEED if abs(dx) > 160 else WALK_SPEED) * self.spd()
            step = max(-abs(dx), min(abs(dx), speed * dt)) * (1 if dx > 0 else -1)
            self.x += step
            self.walk_dist += abs(step)
            self.facing = 1 if dx > 0 else -1
            self.set_anim("corre" if speed > WALK_SPEED else "camina")
        else:
            if abs(cx - self.x) > 4:
                self.facing = 1 if cx > self.x else -1
            self.set_anim("quieta")
        if self.fight and abs(cx - self.x) < self.BW * 0.7 and not self.mouse_taken() and \
                self.y - self.BH * 0.95 < cy < self.y - self.BH * 0.1 and not mouse_down():
            self.start_mouse_grab()
            return
        head = self.y - self.BH
        if now >= self.jump_cd and abs(cx - self.x) < self.BW and 0 < head - cy < CATCH_HEIGHT:
            self.jump_cd = now + random.uniform(1.0, 2.0)
            h = head - cy + self.BH * 0.5
            self.to_air(-(2 * GRAVITY * h) ** 0.5, (cx - self.x) * 2, leave=False)

    # ---------- galleta ----------
    def on_treat_landed(self):
        """La galleta acaba de caer: ¡a comer!"""
        self.treat_tries = 0
        self.chase_until = 0.0
        if self.in_game():
            return
        if self.state == "sleep":
            self.wake()
        elif self.state in ("idle", "walk", "sit", "chase"):
            self.timer = 0
            if self.state == "chase":
                self.start_idle(0.2)

    def react_treat(self):
        t = self.treat
        if t and t.landed and self.state in ("idle", "walk", "goto", "sit", "chase", "oneshot", "tag") \
                and abs(t.x - self.x) < self.BW * 0.5 and abs(t.y - self.y) < 4:
            self.eat()

    def go_eat(self):
        t = self.treat
        self.treat_tries += 1
        if self.treat_tries > 6:
            return False
        same = (t.surface == self.surface) or (t.surface is None and self.surface is None)
        if same:
            self.go_to(t.x, None)
            return True
        if t.surface is None and self.surface is not None:      # bajarse hacia ella
            side = 1 if t.x > self.x else -1
            l, t2, r, b = self.surf_rect
            edge_dist = (r - self.x) if side > 0 else (self.x - l)
            self.facing = side
            self.to_air(-420, side * min(400, max(220, edge_dist * 2)))
            return True
        rect = visible_rect(t.surface)                           # está sobre otra ventana
        self.jump_to(t.x, rect[1])
        return True

    def eat(self):
        if self.treat:
            self.treat.destroy()
            self.treat = None
        self.say(self.phrase("comer", ["¡Rico!", "¡Gracias!", "Ñam ñam", "¡Otra!"]), 2.5, sound=False)
        for p in self.app.others(self):                  # las que no alcanzaron
            if p.state in ("goto", "idle", "walk") and abs(p.x - self.x) < 600:
                p.say(p.phrase("sin_galleta", ["Aww...", "¡Oye, era mía!", "Hmph"], otra=self.name()), 2)
                if p.state == "goto":
                    p.start_idle(random.uniform(0.5, 1.5))
        if self.has_anim("feliz"):
            self.play_once("feliz", lambda: self.start_idle(random.uniform(1, 2)), seconds=1.5)
        else:
            self.to_air(-600, 0, leave=False)

    # ---------- recordatorios (los maneja App) ----------
    def remind(self, text):
        self.say(text, BUBBLE_SECONDS, sound=REMINDER_SOUND)
        if self.state == "sleep":
            self.wake()
        elif self.state in ("idle", "walk", "sit"):
            for name in ("extra_saluda", "feliz"):
                if self.has_anim(name):
                    self.play_once(name, lambda: self.start_idle(random.uniform(2, 4)),
                                   seconds=3.0, loop=name.startswith("extra_"))
                    break

    def say(self, text, seconds, sound=False):
        self.bubble.show(text, seconds)
        if sound:
            try:
                user32.MessageBeep(0x40)
            except Exception:
                pass

    # ---------- menú ----------
    def build_menu(self):
        v = self.app.vars
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Dormir / despertar", command=self.menu_sleep)
        self.menu.add_command(label="Sentarse", command=self.menu_sit)
        self.menu.add_command(label="Saltar", command=self.menu_jump)
        self.menu.add_command(label="Jugar conmigo (persigue el mouse)", command=self.menu_play)
        self.menu.add_command(label="Darle una galleta", command=self.menu_treat)
        self.menu.add_checkbutton(label="Travesuras (empujar ventanas)", variable=v["travesuras"],
                                  command=self.menu_prank_toggle)
        self.menu.add_command(label="¡Haz una travesura!", command=self.menu_prank_now)
        self.menu.add_checkbutton(label="Pelear por el mouse", variable=v["pelear_mouse"],
                                  command=self.menu_fight_toggle)
        self.menu.add_command(label="¡Pelea conmigo!", command=self.menu_fight_now)
        self.menu.add_checkbutton(label="Volar (skins que vuelan)", variable=v["volar"],
                                  command=self.menu_fly_toggle)
        self.menu.add_command(label="¡Vuela!", command=self.menu_fly_now)
        self.menu.add_command(label="Habilidad especial", command=self.menu_ability)
        self.menu.add_command(label="¡Dispara!", command=self.menu_shoot)
        self.menu.add_checkbutton(label="Poderes pesados (minimizar ventanas, lanzar el mouse)",
                                  variable=v["poderes_pesados"],
                                  command=lambda: self.app.set_flag("poderes_pesados"))
        self.pets_menu = tk.Menu(self.menu, tearoff=0, postcommand=self.fill_pets_menu)
        self.menu.add_cascade(label="Mascotas", menu=self.pets_menu)
        rem = tk.Menu(self.menu, tearoff=0)
        rem.add_checkbutton(label="Activados", variable=v["recordatorios_activos"],
                            command=self.menu_rem_toggle)
        rem.add_command(label="Nuevo recordatorio...", command=self.menu_rem_new)
        rem.add_command(label="Ver los próximos", command=self.menu_rem_list)
        rem.add_command(label="Borrar los míos", command=self.menu_rem_clear)
        self.menu.add_cascade(label="Recordatorios", menu=rem)
        self.pause_var = tk.BooleanVar(value=False)
        self.menu.add_checkbutton(label="Quedarse quieta", variable=self.pause_var,
                                  command=self.menu_pause)
        sizes = tk.Menu(self.menu, tearoff=0)
        self.size_var = tk.DoubleVar(value=self.scale)
        for sz in SIZES:
            sizes.add_radiobutton(label="%d %%" % round(sz * 100), value=sz,
                                  variable=self.size_var, command=self.menu_size)
        self.menu.add_cascade(label="Tamaño", menu=sizes)
        self.skin_menu = tk.Menu(self.menu, tearoff=0, postcommand=self.fill_skin_menu)
        self.skin_var = tk.StringVar(value=self.skin or "")
        self.menu.add_cascade(label="Skin", menu=self.skin_menu)
        self.menu.add_separator()
        self.autostart_var = tk.BooleanVar(value=autostart_enabled())
        self.menu.add_checkbutton(label="Iniciar con Windows", variable=self.autostart_var,
                                  command=self.menu_autostart)
        self.menu.add_command(label="Salir (todas)", command=self.app.quit)

    def fill_pets_menu(self):
        m = self.pets_menu
        m.delete(0, "end")
        add = tk.Menu(m, tearoff=0)
        for name, _p in list_skins():
            add.add_command(label=name, command=lambda n=name: self.app.add_pet(n, near=self))
        m.add_cascade(label="Agregar mascota", menu=add)
        many = len(self.app.pets) > 1
        m.add_command(label="Jugar a las atrapadas", command=self.menu_tag,
                      state="normal" if many else "disabled")
        m.add_command(label="Saludar a otra", command=self.menu_greet,
                      state="normal" if many else "disabled")
        m.add_command(label="Pelear con otra", command=self.menu_fight_pet,
                      state="normal" if many else "disabled")
        m.add_separator()
        m.add_command(label="Quitar esta mascota", command=lambda: self.app.remove_pet(self),
                      state="normal" if many else "disabled")

    def menu_tag(self):
        if self.app.game:
            self.app.end_game()
            return
        others = [p for p in self.app.others(self) if p.state != "drag"]
        if not others:
            return
        if self.state == "sleep":
            self.wake()
        other = min(others, key=lambda p: abs(p.x - self.x) + abs(p.y - self.y))
        if other.state == "sleep":
            other.wake()
        self.app.start_game(self, other)

    def menu_ability(self):
        if self.state == "sleep":
            self.wake()
        elif not self.grounded():
            return
        elif not [h for h in self.abilities() if h in ABILITY_NAMES]:
            self.say("No tengo habilidades especiales", 2.5)
        else:
            if self.state not in ("idle", "walk", "sit", "oneshot"):
                self.start_idle(0.5)
            if not self.try_ability():
                self.say("Ahorita no puedo", 2)

    def menu_autostart(self):
        ok = set_autostart(self.autostart_var.get())
        if not ok:
            self.autostart_var.set(autostart_enabled())
            self.say("No pude cambiar el inicio automático", 3)
        else:
            self.say("Listo, arrancaré con Windows." if self.autostart_var.get()
                     else "Ya no arrancaré con Windows.", 3)

    def menu_shoot(self):
        if self.state == "sleep":
            self.wake()
            return
        if self.state == "fight":
            return
        if not self.grounded():
            return
        if self.state not in ("idle", "walk", "sit", "oneshot", "chase"):
            self.start_idle(0.3)
        self.try_shoot()

    def menu_fight_pet(self):
        if self.app.fight:
            self.app.end_fight(None)
            return
        others = [p for p in self.app.others(self) if p.state not in ("drag", "tp")]
        if not others:
            return
        if self.app.game:
            self.app.end_game(quiet=True)
        other = min(others, key=lambda p: abs(p.x - self.x) + abs(p.y - self.y))
        for p in (self, other):
            if p.state in ("sleep", "climb", "mgrab", "push", "beam"):
                p.mgrab = None
                p.start_idle(0.2) if p.state != "climb" else p.to_air(0)
        if not self.app.start_fight(self, other):
            self.say("Ahorita no puedo", 2)

    def menu_greet(self):
        if self.grounded() and self.state != "sleep" and not self.try_greet():
            self.say("No hay nadie cerca en mi mismo piso", 2.5)

    def fill_skin_menu(self):
        """Se arma al abrir el menú, así aparecen las skins nuevas sin reiniciar."""
        m = self.skin_menu
        m.delete(0, "end")
        self.skins = list_skins()
        for name, _p in self.skins:
            m.add_radiobutton(label=name, value=name, variable=self.skin_var,
                              command=lambda n=name: self.set_skin(n))
        m.add_separator()
        m.add_command(label="Abrir carpeta de skins", command=self.open_skins_folder)

    def open_skins_folder(self):
        try:
            os.makedirs(SKINS_DIR, exist_ok=True)
            os.startfile(SKINS_DIR)
        except Exception as e:
            self.say("No pude abrir la carpeta: %s" % e, 4)

    def on_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def grounded(self):
        return self.state in ("idle", "walk", "sit", "sleep", "goto", "oneshot", "chase", "push",
                              "mgrab", "tag", "fight", "beam")

    def menu_sleep(self):
        if self.state == "sleep":
            self.wake()
        elif self.grounded():
            self.start_sleep(10 ** 6)

    def menu_sit(self):
        if self.grounded():
            self.start_sit(random.uniform(15, 30))

    def menu_jump(self):
        if self.grounded() and not self.try_window_jump():
            self.to_air(-750, self.facing * 160, leave=False)

    def menu_fight_toggle(self):
        self.app.set_flag("pelear_mouse")
        if not self.fight_on:
            for p in self.app.pets:
                if p.state == "mgrab":
                    p.release_mouse(None)
                if p.state == "fly" and p.fly_mode in ("follow", "carry"):
                    p.mgrab = None
                    p.end_follow(time.perf_counter())

    def menu_fight_now(self):
        if not self.fight_on:
            self.say("Activa 'Pelear por el mouse' primero", 3)
        elif self.state == "sleep":
            self.wake()
        elif self.grounded():
            self.start_chase(10)
            self.fight = True

    def menu_fly_toggle(self):
        self.app.set_flag("volar")
        if not self.fly_on:
            for p in self.app.pets:
                if p.state == "fly":
                    p.fly_mode = "wander"
                    p.fly_until = 0.0

    def menu_fly_now(self):
        if not (self.skin_cfg.get("vuela") and self.is_sheet):
            self.say("Esta skin no sabe volar", 3)
        elif not self.fly_on:
            self.say("Activa 'Volar' primero", 3)
        elif self.state == "sleep":
            self.wake()
        elif self.grounded() or self.state == "air":
            self.start_fly(random.uniform(*FLY_SECONDS))

    def menu_prank_toggle(self):
        self.app.set_flag("travesuras")
        if not self.pranks:
            for p in self.app.pets:
                if p.state == "push":
                    p.end_push(False)

    def menu_prank_now(self):
        if self.state == "sleep":
            self.wake()
            return
        if not self.grounded():
            return
        if self.surface is not None:
            self.say("Bájame al piso primero", 2.5)
            return
        if not self.try_prank():
            self.say("No veo ninguna ventana que pueda empujar", 3)

    def menu_play(self):
        if self.grounded() and self.state != "sleep":
            self.start_chase(12)
        elif self.state == "sleep":
            self.wake()

    def menu_treat(self):
        self.app.drop_treat(self)

    def menu_rem_toggle(self):
        self.app.set_flag("recordatorios_activos")
        on = self.app.flag("recordatorios_activos")
        self.say("Recordatorios activados." if on else "Recordatorios en pausa.", 3)

    def menu_rem_new(self):
        def saved(text, mins, repeat):
            self.app.add_reminder(text, mins, repeat)
            self.say("Listo, te aviso %s %d min." % ("cada" if repeat else "en", mins), 4)
        ReminderDialog(self.root, saved)

    def menu_rem_list(self):
        now = time.perf_counter()
        on = self.app.flag("recordatorios_activos")
        items = sorted(self.app.reminders, key=lambda r: r["next"])[:5]
        if not items or not on:
            self.say("No tengo recordatorios pendientes." if on
                     else "Los recordatorios están en pausa.", 4)
            return
        lines = ["%d min: %s" % (max(0, round((r["next"] - now) / 60)), r["texto"])
                 for r in items]
        self.say("Próximos:\n" + "\n".join(lines), 12)

    def menu_rem_clear(self):
        self.app.reminders = [r for r in self.app.reminders if not r["propio"]]
        self.app.settings["mis_recordatorios"] = []
        self.app.save()
        self.say("Borré tus recordatorios.", 3)

    def menu_pause(self):
        self.paused = self.pause_var.get()
        if self.paused and self.state in ("walk", "goto"):
            self.start_idle(3.0)

    def menu_size(self):
        sz = self.size_var.get()
        self.apply_scale(sz)
        self.cfg["escala"] = sz
        self.app.save()


# ---------- La aplicación: maneja a todas las mascotas ----------
FLAG_DEFAULTS = {"volar": True, "pelear_mouse": MOUSE_FIGHT, "travesuras": PRANKS,
                 "recordatorios_activos": True, "poderes_pesados": POWER_FLAG_DEFAULT}


class App:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.monitors = get_monitors()
        self.windows = []
        self.next_scan = 0.0
        self.treat = None
        self.game = None                 # juego de las atrapadas en curso
        self.fight = None                # pelea en curso
        self.beams = []
        self.projectiles = []
        self.shakes = []
        self.flung = None                # mouse volando (golpe de Reinhard)
        self.vars = {k: tk.BooleanVar(value=bool(self.settings.get(k, v)))
                     for k, v in FLAG_DEFAULTS.items()}
        self.reminders = []
        self.next_rem_check = 0.0
        start = time.perf_counter()
        for r in RECORDATORIOS + self.settings.get("mis_recordatorios", []):
            self.add_reminder(r["texto"], r["cada_min"], True, start, save=False)

        cfgs = self.settings.get("mascotas")
        if not cfgs:                     # ajustes de la versión de una sola mascota
            cfgs = [{"skin": self.settings.get("skin"),
                     "escala": self.settings.get("escala", SHEET_SCALE)}]
        self.settings["mascotas"] = cfgs
        self.pets = []
        for c in cfgs:
            self.pets.append(Pet(self, c))
        self.save()
        self.last = time.perf_counter()
        self.loop()

    # --- ajustes ---
    def flag(self, name):
        return self.vars[name].get()

    def set_flag(self, name):
        self.settings[name] = self.vars[name].get()
        self.save()

    def save(self):
        save_settings(self.settings)

    def others(self, pet):
        return [p for p in self.pets if p is not pet]

    # --- ciclo principal (uno solo para todas) ---
    def loop(self):
        now = time.perf_counter()
        dt = min(0.05, max(0.0, now - self.last))
        self.last = now
        if now >= self.next_scan:
            try:
                self.windows = list_windows(None)
                self.monitors = get_monitors()
            except Exception as e:
                print("Aviso:", e)
            self.next_scan = now + WINDOW_SCAN_MS / 1000.0
        self.check_reminders(now)
        self.update_treat(dt)
        self.update_game(now)
        self.update_fight(now)
        self.beams = [b for b in self.beams if b.update(now)]
        self.projectiles = [pr for pr in self.projectiles if pr.update(now, dt)]
        self.update_fling(dt)
        self.update_shakes(now)
        for p in list(self.pets):
            p.tick(dt, now)
        self.root.after(TICK_MS, self.loop)

    # --- mascotas ---
    def add_pet(self, skin, near=None):
        cfg = {"skin": skin, "escala": near.scale if near else SHEET_SCALE}
        self.settings["mascotas"].append(cfg)
        pet = Pet(self, cfg)
        if near is not None:
            pet.x = near.x + random.choice([-1, 1]) * near.BW * 1.5
            pet.y = near.y - near.BH * 2
        self.pets.append(pet)
        self.save()
        pet.say(pet.phrase("saludo", ["¡Hola!", "¡Ya llegué!", "¿Me extrañaste?"]), 2.5)

    def remove_pet(self, pet):
        if len(self.pets) <= 1:
            pet.say("Soy la única, no me puedo ir", 3)
            return
        self.end_game(quiet=True)
        self.pets.remove(pet)
        if pet.cfg in self.settings["mascotas"]:
            self.settings["mascotas"].remove(pet.cfg)
        self.save()
        pet.destroy()

    # --- galleta (una para todas: ¡la primera que llegue se la come!) ---
    def update_treat(self, dt):
        t = self.treat
        if not t or not self.pets:
            return
        was = t.landed
        t.still_there()
        t.update(dt, self.pets[0])
        if t.landed and not was:
            for p in self.pets:
                p.on_treat_landed()

    def drop_treat(self, near):
        if self.treat:
            self.treat.destroy()
        cx, cy = cursor_pos()
        m = near.monitor_at(near.x)
        x = min(max(cx + random.uniform(-150, 150), m[0] + 40), m[2] - 40)
        y = max(m[1] + 40, min(cy - 120, m[3] - 200))
        self.treat = Treat(self.root, x, y)
        for p in self.pets:
            p.treat_tries = 0

    # --- recordatorios (los dice una mascota al azar) ---
    def add_reminder(self, text, mins, repeat, now=None, save=True):
        now = time.perf_counter() if now is None else now
        self.reminders.append({"texto": text, "cada_min": mins, "repetir": repeat,
                               "propio": save, "next": now + mins * 60})
        if save and repeat:
            mine = self.settings.setdefault("mis_recordatorios", [])
            mine.append({"texto": text, "cada_min": mins})
            self.save()

    def check_reminders(self, now):
        if not self.flag("recordatorios_activos") or now < self.next_rem_check:
            return
        self.next_rem_check = now + 1.0
        for r in list(self.reminders):
            if now >= r["next"]:
                if r["repetir"]:
                    r["next"] = now + r["cada_min"] * 60
                else:
                    self.reminders.remove(r)
                if self.pets:
                    random.choice(self.pets).remind(r["texto"])
                break

    # --- juego de las atrapadas ---
    def start_game(self, a, b):
        if self.game or self.fight or a is b:
            return
        for p in (a, b):
            if p.state == "drag":
                return
            p.mgrab = None
            p.chase_until = 0.0
            p.fight = False
        now = time.perf_counter()
        self.game = {"chaser": a, "runner": b, "rounds": 0, "max": random.randint(2, 4),
                     "until": now + TAG_SECONDS, "pause_until": now + 0.8}
        a.say(a.phrase("juego", ["¡Te voy a atrapar!", "¡Las traes!", "¡A jugar!"], otra=b.name()), 2)
        b.say(b.phrase("juego_huye", ["¡Atrápame!", "¡No me alcanzas!", "¡Jiji!"], otra=a.name()), 2)
        for p in (a, b):
            p.join_game()

    def update_game(self, now):
        g = self.game
        if not g:
            return
        a, b = g["chaser"], g["runner"]
        if a not in self.pets or b not in self.pets or "drag" in (a.state, b.state):
            self.end_game(quiet=True)
            return
        if now >= g["until"]:
            self.end_game()

    def caught(self):
        g = self.game
        g["rounds"] += 1
        a, b = g["chaser"], g["runner"]
        a.say(a.phrase("atrapa", ["¡Te atrapé!", "¡Tú las traes!", "¡Ja!"], otra=b.name()), 1.8)
        b.say(b.phrase("atrapada", ["¡Ay!", "¡No vale!", "¡Ahora verás!"], otra=a.name()), 1.8)
        if g["rounds"] >= g["max"]:
            self.end_game()
            return
        g["chaser"], g["runner"] = b, a                 # se cambian los papeles
        g["pause_until"] = time.perf_counter() + 1.2    # le da ventaja a la otra

    def end_game(self, quiet=False):
        g = self.game
        if not g:
            return
        self.game = None
        for p in (g["chaser"], g["runner"]):
            if p in self.pets:
                p.leave_game(quiet)

    # --- peleas amistosas ---
    def start_fight(self, a, b):
        if self.fight or self.game or a is b:
            return False
        for p in (a, b):
            if p.state in ("drag", "tp") or p.hidden or p not in self.pets:
                return False
        if math.hypot(a.x - b.x, a.y - b.y) > 1600:
            return False
        now = time.perf_counter()
        self.fight = {"a": a, "b": b, "turn": a, "exchanges": 0, "hits": {},
                      "max": random.randint(4, 7), "next": now + 1.0, "resolve_at": None,
                      "until": now + FIGHT_SECONDS_MAX, "reached": False}
        for p in (a, b):
            other = b if p is a else a
            p.mgrab = None
            p.chase_until = 0.0
            p.fight = False
            p.beam = None
            if p.state == "fly":                      # baja cerca de la otra
                p.fly_mode = "wander"
                side = 1 if p.x > other.x else -1
                p.fly_land = (other.surface if other.state not in ("air", "fly") else None,
                              other.x + side * FIGHT_DISTANCE)
            elif p.state == "climb":
                p.to_air(0)
            elif p.state != "air":
                p.join_fight()
        a.speak("pelea", ["¡En guardia!"], 2, otra=b.name())
        b.speak("pelea", ["¡Ven!"], 2, otra=a.name())
        keepers = [p for p in self.pets if p not in (a, b) and p.skin_cfg.get("pacificador")
                   and p.state in ("idle", "walk", "sit")]
        if keepers and random.random() < 0.35:        # alguien muy fuerte las separa
            self.fight["peacemaker"] = random.choice(keepers)
            self.fight["intervene_at"] = now + random.uniform(2.5, 4.5)
        return True

    # --- el mouse sale volando ---
    def fling_cursor(self, vx, vy):
        x, y = cursor_pos()
        self.flung = {"x": float(x), "y": float(y), "vx": vx, "vy": vy,
                      "until": time.perf_counter() + 0.7}

    def update_fling(self, dt):
        f = self.flung
        if not f:
            return
        if mouse_down() or time.perf_counter() >= f["until"]:
            self.flung = None
            return
        vs = (min(m[0] for m in self.monitors), min(m[1] for m in self.monitors),
              max(m[2] for m in self.monitors) - 2, max(m[3] for m in self.monitors) - 2)
        f["vy"] += 3000 * dt
        f["x"] += f["vx"] * dt
        f["y"] += f["vy"] * dt
        if f["x"] < vs[0] or f["x"] > vs[2]:
            f["vx"] = -f["vx"] * 0.5
            f["x"] = min(max(f["x"], vs[0]), vs[2])
        if f["y"] < vs[1] or f["y"] > vs[3]:
            f["vy"] = -f["vy"] * 0.4
            f["y"] = min(max(f["y"], vs[1]), vs[3])
        user32.SetCursorPos(int(f["x"]), int(f["y"]))

    def update_fight(self, now):
        f = self.fight
        if not f:
            return
        a, b = f["a"], f["b"]
        r = f.get("peacemaker")
        if r is not None and now >= f.get("intervene_at", 1e18):
            f["peacemaker"] = None
            if r in self.pets and r.state in ("idle", "walk", "sit", "oneshot", "chase"):
                r.intervene(a, b)
                return
        if a not in self.pets or b not in self.pets or "drag" in (a.state, b.state):
            self.end_fight(None)
        elif now >= f["until"]:
            self.end_fight(self.leader(f) if f["exchanges"] else None)
        elif f["resolve_at"] and now >= f["resolve_at"] and \
                a.state == "fight" and b.state == "fight":
            self.end_fight(self.leader(f))

    def leader(self, f):
        """Gana la que hizo más daño (golpes x poder; empate: la más fuerte)."""
        a, b = f["a"], f["b"]
        ha, hb = f["hits"].get(a, 0), f["hits"].get(b, 0)
        if ha == hb:
            if a.power() != b.power():
                return a if a.power() > b.power() else b
            return random.choice([a, b])
        return a if ha > hb else b

    def end_fight(self, winner):
        f = self.fight
        if not f:
            return
        self.fight = None
        a, b = f["a"], f["b"]
        for p in (a, b):
            if p not in self.pets:
                continue
            if winner is None:
                if p.state == "fight":
                    p.start_idle(random.uniform(1, 2))
                continue
            other = b if p is a else a
            res = "gana" if p is winner else "pierde"
            p.speak(res, ["¡Gané!"] if res == "gana" else ["Me ganaste..."], 2.5,
                    otra=other.name())
            if p.state == "fight":
                p.leave_fight(res)

    # --- sacudir ventanas (cuando les pega un rayo) ---
    def shake(self, hwnd):
        if any(s_["hwnd"] == hwnd for s_ in self.shakes):
            return
        self.shakes.append({"hwnd": hwnd, "t0": time.perf_counter(), "step": 0})

    def update_shakes(self, now):
        pattern = [10, -20, 16, -12, 8, -2]                # suma cero: regresa a su lugar
        keep = []
        for sh in self.shakes:
            while sh["step"] < len(pattern) and now >= sh["t0"] + 0.04 * sh["step"]:
                if window_ok(sh["hwnd"]):
                    move_window_by(sh["hwnd"], pattern[sh["step"]])
                sh["step"] += 1
            if sh["step"] < len(pattern):
                keep.append(sh)
        self.shakes = keep

    def quit(self):
        for b_ in self.beams + self.projectiles:
            b_.destroy()
        if self.treat:
            self.treat.destroy()
        if winmm:
            try:
                winmm.timeEndPeriod(1)
            except Exception:
                pass
        self.root.destroy()


# ---------- Inicio con Windows, una sola instancia y registro de errores ----------
AUTOSTART_NAME = "MascotasPC"


def launcher_command():
    """Comando para arrancar sin consola (pythonw + Mascotas.pyw si existe)."""
    exe = sys.executable
    folder, base = os.path.split(exe)
    if base.lower() == "python.exe" and os.path.exists(os.path.join(folder, "pythonw.exe")):
        exe = os.path.join(folder, "pythonw.exe")
    target = os.path.join(BASE_DIR, "Mascotas.pyw")
    if not os.path.exists(target):
        target = os.path.abspath(__file__)
    return '"%s" "%s"' % (exe, target)


def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            winreg.QueryValueEx(k, AUTOSTART_NAME)
            return True
    except Exception:
        return False


def set_autostart(on):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                            winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, AUTOSTART_NAME, 0, winreg.REG_SZ, launcher_command())
            else:
                try:
                    winreg.DeleteValue(k, AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception as e:
        print("Aviso:", e)
        return False


def already_running():
    """True si ya hay otra copia abierta (evita mascotas duplicadas)."""
    try:
        k32 = ctypes.windll.kernel32
        k32.CreateMutexW.restype = wintypes.HANDLE
        main.mutex = k32.CreateMutexW(None, False, "MascotasPC_una_sola_vez")
        return k32.GetLastError() == 183          # ERROR_ALREADY_EXISTS
    except Exception:
        return False


def show_error(text):
    try:
        ctypes.windll.user32.MessageBoxW(None, text, "Mascotas", 0x10)
    except Exception:
        print(text)


def setup_log():
    """Sin consola (pythonw) los avisos y errores van a mascotas.log."""
    if sys.stdout is None or sys.stderr is None:
        try:
            log = open(os.path.join(BASE_DIR, "mascotas.log"), "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stderr = log
            print("---", time.strftime("%Y-%m-%d %H:%M:%S"), "---")
        except Exception:
            pass


def main():
    setup_log()
    if "--ver-sheet" in sys.argv:
        i = sys.argv.index("--ver-sheet")
        show_sheet(sys.argv[i + 1] if len(sys.argv) > i + 1 else None)
        return
    if winmm:
        try:
            winmm.timeBeginPeriod(1)     # temporizador de 1 ms: movimiento más parejo
        except Exception:
            pass
    if already_running():
        show_error("Las mascotas ya están abiertas.")
        return
    root = tk.Tk()
    root.withdraw()                      # ventana base invisible; cada mascota tiene la suya
    try:
        App(root)
    except SystemExit as e:
        show_error(str(e))
        return
    except Exception:
        import traceback
        traceback.print_exc()
        show_error("Ocurrió un error al iniciar. Revisa mascotas.log.")
        return
    root.mainloop()


if __name__ == "__main__":
    main()
