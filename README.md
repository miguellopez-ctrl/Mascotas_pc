# Mascotas de escritorio

Mascotas que viven en tu escritorio de Windows: caminan, se suben a las ventanas, trepan, vuelan, duermen, se pelean entre ellas, te roban el mouse y te recuerdan tomar agua.

Hecho en Python con `tkinter` (no necesita instalar nada extra).

## Requisitos

- Windows 10 u 11.
- [Python 3.9 o más nuevo](https://www.python.org/downloads/). Al instalarlo, marca **"Add python.exe to PATH"**.

## Cómo abrirlas

1. Descarga el proyecto: botón verde **Code → Download ZIP** y descomprímelo (o clónalo con git).
2. Haz doble clic en **`Mascotas.pyw`**. Se abren sin ventana de consola.

La primera vez tarda unos segundos por cada personaje mientras procesa su imagen; después arranca en uno o dos segundos.

Si quieres ver los avisos en una consola, ábrelo con `python mascota_escritorio.py`. Sin consola, los errores se guardan en `mascotas.log`.

## Controles

- **Clic**: la acaricias.
- **Arrastrar**: la cargas; si la sueltas en movimiento, sale volando.
- **Clic derecho**: menú con todo:
  - Dormir, sentarse, saltar, jugar con el mouse, darle una galleta.
  - Habilidad especial y ¡Dispara!
  - **Mascotas**: agregar o quitar personajes, atrapadas, saludar, pelear.
  - Recordatorios (descansar la vista, agua…).
  - Tamaño y skin de cada una.
  - Interruptores: travesuras, pelear por el mouse, volar, **poderes pesados**.
  - **Iniciar con Windows**.

## Personajes

| Personaje | Poder | Dispara | Habilidades |
|---|---|---|---|
| Rem | 3 | Lucero del alba (bola con picos) | Limpiar, modo oni, lucero girando |
| Beatrice | 3 | Cristales | Volar, puerta (teletransporte) |
| Emilia | 3 | Carámbanos | Nieve, hielo, congela el mouse |
| Shaula | 5 | Rayo | Rayo a ventanas, súper salto |
| Echidna | 6 | Elementos | Fiesta de té, lectura, curiosear |
| Satella | 8 | Mano de sombra | Sombras, jala a otras y al mouse |
| Reinhard | 10 | Corte de espada | Bendición, minimiza ventanas, manda volando el mouse, separa peleas |

Cada personaje tiene su personalidad y sus relaciones con los demás (por ejemplo, Echidna odia a Emilia y a Satella; Rem no soporta a las brujas; todos le tienen respeto a Reinhard). Eso cambia con quién se pelean, a quién saludan y qué se dicen.

> **Poderes pesados**: Reinhard puede minimizar ventanas y lanzar tu mouse. Si estás trabajando, desactívalo en el menú.

## Agregar o editar personajes

Todo está en la carpeta `skins/`:

- `Nombre.png` — la hoja de sprites (PNG con transparencia o fondo liso).
- `Nombre.json` — su configuración (opcional).

Para ver cómo numera las poses una hoja nueva:

```
python mascota_escritorio.py --ver-sheet skins\Nombre.png
```

Campos principales del `.json`:

| Campo | Para qué |
|---|---|
| `personaje` | Nombre con el que la llaman las demás |
| `poder` | 1 a 10: quién gana, quién esquiva y qué tan lejos sale volando la otra |
| `velocidad` | Multiplicador de velocidad |
| `vuela` | `true` si puede volar |
| `disparo` | `lucero`, `cristal`, `hielo`, `rayo`, `bala`, `elementos`, `mano` o `corte` |
| `habilidades` | Lista: `limpiar`, `aura`, `nieve`, `cristales`, `congelar`, `teletransporte`, `rayo`, `super_salto`, `lucero`, `te`, `lectura`, `curiosear`, `sombra`, `manos`, `bendicion`, `minimizar`, `golpe_mouse` |
| `animaciones` | Qué poses usa cada estado: `[fila, pose]`, `[fila, desde, hasta]` o `["@", x, y]` |
| `frases` | Lo que dice en cada situación |
| `relaciones` | `{"Emilia": {"afinidad": -3, "frases": {...}}}`, de -3 (la odia) a 3 (la adora) |

## Créditos

Proyecto de fans sin fines de lucro. Los personajes pertenecen a *Re:ZERO -Starting Life in Another World-* (Tappei Nagatsuki / KADOKAWA) y las hojas de sprites a sus respectivos autores. El código es libre para usar y modificar.
