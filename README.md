# Physics Ball Race

A Plinko-style idle game where colored balls compete for the highest score by bouncing through a field of pegs and falling into scored buckets at the bottom. Watch the chaos unfold as 18 different colors fight for survival — the lowest scorer gets eliminated, and the game cycles to a new level. Last color standing wins.

## Requirements

- Python 3.8+
- [pygame](https://www.pygame.org/) — `pip install pygame`
- [pymunk](http://www.pymunk.org/) — `pip install pymunk`
- [Pillow](https://python-pillow.org/) — `pip install Pillow` (required for image import in the level editor)

## Running the Game

```bash
python main.py
```

To load a specific level directly:

```bash
python main.py my_level.json
```

## How It Works

Balls of 18 different colors spawn at the top of the maze and bounce through pegs and platforms before landing in scoring buckets at the bottom. Each bucket has a point value — some buckets add score, and two special `+1` buckets spawn an extra ball for the lucky color.

After a set number of balls have scored, the **color with the lowest total score is eliminated** — all its balls are removed. The game then loads the next level in the sequence and play continues. This repeats until only one color remains: the winner.

Wins are saved to `wins.json` and persist between sessions.

## Ball Types

There are 18 ball types — 8 standard colors, 8 sparkly variants of those colors (with animated orbit sparkles and glowing trails), plus two special types:

| Type | Description |
|------|-------------|
| **Rainbow** | Cycles through the full color spectrum over time. Sparkly. |
| **B&W** | Oscillates between black and white. |

## Controls

| Key / Action | Effect |
|---|---|
| Left click on maze | Add a ball of the selected type |
| `1` – `8` | Select ball type (cycles through types) |
| `Space` | Add a wave of balls (one per active color) |
| `R` | Reset all scores and restart from level 1 |
| `+` / `-` | Increase / decrease simulation speed |
| `F11` | Toggle fullscreen |
| `H` (hold) | Show all-time win counts from `wins.json` |

## Level Sequence

Levels are played in order as defined in `level_sequence.json`. When the sequence ends it wraps back to the beginning. Each level is a JSON file describing the maze boundaries, pegs, platforms, walls, and scoring buckets.

```json
{
  "levels": ["level.json", "level02.json", "level03.json"]
}
```

---

## Level Editor

```bash
python level_editor.py
```

A full visual drag-and-drop editor for creating and editing level files.

### Tools

| Key | Tool | Description |
|-----|------|-------------|
| `V` | Select | Click or drag to select and move objects. Drag endpoints to reshape platforms/walls. |
| `P` | Peg | Click or drag-paint to place circular pegs. |
| `L` | Platform | Click two points to draw an angled platform. |
| `W` | Wall | Click two points to draw a wall segment. |
| `B` | Bucket | Drag the dividers between buckets to resize them. Right-click to insert new buckets. |
| `E` | Eraser | Click or drag to delete objects. |

### Editor Shortcuts

| Key / Action | Effect |
|---|---|
| `Ctrl+S` | Save level |
| `Ctrl+O` | Load level |
| `Ctrl+N` | New level |
| `Ctrl+Z` | Undo |
| `Ctrl+G` | Generate a default peg grid |
| `G` | Toggle grid snapping |
| `F5` | Preview the level in the game |
| `Delete` | Delete selected object |

### Importing Images

Click the **Image** button in the toolbar to import any PNG, JPG, BMP, or GIF as a level.

The editor will:
1. Resize the image to fit the maze area
2. Detect edges using image processing and convert them into **platforms**
3. Fill dark interior regions with a staggered grid of **pegs**

This gives you a fast starting point for any shape or silhouette you want to build a level around. After importing, you can continue editing with all the normal tools — add or remove pegs, adjust platforms, and tweak the buckets before saving.

### Level JSON Format

```json
{
  "version": 1,
  "name": "My Level",
  "maze": {
    "width": 860, "height": 1000,
    "maze_top": 80, "maze_bottom": 940,
    "maze_left": 50, "maze_right": 600
  },
  "walls":     [ { "x1": 50, "y1": 80, "x2": 50, "y2": 940, "thickness": 6, "elasticity": 0.5, "friction": 0.4 } ],
  "platforms": [ { "x1": 100, "y1": 200, "x2": 250, "y2": 220, "thickness": 4, "elasticity": 0.4, "friction": 0.5 } ],
  "pegs":      [ { "x": 150.0, "y": 300.0, "radius": 5, "elasticity": 0.6, "friction": 0.3 } ],
  "buckets": {
    "height": 45,
    "entries": [
      { "width_fraction": 0.111, "score": 10, "label": "10" }
    ]
  },
  "spawn":      { "y_offset": 15, "x_spread": 120 },
  "gravity":    [0, 900],
  "ball_radius": 8,
  "ball_limit":  160
}
```
