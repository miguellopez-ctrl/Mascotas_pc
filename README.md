# Mascotas de escritorio

Mascotas que viven en tu escritorio de Windows: caminan, se suben a las ventanas, trepan, vuelan, duermen, se pelean entre ellas (con corazones de vida y torneos), cocinan, se esconden, te roban el mouse y te recuerdan tomar agua.

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

- **Clic**: la acaricias (sube su cariño contigo).
- **Arrastrar**: la cargas; si la sueltas en movimiento, sale volando (Reinhard a veces la atrapa).
- **Ctrl + Alt + M**: esconde o muestra todas (botón de pánico).
- **Clic derecho**: menú con todo:
  - Dormir, sentarse, saltar, jugar con el mouse, darle una galleta.
  - Habilidad especial y ¡Dispara!
  - **Mascotas**: agregar o quitar personajes, atrapadas, saludar, pelear, **¡Torneo!** y **escondidas**.
  - Recordatorios, tamaño (todas a escala), skin, sonidos.
  - **Configuración...**: interruptores generales y qué habilidades tiene encendidas cada personaje.
  - **Estadísticas y logros...**
  - **Iniciar con Windows**.

## Tamaño: estatura del anime

Cada personaje mide lo que mide en la serie (`altura_cm` en su `.json`): Beatrice 140 cm, Rem 154, Echidna 162, Emilia y Satella 164, Shaula 170, Subaru 173, Reinhard 183. El tamaño del menú cambia a todas juntas sin perder la proporción.

## Personajes

| Personaje | Poder | Dispara | Habilidades |
|---|---|---|---|
| Rem | 3 | Lucero del alba | Limpiar, lucero girando, **cocina y le lleva un plato a quien más quiere**, **cura con agua**, **modo oni** (cuerno y aura; se activa sola si se acerca Satella) |
| Beatrice | 3 | Cristales | Vuela, teletransporte **con puertas dibujadas**, **lee arriba de una ventana** (si la despiertas: "¡Betty estaba leyendo, supongo!") |
| Emilia | 3 | Carámbanos | Nieve, congela el mouse, **congela una ventana** (escarcha que se derrite), **nevada en toda la pantalla**, **cura** |
| Shaula | 5 | Rayo | Rayo, súper salto, **forma de escorpión**, **sigue a su "maestro"** (Subaru o a quien más acaricias) |
| Echidna | 6 | Elementos | **Fiesta de té con mesa y tazas** (invita hasta a 3), lectura, curiosear, **trivia** |
| Satella | 8 | Mano de sombra | Vuela, sombras, **celos** (si acaricias a otra, le lanza manos), **oscurece la pantalla** susurrando "te amo..." |
| Reinhard | 10 | Corte de espada | Bendición, minimiza ventanas, lanza el mouse, separa peleas, **desvía disparos** contra sus amigos, **atrapa** a quien sale volando, **espada en serio** contra Satella |
| Subaru | 1 | Bolita de luz | **Regreso por muerte** (si se desmaya en una pelea, todo se oscurece y vuelve al inicio), **Shamak**, **mano invisible**, **¡Mi nombre es Natsuki Subaru!** |

Cada personaje tiene personalidad y relaciones con los demás (Rem y Satella adoran a Subaru, Beatrice es su compañera "Beako", Shaula le dice "maestro", Echidna odia a Emilia y a Satella, Subaru le tiene miedo a Satella...). Eso cambia con quién se pelean, a quién saludan, a quién invitan al té y qué se dicen.

## Sistemas

- **Vida y desmayos**: en las peleas cada una tiene 5 corazones; al acabarse se desmaya con estrellitas. Rem y Emilia van a curarla (o dale clic para ayudarla a levantarse).
- **Cariño**: cada caricia o galleta sube el cariño de ese personaje contigo y cambia lo que te dice.
- **Torneo**: eliminación directa con anuncios en pantalla y trofeo para la campeona.
- **Escondidas**: una se esconde detrás de una ventana; dale clic a esa ventana para encontrarla (cada rato da pistas con brillitos).
- **Día y noche**: de noche duermen más; en la mañana te saludan.
- **Logros y estadísticas** en su ventana.
- **Sonidos** (apagados al inicio): pon archivos `.wav` en la carpeta `sonidos/` con el nombre del evento (`ko`, `logro`, `torneo`, `regreso`, `encontrada`, `puerta`, `hielo`, `comer`, `caricia`).
- **Pantalla completa**: si abres un juego o video en pantalla completa, se esconden solas.

> **Poderes pesados**: Reinhard puede minimizar ventanas y lanzar tu mouse. Si estás trabajando, desactívalo en el menú o en Configuración.

## Agregar o editar personajes

Todo está en la carpeta `skins/`:

- `Nombre.png` — la hoja de sprites (PNG con transparencia o fondo liso, incluso el "transparente falso" de cuadritos).
- `Nombre.json` — su configuración (opcional).

Para ver cómo numera las poses una hoja nueva:

```
python mascota_escritorio.py --ver-sheet skins\Nombre.png
```

Campos principales del `.json`:

| Campo | Para qué |
|---|---|
| `personaje` | Nombre con el que la llaman las demás |
| `altura_cm` | Estatura (para el tamaño proporcional) |
| `poder` | 1 a 10: quién gana, quién esquiva y qué tan lejos sale volando la otra |
| `velocidad` | Multiplicador de velocidad |
| `vuela` | `true` si puede volar |
| `disparo` | `lucero`, `cristal`, `hielo`, `rayo`, `bala`, `elementos`, `mano`, `mano_inv` o `corte` |
| `habilidades` | Lista (ver la lista completa al inicio de `mascota_escritorio.py`) |
| `celosa`, `protector`, `puertas`, `sanadora` | Pasivas: celos, proteger/atrapar, dibujar puertas, curar |
| `animaciones` | Qué poses usa cada estado: `[fila, pose]`, `[fila, desde, hasta]`, `["@", x, y]` (la pose en ese punto de la imagen) o `["#", x0, y0, x1, y1]` (recorte manual) |
| `frases` | Lo que dice en cada situación |
| `relaciones` | `{"Emilia": {"afinidad": -3, "frases": {...}}}`, de -3 (la odia) a 3 (la adora) |

Las poses de trepar se limpian solas: si la hoja dibuja un poste o pared, se quita (la ventana ya hace de pared).

## Créditos

Proyecto de fans sin fines de lucro. Los personajes pertenecen a *Re:ZERO -Starting Life in Another World-* (Tappei Nagatsuki / KADOKAWA) y las hojas de sprites a sus respectivos autores. El código es libre para usar y modificar.
