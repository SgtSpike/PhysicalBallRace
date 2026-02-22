"""
Level Editor for Physics Ball Race
-----------------------------------
Visual drag-and-drop editor for creating and editing level JSON files.

Controls:
  V - Select tool       P - Peg tool        L - Platform tool
  W - Wall tool         B - Bucket tool      E - Eraser tool
  G - Toggle grid snap  Delete - Remove selected
  Ctrl+S - Save         Ctrl+O - Load        Ctrl+N - New level
  Ctrl+Z - Undo         Ctrl+G - Generate peg grid
  F5 - Preview level    Escape - Cancel/deselect
"""

import pygame
import json
import os
import sys
import math
import copy
import subprocess

# --- Constants ---
EDITOR_WIDTH, EDITOR_HEIGHT = 800, 1040
TOOLBAR_HEIGHT = 40
STATUS_HEIGHT = 25
PANEL_LEFT = 620
GRID_DEFAULT = 10

# Colors
C_BG = (20, 20, 30)
C_GRID = (32, 32, 42)
C_MAZE_BG = (25, 25, 38)
C_MAZE_BORDER = (60, 60, 80)
C_PEG = (160, 160, 180)
C_PEG_HI = (200, 200, 210)
C_PLATFORM = (130, 130, 150)
C_WALL = (100, 100, 120)
C_SELECTED = (255, 255, 0)
C_GHOST = (255, 255, 255)
C_PANEL_BG = (30, 30, 45)
C_PANEL_BORDER = (80, 80, 100)
C_BTN = (50, 50, 70)
C_BTN_HOVER = (70, 70, 95)
C_BTN_ACTIVE = (90, 70, 120)
C_TEXT = (200, 200, 220)
C_TEXT_DIM = (140, 140, 160)
C_INPUT_BG = (40, 40, 58)
C_INPUT_ACTIVE = (60, 60, 90)
C_INPUT_BORDER = (100, 100, 130)
C_TOOLBAR_BG = (25, 25, 38)
C_STATUS_BG = (25, 25, 40)

TOOL_SELECT = "select"
TOOL_PEG = "peg"
TOOL_PLATFORM = "platform"
TOOL_WALL = "wall"
TOOL_BUCKET = "bucket"
TOOL_ERASER = "eraser"

TOOL_KEYS = {
    pygame.K_v: TOOL_SELECT,
    pygame.K_p: TOOL_PEG,
    pygame.K_l: TOOL_PLATFORM,
    pygame.K_w: TOOL_WALL,
    pygame.K_b: TOOL_BUCKET,
    pygame.K_e: TOOL_ERASER,
}

TOOL_NAMES = {
    TOOL_SELECT: "[V] Select",
    TOOL_PEG: "[P] Peg",
    TOOL_PLATFORM: "[L] Platform",
    TOOL_WALL: "[W] Wall",
    TOOL_BUCKET: "[B] Bucket",
    TOOL_ERASER: "[E] Eraser",
}


def point_to_segment_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def get_default_level():
    """Generate the default level matching main.py's hardcoded layout."""
    ML, MT, MR, MB = 50, 80, 600, 940
    BH = 45

    platform_defs = [
        ((ML + 20, MT + 100), (ML + 120, MT + 115)),
        ((MR - 120, MT + 100), (MR - 20, MT + 85)),
        ((ML + 60, MT + 220), (ML + 180, MT + 205)),
        ((MR - 180, MT + 220), (MR - 60, MT + 235)),
        ((ML, MT + 340), (ML + 140, MT + 355)),
        ((MR - 140, MT + 340), (MR, MT + 325)),
        ((ML, MT + 520), (ML + 160, MT + 535)),
        ((MR - 160, MT + 520), (MR, MT + 505)),
    ]

    blocked_pegs = [(461, 194), (189, 268), (243, 268)]

    platforms = [{"x1": p1[0], "y1": p1[1], "x2": p2[0], "y2": p2[1],
                  "thickness": 4, "elasticity": 0.4, "friction": 0.5}
                 for p1, p2 in platform_defs]

    walls = [
        {"x1": ML, "y1": MT, "x2": ML, "y2": MB, "thickness": 6, "elasticity": 0.5, "friction": 0.4},
        {"x1": MR, "y1": MT, "x2": MR, "y2": MB, "thickness": 6, "elasticity": 0.5, "friction": 0.4},
    ]

    # Generate pegs
    pegs = []
    rows, cols = 14, 10
    usable_width = MR - ML - 60
    h_spacing = usable_width / (cols - 1)
    v_spacing = (MB - MT - 80) / (rows - 1)
    bucket_top = MB - BH

    for row in range(rows):
        offset = h_spacing / 2 if row % 2 == 1 else 0
        num_cols = cols - 1 if row % 2 == 1 else cols
        y = MT + 40 + row * v_spacing
        for col in range(num_cols):
            x = ML + 30 + col * h_spacing + offset
            if y >= bucket_top - 15:
                continue
            too_close = any(
                point_to_segment_dist(x, y, p1[0], p1[1], p2[0], p2[1]) < 20
                for p1, p2 in platform_defs
            )
            if too_close:
                continue
            blocked = any(math.hypot(x - bx, y - by) < 8 for bx, by in blocked_pegs)
            if blocked:
                continue
            pegs.append({"x": round(x, 1), "y": round(y, 1), "radius": 5,
                         "elasticity": 0.6, "friction": 0.3})

    scores = [0, 10, 5, 3, 1, 3, 5, 10, 0]
    labels = ["+1", "10", "5", "3", "1", "3", "5", "10", "+1"]
    frac = round(1.0 / len(scores), 4)
    entries = [{"width_fraction": frac, "score": s, "label": l} for s, l in zip(scores, labels)]

    return {
        "version": 1, "name": "Default Level",
        "maze": {"width": 800, "height": 1000, "maze_top": MT, "maze_bottom": MB,
                 "maze_left": ML, "maze_right": MR},
        "walls": walls, "platforms": platforms, "pegs": pegs,
        "buckets": {"height": BH, "entries": entries},
        "spawn": {"y_offset": 15, "x_spread": 120},
        "gravity": [0, 900], "ball_radius": 8, "ball_limit": 160,
    }


class TextInput:
    """Simple inline text input field."""
    def __init__(self, x, y, w, h, value, label, numeric=True):
        self.rect = pygame.Rect(x, y, w, h)
        self.value = str(value)
        self.label = label
        self.active = False
        self.numeric = numeric
        self.cursor_blink = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
            return self.active
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN or event.key == pygame.K_TAB:
                self.active = False
                return True
            elif event.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
                return True
            elif event.key == pygame.K_ESCAPE:
                self.active = False
                return True
            else:
                ch = event.unicode
                if ch and (not self.numeric or ch in "0123456789.-+"):
                    self.value += ch
                    return True
        return False

    def draw(self, surface, font):
        # Label
        lbl = font.render(self.label + ":", True, C_TEXT_DIM)
        surface.blit(lbl, (self.rect.x, self.rect.y - 16))
        # Box
        bg = C_INPUT_ACTIVE if self.active else C_INPUT_BG
        pygame.draw.rect(surface, bg, self.rect)
        border = C_SELECTED if self.active else C_INPUT_BORDER
        pygame.draw.rect(surface, border, self.rect, 1)
        # Text
        txt = font.render(self.value, True, C_TEXT)
        surface.blit(txt, (self.rect.x + 4, self.rect.y + 3))
        # Cursor
        if self.active:
            self.cursor_blink = (self.cursor_blink + 1) % 60
            if self.cursor_blink < 30:
                cx = self.rect.x + 4 + txt.get_width()
                pygame.draw.line(surface, C_TEXT, (cx, self.rect.y + 3), (cx, self.rect.y + self.rect.h - 3))

    def get_float(self, default=0.0):
        try:
            return float(self.value)
        except ValueError:
            return default

    def get_int(self, default=0):
        try:
            return int(float(self.value))
        except ValueError:
            return default

    def get_str(self):
        return self.value


class Editor:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((EDITOR_WIDTH, EDITOR_HEIGHT))
        pygame.display.set_caption("Level Editor - Physics Ball Race")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 13)
        self.bold_font = pygame.font.SysFont("consolas", 13, bold=True)
        self.title_font = pygame.font.SysFont("consolas", 15, bold=True)

        self.level = get_default_level()
        self.tool = TOOL_SELECT
        self.selected = None  # (type, index) e.g. ("peg", 5)
        self.grid_size = GRID_DEFAULT
        self.snap = True
        self.status_text = "Ready - Select a tool to begin"

        # Placement state
        self.placing_start = None
        self.dragging = False
        self.drag_what = None  # "object", "endpoint1", "endpoint2", "divider"
        self.drag_divider_idx = -1
        self.mouse_down = False

        # Properties panel inputs
        self.inputs = []

        # Undo
        self.undo_stack = []
        self.max_undo = 50

        # File
        self.current_file = None
        self.dir = os.path.dirname(os.path.abspath(__file__))

    def push_undo(self):
        self.undo_stack.append(copy.deepcopy(self.level))
        if len(self.undo_stack) > self.max_undo:
            self.undo_stack.pop(0)

    def undo(self):
        if self.undo_stack:
            self.level = self.undo_stack.pop()
            self.selected = None
            self.inputs = []
            self.status_text = "Undo"

    def snap_pos(self, x, y):
        if self.snap and self.grid_size > 0:
            return (round(x / self.grid_size) * self.grid_size,
                    round(y / self.grid_size) * self.grid_size)
        return (x, y)

    def maze(self):
        return self.level["maze"]

    def in_canvas(self, pos):
        return pos[0] < PANEL_LEFT and TOOLBAR_HEIGHT < pos[1] < EDITOR_HEIGHT - STATUS_HEIGHT

    # --- Hit testing ---

    def hit_test(self, mx, my):
        best = None
        best_dist = 12

        for i, peg in enumerate(self.level["pegs"]):
            d = math.hypot(mx - peg["x"], my - peg["y"])
            if d < best_dist:
                best_dist = d
                best = ("peg", i)

        for i, plat in enumerate(self.level["platforms"]):
            d = point_to_segment_dist(mx, my, plat["x1"], plat["y1"], plat["x2"], plat["y2"])
            if d < best_dist:
                best_dist = d
                best = ("platform", i)

        for i, wall in enumerate(self.level["walls"]):
            d = point_to_segment_dist(mx, my, wall["x1"], wall["y1"], wall["x2"], wall["y2"])
            if d < best_dist:
                best_dist = d
                best = ("wall", i)

        return best

    def hit_test_bucket(self, mx, my):
        """Return bucket index if click is in bucket zone, else -1."""
        m = self.maze()
        bh = self.level["buckets"]["height"]
        bucket_top = m["maze_bottom"] - bh
        if not (bucket_top <= my <= m["maze_bottom"] and m["maze_left"] <= mx <= m["maze_right"]):
            return -1
        total_w = m["maze_right"] - m["maze_left"]
        x = m["maze_left"]
        for i, entry in enumerate(self.level["buckets"]["entries"]):
            w = entry["width_fraction"] * total_w
            if x <= mx <= x + w:
                return i
            x += w
        return -1

    def hit_test_divider(self, mx, my):
        """Return divider index (between bucket i and i+1) if near a divider, else -1."""
        m = self.maze()
        bh = self.level["buckets"]["height"]
        bucket_top = m["maze_bottom"] - bh
        if not (bucket_top - 12 <= my <= m["maze_bottom"] + 5):
            return -1
        total_w = m["maze_right"] - m["maze_left"]
        x = m["maze_left"]
        entries = self.level["buckets"]["entries"]
        for i in range(len(entries) - 1):
            x += entries[i]["width_fraction"] * total_w
            if abs(mx - x) < 8:
                return i

        return -1

    def endpoint_near(self, mx, my, seg):
        """Check if click is near an endpoint. Returns 1, 2, or 0."""
        d1 = math.hypot(mx - seg["x1"], my - seg["y1"])
        d2 = math.hypot(mx - seg["x2"], my - seg["y2"])
        if d1 < 12:
            return 1
        if d2 < 12:
            return 2
        return 0

    # --- Object manipulation ---

    def delete_selected(self):
        if not self.selected:
            return
        self.push_undo()
        obj_type, idx = self.selected
        if obj_type == "peg" and idx < len(self.level["pegs"]):
            self.level["pegs"].pop(idx)
        elif obj_type == "platform" and idx < len(self.level["platforms"]):
            self.level["platforms"].pop(idx)
        elif obj_type == "wall" and idx < len(self.level["walls"]):
            self.level["walls"].pop(idx)
        elif obj_type == "bucket":
            entries = self.level["buckets"]["entries"]
            if len(entries) > 2 and idx < len(entries):
                removed_frac = entries[idx]["width_fraction"]
                entries.pop(idx)
                # Redistribute removed width
                for e in entries:
                    e["width_fraction"] += removed_frac / len(entries)
                self.normalize_buckets()
        self.selected = None
        self.inputs = []
        self.status_text = "Deleted"

    def normalize_buckets(self):
        entries = self.level["buckets"]["entries"]
        total = sum(e["width_fraction"] for e in entries)
        if total > 0:
            for e in entries:
                e["width_fraction"] /= total

    # --- Properties panel ---

    def build_inputs(self):
        """Build text input fields for the selected object."""
        self.inputs = []
        if not self.selected:
            return

        obj_type, idx = self.selected
        px = PANEL_LEFT + 10
        y = 345

        if obj_type == "peg" and idx < len(self.level["pegs"]):
            peg = self.level["pegs"][idx]
            self.inputs.append(TextInput(px, y, 70, 20, round(peg["x"], 1), "X"))
            self.inputs.append(TextInput(px + 80, y, 70, 20, round(peg["y"], 1), "Y"))
            y += 40
            self.inputs.append(TextInput(px, y, 70, 20, peg["radius"], "Radius"))
            y += 40
            self.inputs.append(TextInput(px, y, 70, 20, peg["elasticity"], "Elastic"))
            self.inputs.append(TextInput(px + 80, y, 70, 20, peg["friction"], "Friction"))

        elif obj_type in ("platform", "wall"):
            lst = self.level["platforms"] if obj_type == "platform" else self.level["walls"]
            if idx < len(lst):
                seg = lst[idx]
                self.inputs.append(TextInput(px, y, 70, 20, round(seg["x1"], 1), "X1"))
                self.inputs.append(TextInput(px + 80, y, 70, 20, round(seg["y1"], 1), "Y1"))
                y += 40
                self.inputs.append(TextInput(px, y, 70, 20, round(seg["x2"], 1), "X2"))
                self.inputs.append(TextInput(px + 80, y, 70, 20, round(seg["y2"], 1), "Y2"))
                y += 40
                self.inputs.append(TextInput(px, y, 70, 20, seg["thickness"], "Thick"))
                y += 40
                self.inputs.append(TextInput(px, y, 70, 20, seg["elasticity"], "Elastic"))
                self.inputs.append(TextInput(px + 80, y, 70, 20, seg["friction"], "Friction"))

        elif obj_type == "bucket":
            entries = self.level["buckets"]["entries"]
            if idx < len(entries):
                entry = entries[idx]
                self.inputs.append(TextInput(px, y, 70, 20, entry["score"], "Score"))
                y += 40
                self.inputs.append(TextInput(px, y, 100, 20, entry["label"], "Label", numeric=False))
                y += 40
                self.inputs.append(TextInput(px, y, 70, 20, round(entry["width_fraction"] * 100, 1), "Width%"))

    def apply_inputs(self):
        """Apply text input values back to the level data."""
        if not self.selected or not self.inputs:
            return
        obj_type, idx = self.selected

        if obj_type == "peg" and idx < len(self.level["pegs"]):
            peg = self.level["pegs"][idx]
            if len(self.inputs) >= 5:
                peg["x"] = self.inputs[0].get_float(peg["x"])
                peg["y"] = self.inputs[1].get_float(peg["y"])
                peg["radius"] = self.inputs[2].get_int(peg["radius"])
                peg["elasticity"] = self.inputs[3].get_float(peg["elasticity"])
                peg["friction"] = self.inputs[4].get_float(peg["friction"])

        elif obj_type in ("platform", "wall"):
            lst = self.level["platforms"] if obj_type == "platform" else self.level["walls"]
            if idx < len(lst) and len(self.inputs) >= 7:
                seg = lst[idx]
                seg["x1"] = self.inputs[0].get_float(seg["x1"])
                seg["y1"] = self.inputs[1].get_float(seg["y1"])
                seg["x2"] = self.inputs[2].get_float(seg["x2"])
                seg["y2"] = self.inputs[3].get_float(seg["y2"])
                seg["thickness"] = self.inputs[4].get_int(seg["thickness"])
                seg["elasticity"] = self.inputs[5].get_float(seg["elasticity"])
                seg["friction"] = self.inputs[6].get_float(seg["friction"])

        elif obj_type == "bucket":
            entries = self.level["buckets"]["entries"]
            if idx < len(entries) and len(self.inputs) >= 3:
                entries[idx]["score"] = self.inputs[0].get_int(entries[idx]["score"])
                entries[idx]["label"] = self.inputs[1].get_str()
                new_pct = self.inputs[2].get_float(entries[idx]["width_fraction"] * 100)
                entries[idx]["width_fraction"] = max(0.03, new_pct / 100)
                self.normalize_buckets()

    # --- File operations ---

    def open_save_dialog(self):
        """Open save dialog with level name and filename inputs."""
        self.show_save_dialog = True
        # Pre-fill from current level name and file
        current_name = self.level.get("name", "My Level")
        if self.current_file:
            current_fname = os.path.basename(self.current_file)
        else:
            # Derive filename from level name
            safe_name = current_name.lower().replace(" ", "_")
            current_fname = f"{safe_name}.json"
        bw = 380
        bx = (EDITOR_WIDTH - bw) // 2
        by = (EDITOR_HEIGHT - 220) // 2
        self.save_name_input = TextInput(bx + 20, by + 65, bw - 40, 22, current_name, "Level Name", numeric=False)
        self.save_file_input = TextInput(bx + 20, by + 125, bw - 40, 22, current_fname, "Filename", numeric=False)

    def do_save(self):
        """Execute the save using values from the save dialog."""
        level_name = self.save_name_input.get_str().strip() or "My Level"
        filename = self.save_file_input.get_str().strip()
        if not filename:
            filename = "level.json"
        if not filename.endswith(".json"):
            filename += ".json"
        self.level["name"] = level_name
        filepath = os.path.join(self.dir, filename)
        with open(filepath, "w") as f:
            json.dump(self.level, f, indent=2)
        self.current_file = filepath
        self.show_save_dialog = False
        self.status_text = f"Saved: {filename}"

    def save_level(self, filepath=None):
        if filepath is None:
            self.open_save_dialog()
            return
        self.level["name"] = os.path.splitext(os.path.basename(filepath))[0]
        with open(filepath, "w") as f:
            json.dump(self.level, f, indent=2)
        self.current_file = filepath
        self.status_text = f"Saved: {os.path.basename(filepath)}"

    def load_level_file(self, filepath=None):
        if filepath is None:
            filepath = os.path.join(self.dir, "level.json")
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                self.level = json.load(f)
            self.current_file = filepath
            self.selected = None
            self.inputs = []
            self.undo_stack.clear()
            self.status_text = f"Loaded: {os.path.basename(filepath)}"
            return True
        self.status_text = f"File not found: {filepath}"
        return False

    def list_json_files(self):
        return sorted(f for f in os.listdir(self.dir) if f.endswith(".json") and f != "wins.json")

    def preview(self):
        preview_path = os.path.join(self.dir, "_preview_level.json")
        with open(preview_path, "w") as f:
            json.dump(self.level, f, indent=2)
        subprocess.Popen([sys.executable, os.path.join(self.dir, "main.py"), preview_path])
        self.status_text = "Preview launched"

    def generate_peg_grid(self):
        """Re-generate the default peg grid, replacing all existing pegs."""
        self.push_undo()
        self.level["pegs"] = get_default_level()["pegs"]
        self.selected = None
        self.inputs = []
        self.status_text = "Peg grid regenerated"

    # --- Event handling ---

    def handle_event(self, event):
        # Let active text inputs consume keys first
        for inp in self.inputs:
            if inp.active and event.type == pygame.KEYDOWN:
                if inp.handle_event(event):
                    self.apply_inputs()
                    return

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Click on text inputs
            for inp in self.inputs:
                if inp.rect.collidepoint(event.pos):
                    for other in self.inputs:
                        other.active = False
                    inp.active = True
                    return

            # Deactivate all inputs on click elsewhere
            for inp in self.inputs:
                inp.active = False
            self.apply_inputs()

            # Tool buttons in panel
            if event.pos[0] >= PANEL_LEFT:
                self.handle_panel_click(event.pos)
                return

            # Toolbar buttons
            if event.pos[1] < TOOLBAR_HEIGHT:
                self.handle_toolbar_click(event.pos)
                return

            # Canvas
            if self.in_canvas(event.pos):
                self.handle_canvas_click(event.pos, event.button)

        elif event.type == pygame.MOUSEBUTTONUP:
            if self.dragging:
                self.dragging = False
                self.drag_what = None
            self.mouse_down = False

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging and self.in_canvas(event.pos):
                self.handle_canvas_drag(event.pos)
            elif self.mouse_down and self.tool == TOOL_PEG and self.in_canvas(event.pos):
                # Paint pegs while dragging
                sx, sy = self.snap_pos(event.pos[0], event.pos[1])
                # Only place if not too close to existing peg
                too_close = any(math.hypot(sx - p["x"], sy - p["y"]) < self.grid_size * 0.8
                                for p in self.level["pegs"])
                if not too_close:
                    self.level["pegs"].append({"x": sx, "y": sy, "radius": 5,
                                               "elasticity": 0.6, "friction": 0.3})
            elif self.mouse_down and self.tool == TOOL_ERASER and self.in_canvas(event.pos):
                # Erase pegs while dragging
                mx, my = event.pos
                to_remove = []
                for i, peg in enumerate(self.level["pegs"]):
                    if math.hypot(mx - peg["x"], my - peg["y"]) < 10:
                        to_remove.append(i)
                for i in reversed(to_remove):
                    self.level["pegs"].pop(i)

        elif event.type == pygame.KEYDOWN:
            self.handle_key(event)

    def handle_toolbar_click(self, pos):
        x = pos[0]
        # Toolbar buttons: Save(0-60), Load(65-125), New(130-185), Preview(190-260), Grid(265-340)
        if x < 60:
            self.save_level()
        elif x < 125:
            self.show_file_browser = True
            self.file_browser_files = self.list_json_files()
            self.file_browser_scroll = 0
            self.status_text = "Click a file to load, or press Escape"
        elif x < 185:
            self.push_undo()
            self.level = get_default_level()
            self.selected = None
            self.inputs = []
            self.current_file = None
            self.status_text = "New level created"
        elif x < 260:
            self.preview()
        elif x < 340:
            self.snap = not self.snap
            self.status_text = f"Grid snap: {'ON' if self.snap else 'OFF'}"

    def handle_panel_click(self, pos):
        y = pos[1]
        # Tool buttons start at y=72 (TOOLBAR_HEIGHT+10+22)
        tool_list = [TOOL_SELECT, TOOL_PEG, TOOL_PLATFORM, TOOL_WALL, TOOL_BUCKET, TOOL_ERASER]
        for i, tool in enumerate(tool_list):
            btn_y = 72 + i * 30
            if btn_y <= y <= btn_y + 24:
                self.tool = tool
                self.placing_start = None
                self.status_text = f"Tool: {TOOL_NAMES[tool]}"
                return

        # Delete button at y=267
        if 267 <= y <= 291 and self.selected:
            self.delete_selected()
            return

        # Bucket insert/delete buttons
        if self.selected and self.selected[0] == "bucket":
            entries = self.level["buckets"]["entries"]
            idx = self.selected[1]
            input_bottom = 345 + 120  # approx where inputs end
            if input_bottom <= y <= input_bottom + 24 and len(entries) < 15:
                # Insert bucket left
                self.push_undo()
                new_frac = entries[idx]["width_fraction"] / 2
                entries[idx]["width_fraction"] = new_frac
                entries.insert(idx, {"width_fraction": new_frac, "score": 1, "label": "1"})
                self.normalize_buckets()
                self.selected = ("bucket", idx)
                self.build_inputs()
                self.status_text = "Bucket inserted"
                return
            if input_bottom + 28 <= y <= input_bottom + 52 and len(entries) < 15:
                # Insert bucket right
                self.push_undo()
                new_frac = entries[idx]["width_fraction"] / 2
                entries[idx]["width_fraction"] = new_frac
                entries.insert(idx + 1, {"width_fraction": new_frac, "score": 1, "label": "1"})
                self.normalize_buckets()
                self.selected = ("bucket", idx)
                self.build_inputs()
                self.status_text = "Bucket inserted"
                return

    def handle_canvas_click(self, pos, button):
        mx, my = pos
        sx, sy = self.snap_pos(mx, my)

        if self.tool == TOOL_SELECT:
            if button == 1:
                # Check bucket zone first if in bucket tool area
                hit = self.hit_test(mx, my)
                if hit:
                    self.selected = hit
                    self.build_inputs()
                    self.dragging = True
                    obj_type, idx = hit
                    if obj_type in ("platform", "wall"):
                        lst = self.level["platforms"] if obj_type == "platform" else self.level["walls"]
                        seg = lst[idx]
                        ep = self.endpoint_near(mx, my, seg)
                        if ep == 1:
                            self.drag_what = "endpoint1"
                        elif ep == 2:
                            self.drag_what = "endpoint2"
                        else:
                            self.drag_what = "object"
                    else:
                        self.drag_what = "object"
                    self.push_undo()
                    self.status_text = f"Selected {obj_type} #{idx}"
                else:
                    self.selected = None
                    self.inputs = []

        elif self.tool == TOOL_PEG:
            if button == 1:
                self.push_undo()
                self.level["pegs"].append({"x": sx, "y": sy, "radius": 5,
                                           "elasticity": 0.6, "friction": 0.3})
                self.mouse_down = True
                self.status_text = f"Peg placed at ({sx}, {sy})"

        elif self.tool == TOOL_PLATFORM:
            if button == 1:
                if self.placing_start is None:
                    self.placing_start = (sx, sy)
                    self.status_text = "Click to set endpoint"
                else:
                    self.push_undo()
                    self.level["platforms"].append({
                        "x1": self.placing_start[0], "y1": self.placing_start[1],
                        "x2": sx, "y2": sy,
                        "thickness": 4, "elasticity": 0.4, "friction": 0.5,
                    })
                    self.placing_start = None
                    self.status_text = "Platform placed"

        elif self.tool == TOOL_WALL:
            if button == 1:
                if self.placing_start is None:
                    self.placing_start = (sx, sy)
                    self.status_text = "Click to set endpoint"
                else:
                    self.push_undo()
                    self.level["walls"].append({
                        "x1": self.placing_start[0], "y1": self.placing_start[1],
                        "x2": sx, "y2": sy,
                        "thickness": 6, "elasticity": 0.5, "friction": 0.4,
                    })
                    self.placing_start = None
                    self.status_text = "Wall placed"

        elif self.tool == TOOL_BUCKET:
            if button == 1:
                # Check divider drag
                div = self.hit_test_divider(mx, my)
                if div >= 0:
                    self.dragging = True
                    self.drag_what = "divider"
                    self.drag_divider_idx = div
                    self.push_undo()
                    return
                # Check bucket selection
                bi = self.hit_test_bucket(mx, my)
                if bi >= 0:
                    self.selected = ("bucket", bi)
                    self.build_inputs()
                    self.status_text = f"Bucket #{bi} selected"
                else:
                    self.selected = None
                    self.inputs = []
            elif button == 3:
                # Right-click for insert context
                bi = self.hit_test_bucket(mx, my)
                if bi >= 0:
                    self.selected = ("bucket", bi)
                    self.build_inputs()

        elif self.tool == TOOL_ERASER:
            if button == 1:
                self.push_undo()
                hit = self.hit_test(mx, my)
                if hit:
                    obj_type, idx = hit
                    if obj_type == "peg":
                        self.level["pegs"].pop(idx)
                    elif obj_type == "platform":
                        self.level["platforms"].pop(idx)
                    elif obj_type == "wall":
                        self.level["walls"].pop(idx)
                    self.status_text = f"Erased {obj_type}"
                self.mouse_down = True

    def handle_canvas_drag(self, pos):
        mx, my = pos
        sx, sy = self.snap_pos(mx, my)

        if not self.selected and self.drag_what != "divider":
            return

        if self.drag_what == "divider":
            # Drag bucket divider
            entries = self.level["buckets"]["entries"]
            m = self.maze()
            total_w = m["maze_right"] - m["maze_left"]
            di = self.drag_divider_idx
            if 0 <= di < len(entries) - 1:
                # Compute new divider position as fraction
                new_x_frac = (mx - m["maze_left"]) / total_w
                # Sum of fractions up to divider
                sum_before = sum(entries[j]["width_fraction"] for j in range(di))
                sum_after_both = sum(entries[j]["width_fraction"] for j in range(di + 2))
                new_left_frac = max(0.03, min(sum_after_both - 0.03, new_x_frac - sum_before))
                new_right_frac = sum_after_both - sum_before - new_left_frac
                if new_right_frac >= 0.03:
                    entries[di]["width_fraction"] = new_left_frac
                    entries[di + 1]["width_fraction"] = new_right_frac
            return

        obj_type, idx = self.selected

        if obj_type == "peg" and idx < len(self.level["pegs"]):
            self.level["pegs"][idx]["x"] = sx
            self.level["pegs"][idx]["y"] = sy

        elif obj_type in ("platform", "wall"):
            lst = self.level["platforms"] if obj_type == "platform" else self.level["walls"]
            if idx < len(lst):
                seg = lst[idx]
                if self.drag_what == "endpoint1":
                    seg["x1"] = sx
                    seg["y1"] = sy
                elif self.drag_what == "endpoint2":
                    seg["x2"] = sx
                    seg["y2"] = sy
                elif self.drag_what == "object":
                    # Move whole segment
                    cx = (seg["x1"] + seg["x2"]) / 2
                    cy = (seg["y1"] + seg["y2"]) / 2
                    dx = sx - cx
                    dy = sy - cy
                    seg["x1"] += dx
                    seg["y1"] += dy
                    seg["x2"] += dx
                    seg["y2"] += dy

        # Update inputs to reflect new positions
        self.build_inputs()

    def handle_key(self, event):
        mods = pygame.key.get_mods()
        ctrl = mods & pygame.KMOD_CTRL

        if event.key == pygame.K_ESCAPE:
            self.placing_start = None
            self.selected = None
            self.inputs = []
            self.status_text = "Cancelled"
            if hasattr(self, 'show_file_browser') and self.show_file_browser:
                self.show_file_browser = False

        elif event.key == pygame.K_DELETE or event.key == pygame.K_BACKSPACE:
            if not any(inp.active for inp in self.inputs):
                self.delete_selected()

        elif event.key == pygame.K_g and ctrl:
            self.generate_peg_grid()
        elif event.key == pygame.K_g and not ctrl:
            self.snap = not self.snap
            self.status_text = f"Grid snap: {'ON' if self.snap else 'OFF'}"

        elif event.key == pygame.K_s and ctrl:
            self.save_level()
        elif event.key == pygame.K_o and ctrl:
            self.show_file_browser = True
            self.file_browser_files = self.list_json_files()
            self.file_browser_scroll = 0
        elif event.key == pygame.K_n and ctrl:
            self.push_undo()
            self.level = get_default_level()
            self.selected = None
            self.inputs = []
            self.current_file = None
            self.status_text = "New level"
        elif event.key == pygame.K_z and ctrl:
            self.undo()
        elif event.key == pygame.K_F5:
            self.preview()

        elif event.key in TOOL_KEYS and not any(inp.active for inp in self.inputs):
            self.tool = TOOL_KEYS[event.key]
            self.placing_start = None
            self.status_text = f"Tool: {TOOL_NAMES[self.tool]}"

    # --- Drawing ---

    def draw(self):
        self.screen.fill(C_BG)

        m = self.maze()

        # Grid
        if self.snap and self.grid_size > 0:
            for x in range(int(m["maze_left"]), int(m["maze_right"]) + 1, self.grid_size):
                pygame.draw.line(self.screen, C_GRID, (x, m["maze_top"]), (x, m["maze_bottom"]))
            for y in range(int(m["maze_top"]), int(m["maze_bottom"]) + 1, self.grid_size):
                pygame.draw.line(self.screen, C_GRID, (m["maze_left"], y), (m["maze_right"], y))

        # Maze background
        maze_rect = pygame.Rect(m["maze_left"], m["maze_top"],
                                m["maze_right"] - m["maze_left"],
                                m["maze_bottom"] - m["maze_top"])
        pygame.draw.rect(self.screen, C_MAZE_BG, maze_rect)
        pygame.draw.rect(self.screen, C_MAZE_BORDER, maze_rect, 2)

        # Draw walls
        for i, wall in enumerate(self.level["walls"]):
            color = C_SELECTED if self.selected == ("wall", i) else C_WALL
            pygame.draw.line(self.screen, color,
                             (int(wall["x1"]), int(wall["y1"])),
                             (int(wall["x2"]), int(wall["y2"])),
                             max(2, wall["thickness"]))
            if self.selected == ("wall", i):
                pygame.draw.circle(self.screen, C_SELECTED, (int(wall["x1"]), int(wall["y1"])), 5, 1)
                pygame.draw.circle(self.screen, C_SELECTED, (int(wall["x2"]), int(wall["y2"])), 5, 1)

        # Draw platforms
        for i, plat in enumerate(self.level["platforms"]):
            color = C_SELECTED if self.selected == ("platform", i) else C_PLATFORM
            pygame.draw.line(self.screen, color,
                             (int(plat["x1"]), int(plat["y1"])),
                             (int(plat["x2"]), int(plat["y2"])),
                             max(2, plat["thickness"]))
            if self.selected == ("platform", i):
                pygame.draw.circle(self.screen, C_SELECTED, (int(plat["x1"]), int(plat["y1"])), 5, 1)
                pygame.draw.circle(self.screen, C_SELECTED, (int(plat["x2"]), int(plat["y2"])), 5, 1)

        # Draw pegs
        for i, peg in enumerate(self.level["pegs"]):
            px, py = int(peg["x"]), int(peg["y"])
            if self.selected == ("peg", i):
                pygame.draw.circle(self.screen, C_SELECTED, (px, py), peg["radius"] + 2, 1)
            pygame.draw.circle(self.screen, C_PEG, (px, py), peg["radius"])
            pygame.draw.circle(self.screen, C_PEG_HI, (px - 1, py - 1), max(1, peg["radius"] // 2))

        # Draw buckets
        self.draw_buckets()

        # Ghost preview
        mouse_pos = pygame.mouse.get_pos()
        if self.in_canvas(mouse_pos):
            gx, gy = self.snap_pos(mouse_pos[0], mouse_pos[1])

            if self.tool == TOOL_PEG:
                pygame.draw.circle(self.screen, C_GHOST, (gx, gy), 5, 1)

            if self.placing_start and self.tool in (TOOL_PLATFORM, TOOL_WALL):
                pygame.draw.line(self.screen, C_GHOST, self.placing_start, (gx, gy), 2)
                pygame.draw.circle(self.screen, C_GHOST, self.placing_start, 4, 1)
                pygame.draw.circle(self.screen, C_GHOST, (gx, gy), 4, 1)

            if self.tool == TOOL_ERASER:
                pygame.draw.circle(self.screen, (255, 80, 80), mouse_pos, 10, 1)

        # Toolbar
        self.draw_toolbar()

        # Panel
        self.draw_panel()

        # Status bar
        pygame.draw.rect(self.screen, C_STATUS_BG,
                         (0, EDITOR_HEIGHT - STATUS_HEIGHT, EDITOR_WIDTH, STATUS_HEIGHT))
        status = self.font.render(self.status_text, True, C_TEXT)
        self.screen.blit(status, (10, EDITOR_HEIGHT - STATUS_HEIGHT + 5))

        # Overlays
        if hasattr(self, 'show_file_browser') and self.show_file_browser:
            self.draw_file_browser()
        if hasattr(self, 'show_save_dialog') and self.show_save_dialog:
            self.draw_save_dialog()

    def draw_buckets(self):
        m = self.maze()
        entries = self.level["buckets"]["entries"]
        bh = self.level["buckets"]["height"]
        total_w = m["maze_right"] - m["maze_left"]
        bucket_top = m["maze_bottom"] - bh

        x = m["maze_left"]
        for i, entry in enumerate(entries):
            w = entry["width_fraction"] * total_w

            # Background
            if entry["score"] == 0:
                bg = (25, 50, 35)
            else:
                intensity = min(255, 25 + entry["score"] * 6)
                bg = (intensity, intensity + 5, intensity + 15)
            rect = pygame.Rect(int(x) + 1, int(bucket_top) + 1, int(w) - 2, bh - 2)
            pygame.draw.rect(self.screen, bg, rect)

            # Selection highlight
            if self.selected == ("bucket", i):
                pygame.draw.rect(self.screen, C_SELECTED, rect, 2)

            # Label
            if entry["score"] == 0:
                lc = (100, 220, 130)
            elif entry["score"] >= 10:
                lc = (255, 215, 0)
            else:
                lc = (200, 200, 220)
            label = self.font.render(entry["label"], True, lc)
            lx = int(x + w / 2 - label.get_width() / 2)
            ly = int(bucket_top + bh / 2 - label.get_height() / 2)
            self.screen.blit(label, (lx, ly))

            x += w

        # Divider lines with handles
        x = m["maze_left"]
        for i in range(len(entries)):
            x += entries[i]["width_fraction"] * total_w
            if i < len(entries) - 1:
                dx = int(x)
                pygame.draw.line(self.screen, C_WALL, (dx, int(bucket_top)), (dx, m["maze_bottom"]), 3)
                # Handle
                handle = pygame.Rect(dx - 4, int(bucket_top) - 8, 8, 8)
                pygame.draw.rect(self.screen, (180, 180, 200), handle)

        # Bottom line
        pygame.draw.line(self.screen, C_WALL,
                         (m["maze_left"], m["maze_bottom"]), (m["maze_right"], m["maze_bottom"]), 4)

    def draw_toolbar(self):
        pygame.draw.rect(self.screen, C_TOOLBAR_BG, (0, 0, EDITOR_WIDTH, TOOLBAR_HEIGHT))
        pygame.draw.line(self.screen, C_PANEL_BORDER, (0, TOOLBAR_HEIGHT), (EDITOR_WIDTH, TOOLBAR_HEIGHT))

        buttons = [("Save", 0), ("Load", 65), ("New", 130), ("Preview", 190), ("Grid", 265)]
        mx, my = pygame.mouse.get_pos()
        for label, bx in buttons:
            bw = 55 if label != "Preview" else 65
            rect = pygame.Rect(bx + 5, 6, bw, 26)
            hover = rect.collidepoint(mx, my) and my < TOOLBAR_HEIGHT
            color = C_BTN_HOVER if hover else C_BTN
            if label == "Grid" and self.snap:
                color = C_BTN_ACTIVE
            pygame.draw.rect(self.screen, color, rect, border_radius=4)
            pygame.draw.rect(self.screen, C_PANEL_BORDER, rect, 1, border_radius=4)
            txt = self.font.render(label, True, C_TEXT)
            self.screen.blit(txt, (rect.x + (rect.w - txt.get_width()) // 2, rect.y + 5))

        # File indicator
        fname = os.path.basename(self.current_file) if self.current_file else "(unsaved)"
        ftxt = self.font.render(fname, True, C_TEXT_DIM)
        self.screen.blit(ftxt, (340, 12))

    def draw_panel(self):
        # Panel background
        panel = pygame.Rect(PANEL_LEFT, TOOLBAR_HEIGHT, EDITOR_WIDTH - PANEL_LEFT,
                            EDITOR_HEIGHT - TOOLBAR_HEIGHT - STATUS_HEIGHT)
        pygame.draw.rect(self.screen, C_PANEL_BG, panel)
        pygame.draw.line(self.screen, C_PANEL_BORDER, (PANEL_LEFT, TOOLBAR_HEIGHT),
                         (PANEL_LEFT, EDITOR_HEIGHT - STATUS_HEIGHT))

        px = PANEL_LEFT + 10
        y = TOOLBAR_HEIGHT + 10

        # Title
        title = self.title_font.render("TOOLS", True, C_TEXT)
        self.screen.blit(title, (px, y))
        y += 22

        # Tool buttons
        mx, my = pygame.mouse.get_pos()
        tool_list = [TOOL_SELECT, TOOL_PEG, TOOL_PLATFORM, TOOL_WALL, TOOL_BUCKET, TOOL_ERASER]
        for tool in tool_list:
            rect = pygame.Rect(px, y, 160, 24)
            hover = rect.collidepoint(mx, my)
            if tool == self.tool:
                color = C_BTN_ACTIVE
            elif hover:
                color = C_BTN_HOVER
            else:
                color = C_BTN
            pygame.draw.rect(self.screen, color, rect, border_radius=3)
            txt = self.font.render(TOOL_NAMES[tool], True, C_TEXT)
            self.screen.blit(txt, (px + 8, y + 5))
            y += 30

        # Divider
        y += 5
        pygame.draw.line(self.screen, C_PANEL_BORDER, (px, y), (px + 160, y))
        y += 10

        # Delete button
        if self.selected:
            del_rect = pygame.Rect(px, y, 160, 24)
            hover = del_rect.collidepoint(mx, my)
            pygame.draw.rect(self.screen, (100, 40, 40) if hover else (70, 30, 30), del_rect, border_radius=3)
            del_txt = self.font.render("Delete Selected", True, (220, 100, 100))
            self.screen.blit(del_txt, (px + 8, y + 5))
        y += 30

        # Selection info
        pygame.draw.line(self.screen, C_PANEL_BORDER, (px, y), (px + 160, y))
        y += 8

        if self.selected:
            obj_type, idx = self.selected
            info = self.title_font.render(f"{obj_type.upper()} #{idx}", True, C_SELECTED)
            self.screen.blit(info, (px, y))
            y += 20

            # Draw text inputs
            for inp in self.inputs:
                inp.draw(self.screen, self.font)

            # Bucket-specific buttons
            if obj_type == "bucket":
                entries = self.level["buckets"]["entries"]
                by = 345 + 120
                if len(entries) < 15:
                    btn = pygame.Rect(px, by, 160, 24)
                    hover = btn.collidepoint(mx, my)
                    pygame.draw.rect(self.screen, C_BTN_HOVER if hover else C_BTN, btn, border_radius=3)
                    self.screen.blit(self.font.render("Insert Left", True, C_TEXT), (px + 8, by + 5))

                    btn2 = pygame.Rect(px, by + 28, 160, 24)
                    hover2 = btn2.collidepoint(mx, my)
                    pygame.draw.rect(self.screen, C_BTN_HOVER if hover2 else C_BTN, btn2, border_radius=3)
                    self.screen.blit(self.font.render("Insert Right", True, C_TEXT), (px + 8, by + 33))

                    if len(entries) > 2:
                        btn3 = pygame.Rect(px, by + 56, 160, 24)
                        hover3 = btn3.collidepoint(mx, my)
                        pygame.draw.rect(self.screen, (100, 40, 40) if hover3 else (70, 30, 30), btn3, border_radius=3)
                        self.screen.blit(self.font.render("Delete Bucket", True, (220, 100, 100)), (px + 8, by + 61))

                count_txt = self.font.render(f"Buckets: {len(entries)}", True, C_TEXT_DIM)
                self.screen.blit(count_txt, (px, by + 88))
        else:
            no_sel = self.font.render("Nothing selected", True, C_TEXT_DIM)
            self.screen.blit(no_sel, (px, y))

        # Stats at bottom of panel
        by = EDITOR_HEIGHT - STATUS_HEIGHT - 80
        pygame.draw.line(self.screen, C_PANEL_BORDER, (px, by), (px + 160, by))
        by += 8
        stats = [
            f"Pegs: {len(self.level['pegs'])}",
            f"Platforms: {len(self.level['platforms'])}",
            f"Walls: {len(self.level['walls'])}",
            f"Buckets: {len(self.level['buckets']['entries'])}",
        ]
        for s in stats:
            txt = self.font.render(s, True, C_TEXT_DIM)
            self.screen.blit(txt, (px, by))
            by += 16

    def draw_file_browser(self):
        """Draw a file browser overlay with scrollbar."""
        overlay = pygame.Surface((EDITOR_WIDTH, EDITOR_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        bw, bh = 350, 500
        bx = (EDITOR_WIDTH - bw) // 2
        by = (EDITOR_HEIGHT - bh) // 2
        pygame.draw.rect(self.screen, C_PANEL_BG, (bx, by, bw, bh), border_radius=8)
        pygame.draw.rect(self.screen, C_PANEL_BORDER, (bx, by, bw, bh), 2, border_radius=8)

        title = self.title_font.render("Load Level", True, C_TEXT)
        self.screen.blit(title, (bx + 20, by + 15))

        files = getattr(self, 'file_browser_files', [])
        scroll = getattr(self, 'file_browser_scroll', 0)
        mx, my = pygame.mouse.get_pos()

        # List area
        list_top = by + 45
        list_bottom = by + bh - 35
        list_height = list_bottom - list_top
        row_h = 30
        visible_count = list_height // row_h
        max_scroll = max(0, len(files) - visible_count)
        scroll = max(0, min(scroll, max_scroll))
        self.file_browser_scroll = scroll

        # Clip to list area
        clip_rect = pygame.Rect(bx, list_top, bw, list_height)
        self.screen.set_clip(clip_rect)

        fy = list_top
        for i in range(scroll, min(scroll + visible_count, len(files))):
            fname = files[i]
            rect = pygame.Rect(bx + 10, fy, bw - 35, 26)
            hover = rect.collidepoint(mx, my)
            if hover:
                pygame.draw.rect(self.screen, C_BTN_HOVER, rect, border_radius=3)
                if pygame.mouse.get_pressed()[0]:
                    filepath = os.path.join(self.dir, fname)
                    self.load_level_file(filepath)
                    self.show_file_browser = False
                    self.screen.set_clip(None)
                    return
            txt = self.font.render(fname, True, C_TEXT)
            self.screen.blit(txt, (rect.x + 8, rect.y + 5))
            fy += row_h

        self.screen.set_clip(None)

        if not files:
            no_files = self.font.render("No .json level files found", True, C_TEXT_DIM)
            self.screen.blit(no_files, (bx + 20, list_top))

        # Scrollbar
        if len(files) > visible_count:
            sb_x = bx + bw - 18
            sb_w = 8
            track_rect = pygame.Rect(sb_x, list_top, sb_w, list_height)
            pygame.draw.rect(self.screen, (40, 40, 55), track_rect, border_radius=4)

            thumb_frac = visible_count / len(files)
            thumb_h = max(20, int(list_height * thumb_frac))
            thumb_pos = list_top + int((list_height - thumb_h) * scroll / max_scroll) if max_scroll > 0 else list_top
            thumb_rect = pygame.Rect(sb_x, thumb_pos, sb_w, thumb_h)
            thumb_hover = thumb_rect.collidepoint(mx, my)
            thumb_color = (120, 120, 150) if thumb_hover else (80, 80, 110)
            pygame.draw.rect(self.screen, thumb_color, thumb_rect, border_radius=4)

            # File count
            count_txt = self.font.render(f"{len(files)} files", True, C_TEXT_DIM)
            self.screen.blit(count_txt, (bx + 20, by + bh - 28))

        hint = self.font.render("Escape to cancel, scroll to browse", True, C_TEXT_DIM)
        self.screen.blit(hint, (bx + 20, by + bh - 14))

    def draw_save_dialog(self):
        """Draw the save dialog overlay."""
        overlay = pygame.Surface((EDITOR_WIDTH, EDITOR_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.screen.blit(overlay, (0, 0))

        bw, bh = 380, 220
        bx = (EDITOR_WIDTH - bw) // 2
        by = (EDITOR_HEIGHT - bh) // 2
        pygame.draw.rect(self.screen, C_PANEL_BG, (bx, by, bw, bh), border_radius=8)
        pygame.draw.rect(self.screen, C_PANEL_BORDER, (bx, by, bw, bh), 2, border_radius=8)

        title = self.title_font.render("Save Level", True, C_TEXT)
        self.screen.blit(title, (bx + 20, by + 15))

        # Draw the two inputs
        self.save_name_input.draw(self.screen, self.font)
        self.save_file_input.draw(self.screen, self.font)

        # Save and Cancel buttons
        mx, my = pygame.mouse.get_pos()
        save_btn = pygame.Rect(bx + bw - 170, by + bh - 40, 70, 28)
        cancel_btn = pygame.Rect(bx + bw - 90, by + bh - 40, 70, 28)

        hover_save = save_btn.collidepoint(mx, my)
        hover_cancel = cancel_btn.collidepoint(mx, my)

        pygame.draw.rect(self.screen, (50, 100, 60) if hover_save else (40, 80, 50), save_btn, border_radius=4)
        pygame.draw.rect(self.screen, C_PANEL_BORDER, save_btn, 1, border_radius=4)
        stxt = self.font.render("Save", True, (140, 220, 150))
        self.screen.blit(stxt, (save_btn.x + (save_btn.w - stxt.get_width()) // 2, save_btn.y + 6))

        pygame.draw.rect(self.screen, C_BTN_HOVER if hover_cancel else C_BTN, cancel_btn, border_radius=4)
        pygame.draw.rect(self.screen, C_PANEL_BORDER, cancel_btn, 1, border_radius=4)
        ctxt = self.font.render("Cancel", True, C_TEXT)
        self.screen.blit(ctxt, (cancel_btn.x + (cancel_btn.w - ctxt.get_width()) // 2, cancel_btn.y + 6))

        hint = self.font.render("Enter to save, Escape to cancel", True, C_TEXT_DIM)
        self.screen.blit(hint, (bx + 20, by + bh - 18))

    # --- Main loop ---

    def run(self):
        self.show_file_browser = False
        self.show_save_dialog = False
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif hasattr(self, 'show_save_dialog') and self.show_save_dialog:
                    # Save dialog events
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.show_save_dialog = False
                            self.status_text = "Save cancelled"
                        elif event.key == pygame.K_RETURN:
                            if self.save_name_input.active:
                                self.save_name_input.active = False
                                self.save_file_input.active = True
                            elif self.save_file_input.active:
                                self.save_file_input.active = False
                                self.do_save()
                            else:
                                self.do_save()
                        elif event.key == pygame.K_TAB:
                            # Tab between inputs
                            if self.save_name_input.active:
                                self.save_name_input.active = False
                                self.save_file_input.active = True
                            elif self.save_file_input.active:
                                self.save_file_input.active = False
                            else:
                                self.save_name_input.active = True
                        else:
                            self.save_name_input.handle_event(event)
                            self.save_file_input.handle_event(event)
                    elif event.type == pygame.MOUSEBUTTONDOWN:
                        self.save_name_input.handle_event(event)
                        self.save_file_input.handle_event(event)
                        # Check save/cancel button clicks
                        bw, bh_d = 380, 220
                        bx = (EDITOR_WIDTH - bw) // 2
                        by_d = (EDITOR_HEIGHT - bh_d) // 2
                        save_btn = pygame.Rect(bx + bw - 170, by_d + bh_d - 40, 70, 28)
                        cancel_btn = pygame.Rect(bx + bw - 90, by_d + bh_d - 40, 70, 28)
                        if save_btn.collidepoint(event.pos):
                            self.do_save()
                        elif cancel_btn.collidepoint(event.pos):
                            self.show_save_dialog = False
                            self.status_text = "Save cancelled"
                elif hasattr(self, 'show_file_browser') and self.show_file_browser:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            self.show_file_browser = False
                        elif event.key == pygame.K_UP:
                            self.file_browser_scroll = max(0, self.file_browser_scroll - 1)
                        elif event.key == pygame.K_DOWN:
                            self.file_browser_scroll += 1
                        elif event.key == pygame.K_PAGEUP:
                            self.file_browser_scroll = max(0, self.file_browser_scroll - 10)
                        elif event.key == pygame.K_PAGEDOWN:
                            self.file_browser_scroll += 10
                        elif event.key == pygame.K_HOME:
                            self.file_browser_scroll = 0
                        elif event.key == pygame.K_END:
                            self.file_browser_scroll = max(0, len(getattr(self, 'file_browser_files', [])) - 1)
                    elif event.type == pygame.MOUSEWHEEL:
                        self.file_browser_scroll = max(0, self.file_browser_scroll - event.y * 3)
                    # File browser click handled in draw
                else:
                    self.handle_event(event)

            self.draw()
            pygame.display.flip()
            self.clock.tick(30)

        pygame.quit()


if __name__ == "__main__":
    editor = Editor()
    editor.run()
