import pygame
import pymunk
import random
import math
import os
import json
import sys

# --- Constants ---
FPS = 60
BALL_RADIUS = 8
GRAVITY = (0, 900)
BALL_LIMIT = 80
STUCK_THRESHOLD = 180  # frames (~3 sec) before nudging a stuck ball
STUCK_SPEED = 5.0  # speed below which a ball counts as stuck
STUCK_PEG_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stuck_pegs.log")
STUCK_PEG_RADIUS = 30  # max distance to attribute a stuck ball to a peg
WINS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wins.json")
AUTO_RESTART_SECONDS = 10

# Ball colors with names and display colors
BALL_TYPES = [
    {"name": "Red",        "color": (220, 50, 50),   "score": 0, "sparkly": False},
    {"name": "Blue",       "color": (50, 100, 220),  "score": 0, "sparkly": False},
    {"name": "Green",      "color": (50, 180, 50),   "score": 0, "sparkly": False},
    {"name": "Yellow",     "color": (220, 200, 40),  "score": 0, "sparkly": False},
    {"name": "Purple",     "color": (160, 50, 200),  "score": 0, "sparkly": False},
    {"name": "Orange",     "color": (230, 130, 30),  "score": 0, "sparkly": False},
    {"name": "Cyan",       "color": (40, 200, 200),  "score": 0, "sparkly": False},
    {"name": "Pink",       "color": (230, 100, 160), "score": 0, "sparkly": False},
    {"name": "S.Red",      "color": (220, 50, 50),   "score": 0, "sparkly": True},
    {"name": "S.Blue",     "color": (50, 100, 220),  "score": 0, "sparkly": True},
    {"name": "S.Green",    "color": (50, 180, 50),   "score": 0, "sparkly": True},
    {"name": "S.Yellow",   "color": (220, 200, 40),  "score": 0, "sparkly": True},
    {"name": "S.Purple",   "color": (160, 50, 200),  "score": 0, "sparkly": True},
    {"name": "S.Orange",   "color": (230, 130, 30),  "score": 0, "sparkly": True},
    {"name": "S.Cyan",     "color": (40, 200, 200),  "score": 0, "sparkly": True},
    {"name": "S.Pink",     "color": (230, 100, 160), "score": 0, "sparkly": True},
]

# Collision types
BALL_CT = 1
WALL_CT = 2
FLOOR_CT = 3
PEG_CT = 4


def load_level(filepath):
    """Load a level from a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def load_wins():
    """Load the persistent wins tracker from JSON file."""
    if os.path.exists(WINS_FILE):
        try:
            with open(WINS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_wins(wins):
    """Save the wins tracker to JSON file."""
    with open(WINS_FILE, "w") as f:
        json.dump(wins, f, indent=2)


# --- Physics creation from level data ---

def create_walls_from_level(space, level, static_bodies):
    """Create walls from level data. Appends bodies to static_bodies for cleanup."""
    walls = []
    for w in level["walls"]:
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        seg = pymunk.Segment(body, (w["x1"], w["y1"]), (w["x2"], w["y2"]), w["thickness"])
        seg.elasticity = w["elasticity"]
        seg.friction = w["friction"]
        seg.collision_type = WALL_CT
        seg.color = pygame.Color(100, 100, 120, 255)
        space.add(body, seg)
        walls.append(seg)
        static_bodies.append((body, seg))
    return walls


def create_pegs_from_level(space, level, static_bodies):
    """Create pegs from level data (explicit positions)."""
    pegs = []
    peg_color = (160, 160, 180)
    for p in level["pegs"]:
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        body.position = (p["x"], p["y"])
        shape = pymunk.Circle(body, p["radius"])
        shape.elasticity = p["elasticity"]
        shape.friction = p["friction"]
        shape.collision_type = PEG_CT
        shape.color = pygame.Color(*peg_color, 255)
        space.add(body, shape)
        pegs.append(shape)
        static_bodies.append((body, shape))
    return pegs


def create_platforms_from_level(space, level, static_bodies):
    """Create platforms from level data."""
    platforms = []
    platform_color = (130, 130, 150)
    for p in level["platforms"]:
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        seg = pymunk.Segment(body, (p["x1"], p["y1"]), (p["x2"], p["y2"]), p["thickness"])
        seg.elasticity = p["elasticity"]
        seg.friction = p["friction"]
        seg.collision_type = WALL_CT
        seg.color = pygame.Color(*platform_color, 255)
        space.add(body, seg)
        platforms.append(seg)
        static_bodies.append((body, seg))
    return platforms


def create_buckets_from_level(space, level, static_bodies):
    """Create buckets from level data with variable widths."""
    maze = level["maze"]
    bucket_data = level["buckets"]
    entries = bucket_data["entries"]
    bh = bucket_data["height"]
    total_width = maze["maze_right"] - maze["maze_left"]
    bucket_top = maze["maze_bottom"] - bh
    dividers = []
    sensors = []
    thickness = 3

    # Calculate pixel widths from fractions
    widths = [e["width_fraction"] * total_width for e in entries]

    # Divider walls between buckets
    x = maze["maze_left"]
    divider_xs = []
    for i in range(len(entries)):
        x += widths[i]
        if i < len(entries) - 1:
            divider_xs.append(x)
            body = pymunk.Body(body_type=pymunk.Body.STATIC)
            seg = pymunk.Segment(body, (x, bucket_top), (x, maze["maze_bottom"]), thickness)
            seg.elasticity = 0.3
            seg.friction = 0.4
            seg.collision_type = WALL_CT
            space.add(body, seg)
            dividers.append(seg)
            static_bodies.append((body, seg))

    # Floor sensor per bucket
    x = maze["maze_left"]
    for i, entry in enumerate(entries):
        left = x
        right = x + widths[i]
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        seg = pymunk.Segment(body, (left + thickness, maze["maze_bottom"] - 2),
                             (right - thickness, maze["maze_bottom"] - 2), 4)
        seg.sensor = True
        seg.collision_type = FLOOR_CT
        seg.bucket_score = entry["score"]
        seg.bucket_index = i
        space.add(body, seg)
        sensors.append(seg)
        static_bodies.append((body, seg))
        x += widths[i]

    # Solid floor under the buckets
    body = pymunk.Body(body_type=pymunk.Body.STATIC)
    seg = pymunk.Segment(body, (maze["maze_left"], maze["maze_bottom"]),
                         (maze["maze_right"], maze["maze_bottom"]), 4)
    seg.elasticity = 0.2
    seg.friction = 0.6
    seg.collision_type = WALL_CT
    space.add(body, seg)
    static_bodies.append((body, seg))

    return dividers, sensors


def load_level_sequence(game_dir):
    """Load the level sequence file listing level filenames to cycle through."""
    seq_file = os.path.join(game_dir, "level_sequence.json")
    if os.path.exists(seq_file):
        try:
            with open(seq_file, "r") as f:
                data = json.load(f)
            files = data.get("levels", [])
            # Resolve to absolute paths and filter to existing files
            resolved = []
            for fname in files:
                path = os.path.join(game_dir, fname)
                if os.path.exists(path):
                    resolved.append(path)
            return resolved
        except (json.JSONDecodeError, IOError):
            pass
    return []


def spawn_ball(space, balls, ball_type_index, maze_info, ball_radius, spawn_info):
    """Spawn a ball at the top of the maze with slight random offset."""
    mass = 1
    moment = pymunk.moment_for_circle(mass, 0, ball_radius)
    body = pymunk.Body(mass, moment)
    center_x = (maze_info["maze_left"] + maze_info["maze_right"]) / 2
    x = center_x + random.uniform(-spawn_info["x_spread"], spawn_info["x_spread"])
    body.position = (x, maze_info["maze_top"] + spawn_info["y_offset"])
    body.velocity = (random.uniform(-30, 30), 0)

    shape = pymunk.Circle(body, ball_radius)
    shape.elasticity = 0.5
    shape.friction = 0.3
    shape.collision_type = BALL_CT
    shape.ball_type = ball_type_index

    space.add(body, shape)
    balls.append(shape)
    return shape


def remove_ball(space, ball, balls):
    """Remove a ball from the space and tracking list."""
    space.remove(ball.body, ball)
    if ball in balls:
        balls.remove(ball)


# --- Drawing functions ---

def draw_scoreboard(screen, font, small_font, total_score, ball_counts, eliminated, maze_info):
    """Draw the scoreboard on the right side."""
    scoreboard_x = maze_info["maze_right"] + 20
    w = maze_info["width"]
    h = maze_info["height"]

    # Background panel
    panel_rect = pygame.Rect(scoreboard_x - 5, 10, w - scoreboard_x - 5, h - 20)
    pygame.draw.rect(screen, (30, 30, 45), panel_rect, border_radius=8)
    pygame.draw.rect(screen, (80, 80, 100), panel_rect, 2, border_radius=8)

    # Title
    title = font.render("SCORES", True, (220, 220, 240))
    screen.blit(title, (scoreboard_x + 10, 25))

    # Total
    total_text = font.render(f"Total: {total_score}", True, (255, 215, 0))
    screen.blit(total_text, (scoreboard_x + 10, 55))

    # Divider
    pygame.draw.line(screen, (80, 80, 100),
                     (scoreboard_x + 5, 85), (w - 15, 85), 1)

    # Individual scores - sorted by score descending
    y = 100
    row_height = 22
    sorted_types = sorted(enumerate(BALL_TYPES), key=lambda ib: ib[1]["score"], reverse=True)
    for idx, bt in sorted_types:
        is_elim = idx in eliminated

        # Color swatch (dimmed if eliminated)
        color = bt["color"] if not is_elim else tuple(c // 3 for c in bt["color"])
        swatch_y = y + row_height // 2 - 1
        pygame.draw.circle(screen, color, (scoreboard_x + 16, swatch_y), 6)
        if bt["sparkly"]:
            pygame.draw.circle(screen, (255, 255, 255), (scoreboard_x + 16, swatch_y), 6, 1)
        else:
            pygame.draw.circle(screen, (200, 200, 200), (scoreboard_x + 16, swatch_y), 6, 1)
        if is_elim:
            pygame.draw.line(screen, (180, 50, 50), (scoreboard_x + 11, swatch_y - 5), (scoreboard_x + 21, swatch_y + 5), 2)
            pygame.draw.line(screen, (180, 50, 50), (scoreboard_x + 21, swatch_y - 5), (scoreboard_x + 11, swatch_y + 5), 2)

        # Name and score
        count = ball_counts.get(bt['name'], 0)
        text_color = (100, 100, 110) if is_elim else (200, 200, 210)
        text = small_font.render(f"{bt['name']} ({count}): {bt['score']}", True, text_color)
        screen.blit(text, (scoreboard_x + 28, y + 1))

        # Strikethrough line for eliminated
        if is_elim:
            tx = scoreboard_x + 28
            tw = text.get_width()
            th_y = y + row_height // 2
            pygame.draw.line(screen, (180, 50, 50), (tx, th_y), (tx + tw, th_y), 2)

        y += row_height

    # Instructions
    y += 20
    pygame.draw.line(screen, (80, 80, 100),
                     (scoreboard_x + 5, y), (w - 15, y), 1)
    y += 10
    instructions = [
        "Click: Add ball",
        "1-8: Ball type",
        "Space: Add wave",
        "R: Reset scores",
        "Speed: +/-",
        "F11: Fullscreen",
    ]
    for line in instructions:
        text = small_font.render(line, True, (140, 140, 160))
        screen.blit(text, (scoreboard_x + 10, y))
        y += 22


def draw_maze_border(screen, maze_info):
    """Draw a decorative border around the maze area."""
    border_rect = pygame.Rect(maze_info["maze_left"] - 8, maze_info["maze_top"] - 8,
                              maze_info["maze_right"] - maze_info["maze_left"] + 16,
                              maze_info["maze_bottom"] - maze_info["maze_top"] + 16)
    pygame.draw.rect(screen, (60, 60, 80), border_rect, 3, border_radius=4)


_frame_counter = 0
_sparkle_trails = []  # list of (x, y, color, frames_remaining)
SPARKLE_TRAIL_LIFETIME = 60  # frames (~1 second)
SPARKLE_TRAIL_INTERVAL = 3   # emit a particle every N frames


def draw_sparkle_trails(screen):
    """Draw and age sparkle trail particles."""
    for particle in _sparkle_trails:
        x, y, color, life = particle
        alpha = life / SPARKLE_TRAIL_LIFETIME
        r = int(color[0] * alpha)
        g = int(color[1] * alpha)
        b = int(color[2] * alpha)
        size = max(1, int(2 * alpha))
        pygame.draw.circle(screen, (r, g, b), (int(x), int(y)), size)


def update_sparkle_trails():
    """Age particles and remove expired ones."""
    i = 0
    while i < len(_sparkle_trails):
        p = _sparkle_trails[i]
        _sparkle_trails[i] = (p[0], p[1], p[2], p[3] - 1)
        if _sparkle_trails[i][3] <= 0:
            _sparkle_trails.pop(i)
        else:
            i += 1


def emit_sparkle_trail(ball):
    """Emit a sparkle particle at the ball's current position."""
    bt = BALL_TYPES[ball.ball_type]
    if not bt["sparkly"]:
        return
    if _frame_counter % SPARKLE_TRAIL_INTERVAL != 0:
        return
    x, y = ball.body.position.x, ball.body.position.y
    bright = tuple(min(255, c + 100) for c in bt["color"])
    _sparkle_trails.append((
        x + random.uniform(-3, 3),
        y + random.uniform(-3, 3),
        bright,
        SPARKLE_TRAIL_LIFETIME
    ))


def draw_ball(screen, ball, ball_radius):
    """Draw a ball with a slight shading effect. Sparkly balls get animated sparkles."""
    pos = int(ball.body.position.x), int(ball.body.position.y)
    bt = BALL_TYPES[ball.ball_type]
    color = bt["color"]

    pygame.draw.circle(screen, color, pos, ball_radius)

    highlight_color = tuple(min(255, c + 80) for c in color)
    highlight_pos = (pos[0] - 2, pos[1] - 2)
    pygame.draw.circle(screen, highlight_color, highlight_pos, ball_radius // 3)

    if bt["sparkly"]:
        pygame.draw.circle(screen, (255, 255, 255), pos, ball_radius, 1)
        num_sparkles = 3
        speed = 0.08
        base_angle = _frame_counter * speed + ball.ball_type * 0.7
        for i in range(num_sparkles):
            angle = base_angle + i * (2 * math.pi / num_sparkles)
            r = ball_radius + 2
            sx = pos[0] + int(r * math.cos(angle))
            sy = pos[1] + int(r * math.sin(angle))
            brightness = int(180 + 75 * math.sin(_frame_counter * 0.15 + i * 2.0))
            spark_color = (brightness, brightness, brightness)
            pygame.draw.circle(screen, spark_color, (sx, sy), 1)


def draw_pegs(screen, pegs):
    """Draw pegs with a subtle 3D effect."""
    for peg in pegs:
        pos = int(peg.body.position.x), int(peg.body.position.y)
        pygame.draw.circle(screen, (160, 160, 180), pos, 5)
        pygame.draw.circle(screen, (200, 200, 210), (pos[0] - 1, pos[1] - 1), 2)


def draw_speed_indicator(screen, font, speed_mult, maze_info):
    """Draw current speed multiplier."""
    text = font.render(f"Speed: {speed_mult}x", True, (180, 180, 200))
    screen.blit(text, (maze_info["maze_left"], maze_info["maze_top"] - 25))


def draw_ball_counter(screen, font, num_balls, ball_limit, maze_info):
    """Draw the current ball count vs limit."""
    color = (255, 80, 80) if num_balls >= ball_limit else (180, 180, 200)
    text = font.render(f"Balls: {num_balls}/{ball_limit}", True, color)
    screen.blit(text, (maze_info["maze_left"] + 350, maze_info["maze_top"] - 25))


def draw_game_over(screen, font, winner_idx, wins, countdown_seconds, maze_info):
    """Draw a game over overlay announcing the winner with wins history."""
    w, h = maze_info["width"], maze_info["height"]
    overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))

    bt = BALL_TYPES[winner_idx]
    cx, cy = w // 2, h // 2

    box_w, box_h = 400, 380
    box_rect = pygame.Rect(cx - box_w // 2, cy - box_h // 2, box_w, box_h)
    pygame.draw.rect(screen, (30, 30, 50), box_rect, border_radius=12)
    pygame.draw.rect(screen, bt["color"], box_rect, 3, border_radius=12)

    y_pos = cy - box_h // 2 + 20

    big_font = pygame.font.SysFont("consolas", 36, bold=True)
    title = big_font.render("GAME OVER", True, (220, 220, 240))
    screen.blit(title, (cx - title.get_width() // 2, y_pos))
    y_pos += 50

    winner_text = font.render(f"{bt['name']} wins!", True, bt["color"])
    screen.blit(winner_text, (cx - winner_text.get_width() // 2, y_pos))
    y_pos += 30

    pygame.draw.circle(screen, bt["color"], (cx, y_pos + 10), 16)
    highlight = tuple(min(255, c + 80) for c in bt["color"])
    pygame.draw.circle(screen, highlight, (cx - 4, y_pos + 6), 5)
    y_pos += 35

    score_text = font.render(f"Score: {bt['score']}", True, (255, 215, 0))
    screen.blit(score_text, (cx - score_text.get_width() // 2, y_pos))
    y_pos += 35

    pygame.draw.line(screen, (80, 80, 100), (cx - 150, y_pos), (cx + 150, y_pos), 1)
    y_pos += 10

    wins_title = font.render("Total Wins", True, (200, 200, 220))
    screen.blit(wins_title, (cx - wins_title.get_width() // 2, y_pos))
    y_pos += 25

    small_font = pygame.font.SysFont("consolas", 15)
    sorted_wins = sorted(BALL_TYPES, key=lambda b: wins.get(b["name"], 0), reverse=True)
    for btype in sorted_wins:
        wc = wins.get(btype["name"], 0)
        if wc > 0:
            color = btype["color"]
            pygame.draw.circle(screen, color, (cx - 80, y_pos + 7), 6)
            win_text = small_font.render(f"{btype['name']}: {wc}", True, (200, 200, 210))
            screen.blit(win_text, (cx - 68, y_pos))
            y_pos += 20

    y_pos = cy + box_h // 2 - 30
    countdown_text = font.render(f"Restarting in {countdown_seconds}s  (R to restart now)", True, (140, 140, 160))
    screen.blit(countdown_text, (cx - countdown_text.get_width() // 2, y_pos))


def draw_buckets(screen, font, small_font, bucket_counts, level):
    """Draw the scoring buckets at the bottom of the maze."""
    maze = level["maze"]
    entries = level["buckets"]["entries"]
    bh = level["buckets"]["height"]
    total_width = maze["maze_right"] - maze["maze_left"]
    bucket_top = maze["maze_bottom"] - bh

    x = maze["maze_left"]
    for i, entry in enumerate(entries):
        w = entry["width_fraction"] * total_width
        score = entry["score"]
        label_text = entry["label"]

        # Bucket background
        if score == 0:
            bg_color = (25, 50, 35)
        else:
            intensity = min(255, 25 + score * 6)
            bg_color = (intensity, intensity + 5, intensity + 15)
        rect = pygame.Rect(int(x) + 1, int(bucket_top) + 1,
                           int(w) - 2, bh - 2)
        pygame.draw.rect(screen, bg_color, rect)

        # Score label
        if score == 0:
            label_color = (100, 220, 130)
        elif score >= 10:
            label_color = (255, 215, 0)
        else:
            label_color = (200, 200, 220)
        label = font.render(label_text, True, label_color)
        lx = int(x + w / 2 - label.get_width() / 2)
        ly = int(bucket_top + bh / 2 - label.get_height() / 2)
        screen.blit(label, (lx, ly))

        x += w

    # Divider lines
    x = maze["maze_left"]
    for i in range(len(entries)):
        x += entries[i]["width_fraction"] * total_width
        if i < len(entries) - 1:
            pygame.draw.line(screen, (100, 100, 120), (int(x), int(bucket_top)), (int(x), maze["maze_bottom"]), 3)

    # Bottom line
    pygame.draw.line(screen, (100, 100, 120),
                     (maze["maze_left"], maze["maze_bottom"]), (maze["maze_right"], maze["maze_bottom"]), 4)

    # Bucket hit counters below each bucket
    x = maze["maze_left"]
    for i, entry in enumerate(entries):
        w = entry["width_fraction"] * total_width
        count_val = bucket_counts[i] if i < len(bucket_counts) else 0
        count_label = small_font.render(str(count_val), True, (140, 140, 160))
        cx = int(x + w / 2 - count_label.get_width() / 2)
        screen.blit(count_label, (cx, maze["maze_bottom"] + 6))
        x += w


def main():
    global _frame_counter

    game_dir = os.path.dirname(os.path.abspath(__file__))

    # Load level: from command line arg, or from level sequence
    level_file = sys.argv[1] if len(sys.argv) > 1 else None
    if level_file and os.path.exists(level_file):
        level = load_level(level_file)
        level_files = []  # Single-level mode when launched with specific file
    else:
        level_files = load_level_sequence(game_dir)
        level = load_level(level_files[0])

    # Game state dict for mutable references shared with closures
    gs = {
        "level": level,
        "maze": level["maze"],
        "ball_radius": level.get("ball_radius", BALL_RADIUS),
        "ball_limit": level.get("ball_limit", BALL_LIMIT),
        "spawn_info": level.get("spawn", {"y_offset": 15, "x_spread": 120}),
        "bucket_entries": level["buckets"]["entries"],
        "bucket_count": len(level["buckets"]["entries"]),
        "bucket_counts": [0] * len(level["buckets"]["entries"]),
        "level_index": 0,
    }
    gw, gh = gs["maze"]["width"], gs["maze"]["height"]

    pygame.init()
    screen = pygame.display.set_mode((gw, gh), pygame.RESIZABLE)
    pygame.display.set_caption("Physics Ball Race - Idle Game")
    game_surface = pygame.Surface((gw, gh))
    fullscreen = False
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18, bold=True)
    small_font = pygame.font.SysFont("consolas", 15)

    # Physics space
    space = pymunk.Space()
    space.gravity = tuple(level.get("gravity", GRAVITY))

    # Build the maze from level data
    static_bodies = []
    walls = create_walls_from_level(space, level, static_bodies)
    pegs = create_pegs_from_level(space, level, static_bodies)
    platforms = create_platforms_from_level(space, level, static_bodies)
    bucket_dividers, bucket_sensors = create_buckets_from_level(space, level, static_bodies)

    # Ball tracking
    balls = []
    balls_to_respawn = []
    stuck_frames = {}
    eliminated = set()
    game_over = False
    game_over_timer = 0
    winner = None
    wins = load_wins()
    selected_type = 0
    speed_mult = 1

    def rebuild_level(new_level):
        """Remove all static geometry and rebuild from a new level dict."""
        nonlocal walls, pegs, platforms, bucket_dividers, bucket_sensors

        # Remove all static bodies from space
        for body, shape in static_bodies:
            if body in space.bodies:
                space.remove(body, shape)
        static_bodies.clear()

        # Remove all balls
        for ball in balls[:]:
            remove_ball(space, ball, balls)
        stuck_frames.clear()
        balls_to_respawn.clear()
        _sparkle_trails.clear()

        # Update game state
        gs["level"] = new_level
        gs["maze"] = new_level["maze"]
        gs["ball_radius"] = new_level.get("ball_radius", BALL_RADIUS)
        gs["ball_limit"] = new_level.get("ball_limit", BALL_LIMIT)
        gs["spawn_info"] = new_level.get("spawn", {"y_offset": 15, "x_spread": 120})
        gs["bucket_entries"] = new_level["buckets"]["entries"]
        gs["bucket_count"] = len(new_level["buckets"]["entries"])
        gs["bucket_counts"] = [0] * gs["bucket_count"]

        space.gravity = tuple(new_level.get("gravity", GRAVITY))

        # Rebuild geometry
        walls = create_walls_from_level(space, new_level, static_bodies)
        pegs = create_pegs_from_level(space, new_level, static_bodies)
        platforms = create_platforms_from_level(space, new_level, static_bodies)
        bucket_dividers, bucket_sensors = create_buckets_from_level(space, new_level, static_bodies)

        # Respawn one ball per remaining active color
        active = [i for i in range(len(BALL_TYPES)) if i not in eliminated]
        for i in active:
            spawn_ball(space, balls, i, gs["maze"], gs["ball_radius"], gs["spawn_info"])

    def switch_to_next_level():
        """Advance to the next level in the sequence."""
        if not level_files:
            return
        gs["level_index"] = (gs["level_index"] + 1) % len(level_files)
        new_level = load_level(level_files[gs["level_index"]])
        rebuild_level(new_level)

    def reset_to_first_level():
        """Reset to the first level in the sequence."""
        gs["level_index"] = 0
        new_level = load_level(level_files[0])
        rebuild_level(new_level)

    # Floor collision handler - score based on bucket and queue respawn
    def ball_hit_floor(arbiter, space, data):
        shapes = arbiter.shapes
        ball_shape = None
        bucket_score = 1
        bucket_idx = -1
        for shape in shapes:
            if hasattr(shape, 'ball_type'):
                ball_shape = shape
            if hasattr(shape, 'bucket_score'):
                bucket_score = shape.bucket_score
                bucket_idx = shape.bucket_index
        if ball_shape is not None:
            bt_idx = ball_shape.ball_type
            if bucket_idx >= 0 and bucket_idx < gs["bucket_count"]:
                gs["bucket_counts"][bucket_idx] += 1
            if bt_idx in eliminated:
                space.add_post_step_callback(_remove_ball_post, ball_shape)
            elif (0 <= bucket_idx < gs["bucket_count"] and gs["bucket_entries"][bucket_idx]["score"] == 0):
                # Spawn bucket: respawn this ball + spawn an extra of the same color
                balls_to_respawn.append(bt_idx)
                balls_to_respawn.append(bt_idx)
                space.add_post_step_callback(_remove_ball_post, ball_shape)
            else:
                BALL_TYPES[bt_idx]["score"] += bucket_score
                balls_to_respawn.append(bt_idx)
                space.add_post_step_callback(_remove_ball_post, ball_shape)

    def _remove_ball_post(space, shape):
        stuck_frames.pop(shape, None)
        if shape in balls:
            balls.remove(shape)
        if shape.body in space.bodies:
            space.remove(shape.body, shape)

    space.on_collision(BALL_CT, FLOOR_CT, begin=ball_hit_floor)

    # Initial balls
    for i in range(len(BALL_TYPES)):
        spawn_ball(space, balls, i, gs["maze"], gs["ball_radius"], gs["spawn_info"])

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.VIDEORESIZE:
                if not fullscreen:
                    screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

                elif event.key == pygame.K_F11:
                    fullscreen = not fullscreen
                    if fullscreen:
                        screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                    else:
                        screen = pygame.display.set_mode((gw, gh), pygame.RESIZABLE)

                elif event.key in range(pygame.K_1, pygame.K_9):
                    idx = event.key - pygame.K_1
                    if idx < len(BALL_TYPES):
                        selected_type = idx

                elif event.key == pygame.K_SPACE:
                    for i in range(len(BALL_TYPES)):
                        if len(balls) < gs["ball_limit"]:
                            spawn_ball(space, balls, i, gs["maze"], gs["ball_radius"], gs["spawn_info"])

                elif event.key == pygame.K_r:
                    for bt in BALL_TYPES:
                        bt["score"] = 0
                    eliminated.clear()
                    game_over = False
                    game_over_timer = 0
                    winner = None
                    reset_to_first_level()

                elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    speed_mult = min(speed_mult + 1, 5)
                elif event.key == pygame.K_MINUS:
                    speed_mult = max(speed_mult - 1, 1)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                win_w, win_h = screen.get_size()
                scale = min(win_w / gw, win_h / gh)
                offset_x = (win_w - int(gw * scale)) // 2
                offset_y = (win_h - int(gh * scale)) // 2
                mx = (event.pos[0] - offset_x) / scale
                my = (event.pos[1] - offset_y) / scale
                if gs["maze"]["maze_left"] < mx < gs["maze"]["maze_right"] and my < gs["maze"]["maze_top"] + 30:
                    if len(balls) < gs["ball_limit"]:
                        spawn_ball(space, balls, selected_type, gs["maze"], gs["ball_radius"], gs["spawn_info"])

        if game_over:
            balls_to_respawn.clear()

        # Respawn scored balls (skip eliminated colors)
        for bt_idx in balls_to_respawn:
            if bt_idx not in eliminated and len(balls) < gs["ball_limit"]:
                spawn_ball(space, balls, bt_idx, gs["maze"], gs["ball_radius"], gs["spawn_info"])
        balls_to_respawn.clear()

        # Elimination check
        if not game_over and len(balls) >= gs["ball_limit"]:
            active = [i for i in range(len(BALL_TYPES)) if i not in eliminated]
            if len(active) > 1:
                loser = min(active, key=lambda i: BALL_TYPES[i]["score"])
                eliminated.add(loser)
                for ball in balls[:]:
                    if ball.ball_type == loser:
                        remove_ball(space, ball, balls)
                        stuck_frames.pop(ball, None)

                # Switch to next level
                switch_to_next_level()

            active = [i for i in range(len(BALL_TYPES)) if i not in eliminated]
            if len(active) == 1:
                game_over = True
                game_over_timer = 0
                winner = active[0]
                wins[BALL_TYPES[winner]["name"]] = wins.get(BALL_TYPES[winner]["name"], 0) + 1
                save_wins(wins)

        # Auto-restart after game over
        if game_over:
            game_over_timer += 1
            if game_over_timer >= AUTO_RESTART_SECONDS * FPS:
                for bt in BALL_TYPES:
                    bt["score"] = 0
                eliminated.clear()
                game_over = False
                game_over_timer = 0
                winner = None
                reset_to_first_level()

        # Remove balls that fell way off screen
        for ball in balls[:]:
            if ball.body.position.y > gh + 100 or ball.body.position.x < -100 or ball.body.position.x > gw + 100:
                balls_to_respawn.append(ball.ball_type)
                remove_ball(space, ball, balls)
                stuck_frames.pop(ball, None)

        # Nudge stuck balls
        for ball in balls:
            speed = ball.body.velocity.length
            if speed < STUCK_SPEED:
                stuck_frames[ball] = stuck_frames.get(ball, 0) + 1
                if stuck_frames[ball] >= STUCK_THRESHOLD:
                    bx, by = ball.body.position.x, ball.body.position.y
                    best_dist = STUCK_PEG_RADIUS
                    best_peg = None
                    for peg in pegs:
                        px, py = peg.body.position.x, peg.body.position.y
                        d = math.hypot(bx - px, by - py)
                        if d < best_dist:
                            best_dist = d
                            best_peg = peg
                    if best_peg is not None:
                        px, py = best_peg.body.position.x, best_peg.body.position.y
                        with open(STUCK_PEG_LOG, "a") as f:
                            f.write(f"peg ({px:.0f}, {py:.0f}) dist={best_dist:.1f}\n")

                    ball.body.apply_impulse_at_local_point(
                        (random.uniform(-200, 200), random.uniform(-150, -50))
                    )
                    stuck_frames[ball] = 0
            else:
                stuck_frames[ball] = 0

        # Step physics
        dt = 1.0 / FPS
        for _ in range(speed_mult):
            space.step(dt)

        # --- Draw to game surface ---
        _frame_counter += 1
        for ball in balls:
            emit_sparkle_trail(ball)
        update_sparkle_trails()
        game_surface.fill((20, 20, 30))

        draw_maze_border(game_surface, gs["maze"])

        maze_bg = pygame.Rect(gs["maze"]["maze_left"], gs["maze"]["maze_top"],
                              gs["maze"]["maze_right"] - gs["maze"]["maze_left"],
                              gs["maze"]["maze_bottom"] - gs["maze"]["maze_top"])
        pygame.draw.rect(game_surface, (25, 25, 38), maze_bg)

        draw_buckets(game_surface, font, small_font, gs["bucket_counts"], gs["level"])

        for wall in walls:
            p1 = int(wall.a[0]), int(wall.a[1])
            p2 = int(wall.b[0]), int(wall.b[1])
            pygame.draw.line(game_surface, (100, 100, 120), p1, p2, 6)

        for plat in platforms:
            p1 = int(plat.a[0]), int(plat.a[1])
            p2 = int(plat.b[0]), int(plat.b[1])
            pygame.draw.line(game_surface, (130, 130, 150), p1, p2, 4)

        draw_pegs(game_surface, pegs)
        draw_sparkle_trails(game_surface)

        for ball in balls:
            draw_ball(game_surface, ball, gs["ball_radius"])

        total = sum(bt["score"] for bt in BALL_TYPES)
        ball_counts_dict = {}
        for b in balls:
            name = BALL_TYPES[b.ball_type]["name"]
            ball_counts_dict[name] = ball_counts_dict.get(name, 0) + 1
        draw_scoreboard(game_surface, font, small_font, total, ball_counts_dict, eliminated, gs["maze"])

        draw_speed_indicator(game_surface, small_font, speed_mult, gs["maze"])
        pending = sum(1 for bt in balls_to_respawn if bt not in eliminated)
        draw_ball_counter(game_surface, small_font, len(balls) + pending, gs["ball_limit"], gs["maze"])

        sel_text = small_font.render(f"Selected: {BALL_TYPES[selected_type]['name']}", True,
                                     BALL_TYPES[selected_type]["color"])
        game_surface.blit(sel_text, (gs["maze"]["maze_left"] + 200, gs["maze"]["maze_top"] - 25))

        # Level name display
        level_name = gs["level"].get("name", "")
        if level_name:
            name_surf = small_font.render(f"Level: {level_name}", True, (255, 255, 255))
            name_x = (gs["maze"]["maze_left"] + gs["maze"]["maze_right"]) // 2 - name_surf.get_width() // 2
            name_y = gs["maze"]["maze_top"] - 45
            game_surface.blit(name_surf, (name_x, name_y))

        if game_over and winner is not None:
            countdown = max(0, AUTO_RESTART_SECONDS - game_over_timer // FPS)
            draw_game_over(game_surface, font, winner, wins, countdown, gs["maze"])

        # Scale game surface to window/fullscreen
        screen.fill((0, 0, 0))
        win_w, win_h = screen.get_size()
        scale = min(win_w / gw, win_h / gh)
        scaled_w, scaled_h = int(gw * scale), int(gh * scale)
        offset_x = (win_w - scaled_w) // 2
        offset_y = (win_h - scaled_h) // 2
        scaled_surface = pygame.transform.smoothscale(game_surface, (scaled_w, scaled_h))
        screen.blit(scaled_surface, (offset_x, offset_y))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
