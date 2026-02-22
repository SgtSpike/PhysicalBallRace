import pygame
import pymunk
import random
import math
import os
import json

# --- Constants ---
WIDTH, HEIGHT = 800, 1000
MAZE_TOP = 80
MAZE_BOTTOM = HEIGHT - 60
MAZE_LEFT = 50
MAZE_RIGHT = WIDTH - 200
SCOREBOARD_X = MAZE_RIGHT + 20
FPS = 60
BALL_RADIUS = 8
GRAVITY = (0, 900)
BALL_LIMIT = 160
BUCKET_SCORES = [0, 10, 5, 3, 1, 3, 5, 10, 0]  # 0 = spawn bucket (+1 ball)
BUCKET_LABELS = ["+1", "10", "5", "3", "1", "3", "5", "10", "+1"]
BUCKET_COUNT = len(BUCKET_SCORES)
BUCKET_HEIGHT = 45
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


def point_to_segment_dist(px, py, ax, ay, bx, by):
    """Return the shortest distance from point (px,py) to segment (ax,ay)-(bx,by)."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    proj_x, proj_y = ax + t * dx, ay + t * dy
    return math.hypot(px - proj_x, py - proj_y)


# Platform definitions (shared between create_platforms and create_maze_pegs)
PLATFORM_DEFS = [
    ((MAZE_LEFT + 20, MAZE_TOP + 100), (MAZE_LEFT + 120, MAZE_TOP + 115)),
    ((MAZE_RIGHT - 120, MAZE_TOP + 100), (MAZE_RIGHT - 20, MAZE_TOP + 85)),
    ((MAZE_LEFT + 60, MAZE_TOP + 220), (MAZE_LEFT + 180, MAZE_TOP + 205)),
    ((MAZE_RIGHT - 180, MAZE_TOP + 220), (MAZE_RIGHT - 60, MAZE_TOP + 235)),
    ((MAZE_LEFT, MAZE_TOP + 340), (MAZE_LEFT + 140, MAZE_TOP + 355)),
    ((MAZE_RIGHT - 140, MAZE_TOP + 340), (MAZE_RIGHT, MAZE_TOP + 325)),
    ((MAZE_LEFT, MAZE_TOP + 520), (MAZE_LEFT + 160, MAZE_TOP + 535)),
    ((MAZE_RIGHT - 160, MAZE_TOP + 520), (MAZE_RIGHT, MAZE_TOP + 505)),
]

PEG_PLATFORM_CLEARANCE = 20

# Pegs identified from stuck_pegs.log as causing stuck balls
BLOCKED_PEGS = [
    (461, 194),
    (189, 268),
    (243, 268),
]
BLOCKED_PEG_RADIUS = 8  # how close a peg grid position must be to count as a match


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


def create_walls(space):
    """Create the boundary walls of the maze area."""
    walls = []
    thickness = 6
    wall_color = (100, 100, 120)

    wall_defs = [
        # Left wall (extends through bucket area)
        ((MAZE_LEFT, MAZE_TOP), (MAZE_LEFT, MAZE_BOTTOM)),
        # Right wall (extends through bucket area)
        ((MAZE_RIGHT, MAZE_TOP), (MAZE_RIGHT, MAZE_BOTTOM)),
    ]

    for p1, p2 in wall_defs:
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        seg = pymunk.Segment(body, p1, p2, thickness)
        seg.elasticity = 0.5
        seg.friction = 0.4
        seg.collision_type = WALL_CT
        seg.color = pygame.Color(*wall_color, 255)
        space.add(body, seg)
        walls.append(seg)

    return walls


def create_maze_pegs(space):
    """Create a peg-board maze with staggered rows of pegs."""
    pegs = []
    peg_radius = 5
    peg_color = (160, 160, 180)

    rows = 14
    usable_width = MAZE_RIGHT - MAZE_LEFT - 60
    cols = 10
    h_spacing = usable_width / (cols - 1)
    v_spacing = (MAZE_BOTTOM - MAZE_TOP - 80) / (rows - 1)

    for row in range(rows):
        offset = h_spacing / 2 if row % 2 == 1 else 0
        num_cols = cols - 1 if row % 2 == 1 else cols
        y = MAZE_TOP + 40 + row * v_spacing

        for col in range(num_cols):
            x = MAZE_LEFT + 30 + col * h_spacing + offset

            # Skip pegs in or near the bucket zone
            bucket_top = MAZE_BOTTOM - BUCKET_HEIGHT
            if y >= bucket_top - 15:
                continue

            # Skip pegs that are too close to any platform
            too_close = False
            for (p1, p2) in PLATFORM_DEFS:
                if point_to_segment_dist(x, y, p1[0], p1[1], p2[0], p2[1]) < PEG_PLATFORM_CLEARANCE:
                    too_close = True
                    break
            if too_close:
                continue

            # Skip pegs identified as problematic from stuck_pegs.log
            blocked = False
            for bpx, bpy in BLOCKED_PEGS:
                if math.hypot(x - bpx, y - bpy) < BLOCKED_PEG_RADIUS:
                    blocked = True
                    break
            if blocked:
                continue

            body = pymunk.Body(body_type=pymunk.Body.STATIC)
            body.position = (x, y)
            shape = pymunk.Circle(body, peg_radius)
            shape.elasticity = 0.6
            shape.friction = 0.3
            shape.collision_type = PEG_CT
            shape.color = pygame.Color(*peg_color, 255)
            space.add(body, shape)
            pegs.append(shape)

    return pegs


def create_platforms(space):
    """Create angled platforms/shelves for variety."""
    platforms = []
    platform_color = (130, 130, 150)
    thickness = 4

    for p1, p2 in PLATFORM_DEFS:
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        seg = pymunk.Segment(body, p1, p2, thickness)
        seg.elasticity = 0.4
        seg.friction = 0.5
        seg.collision_type = WALL_CT
        seg.color = pygame.Color(*platform_color, 255)
        space.add(body, seg)
        platforms.append(seg)

    return platforms


def create_buckets(space):
    """Create scoring buckets at the bottom of the maze with divider walls and floor sensors."""
    bucket_width = (MAZE_RIGHT - MAZE_LEFT) / BUCKET_COUNT
    bucket_top = MAZE_BOTTOM - BUCKET_HEIGHT
    dividers = []
    sensors = []
    thickness = 3

    # Divider walls between buckets (internal only, outer walls already exist)
    for i in range(1, BUCKET_COUNT):
        x = MAZE_LEFT + i * bucket_width
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        seg = pymunk.Segment(body, (x, bucket_top), (x, MAZE_BOTTOM), thickness)
        seg.elasticity = 0.3
        seg.friction = 0.4
        seg.collision_type = WALL_CT
        space.add(body, seg)
        dividers.append(seg)

    # Floor sensor per bucket
    for i in range(BUCKET_COUNT):
        left = MAZE_LEFT + i * bucket_width
        right = left + bucket_width
        body = pymunk.Body(body_type=pymunk.Body.STATIC)
        seg = pymunk.Segment(body, (left + thickness, MAZE_BOTTOM - 2), (right - thickness, MAZE_BOTTOM - 2), 4)
        seg.sensor = True
        seg.collision_type = FLOOR_CT
        seg.bucket_score = BUCKET_SCORES[i]
        seg.bucket_index = i
        space.add(body, seg)
        sensors.append(seg)

    # Solid floor under the buckets
    body = pymunk.Body(body_type=pymunk.Body.STATIC)
    seg = pymunk.Segment(body, (MAZE_LEFT, MAZE_BOTTOM), (MAZE_RIGHT, MAZE_BOTTOM), 4)
    seg.elasticity = 0.2
    seg.friction = 0.6
    seg.collision_type = WALL_CT
    space.add(body, seg)

    return dividers, sensors


def spawn_ball(space, balls, ball_type_index):
    """Spawn a ball at the top of the maze with slight random offset."""
    mass = 1
    moment = pymunk.moment_for_circle(mass, 0, BALL_RADIUS)
    body = pymunk.Body(mass, moment)
    center_x = (MAZE_LEFT + MAZE_RIGHT) / 2
    x = center_x + random.uniform(-120, 120)
    body.position = (x, MAZE_TOP + 15)
    body.velocity = (random.uniform(-30, 30), 0)

    shape = pymunk.Circle(body, BALL_RADIUS)
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


def draw_scoreboard(screen, font, small_font, total_score, ball_counts, eliminated):
    """Draw the scoreboard on the right side."""
    # Background panel
    panel_rect = pygame.Rect(SCOREBOARD_X - 5, 10, WIDTH - SCOREBOARD_X - 5, HEIGHT - 20)
    pygame.draw.rect(screen, (30, 30, 45), panel_rect, border_radius=8)
    pygame.draw.rect(screen, (80, 80, 100), panel_rect, 2, border_radius=8)

    # Title
    title = font.render("SCORES", True, (220, 220, 240))
    screen.blit(title, (SCOREBOARD_X + 10, 25))

    # Total
    total_text = font.render(f"Total: {total_score}", True, (255, 215, 0))
    screen.blit(total_text, (SCOREBOARD_X + 10, 55))

    # Divider
    pygame.draw.line(screen, (80, 80, 100),
                     (SCOREBOARD_X + 5, 85), (WIDTH - 15, 85), 1)

    # Individual scores - sorted by score descending
    y = 100
    row_height = 22
    sorted_types = sorted(enumerate(BALL_TYPES), key=lambda ib: ib[1]["score"], reverse=True)
    for idx, bt in sorted_types:
        is_elim = idx in eliminated

        # Color swatch (dimmed if eliminated)
        color = bt["color"] if not is_elim else tuple(c // 3 for c in bt["color"])
        swatch_y = y + row_height // 2 - 1
        pygame.draw.circle(screen, color, (SCOREBOARD_X + 16, swatch_y), 6)
        if bt["sparkly"]:
            # White ring for sparkly
            pygame.draw.circle(screen, (255, 255, 255), (SCOREBOARD_X + 16, swatch_y), 6, 1)
        else:
            pygame.draw.circle(screen, (200, 200, 200), (SCOREBOARD_X + 16, swatch_y), 6, 1)
        if is_elim:
            # X over swatch
            pygame.draw.line(screen, (180, 50, 50), (SCOREBOARD_X + 11, swatch_y - 5), (SCOREBOARD_X + 21, swatch_y + 5), 2)
            pygame.draw.line(screen, (180, 50, 50), (SCOREBOARD_X + 21, swatch_y - 5), (SCOREBOARD_X + 11, swatch_y + 5), 2)

        # Name and score
        count = ball_counts.get(bt['name'], 0)
        text_color = (100, 100, 110) if is_elim else (200, 200, 210)
        text = small_font.render(f"{bt['name']} ({count}): {bt['score']}", True, text_color)
        screen.blit(text, (SCOREBOARD_X + 28, y + 1))

        # Strikethrough line for eliminated
        if is_elim:
            tx = SCOREBOARD_X + 28
            tw = text.get_width()
            th_y = y + row_height // 2
            pygame.draw.line(screen, (180, 50, 50), (tx, th_y), (tx + tw, th_y), 2)

        y += row_height

    # Instructions
    y += 20
    pygame.draw.line(screen, (80, 80, 100),
                     (SCOREBOARD_X + 5, y), (WIDTH - 15, y), 1)
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
        screen.blit(text, (SCOREBOARD_X + 10, y))
        y += 22


def draw_maze_border(screen):
    """Draw a decorative border around the maze area."""
    border_rect = pygame.Rect(MAZE_LEFT - 8, MAZE_TOP - 8,
                              MAZE_RIGHT - MAZE_LEFT + 16, MAZE_BOTTOM - MAZE_TOP + 16)
    pygame.draw.rect(screen, (60, 60, 80), border_rect, 3, border_radius=4)


_frame_counter = 0
_sparkle_trails = []  # list of (x, y, color, frames_remaining)
SPARKLE_TRAIL_LIFETIME = 60  # frames (~1 second)
SPARKLE_TRAIL_INTERVAL = 3   # emit a particle every N frames


def draw_sparkle_trails(screen):
    """Draw and age sparkle trail particles."""
    for particle in _sparkle_trails:
        x, y, color, life = particle
        # Fade based on remaining life
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
    # Bright version of the ball's color
    bright = tuple(min(255, c + 100) for c in bt["color"])
    _sparkle_trails.append((
        x + random.uniform(-3, 3),
        y + random.uniform(-3, 3),
        bright,
        SPARKLE_TRAIL_LIFETIME
    ))


def draw_ball(screen, ball):
    """Draw a ball with a slight shading effect. Sparkly balls get animated sparkles."""
    global _frame_counter
    pos = int(ball.body.position.x), int(ball.body.position.y)
    bt = BALL_TYPES[ball.ball_type]
    color = bt["color"]

    # Main circle
    pygame.draw.circle(screen, color, pos, BALL_RADIUS)

    # Highlight
    highlight_color = tuple(min(255, c + 80) for c in color)
    highlight_pos = (pos[0] - 2, pos[1] - 2)
    pygame.draw.circle(screen, highlight_color, highlight_pos, BALL_RADIUS // 3)

    # Sparkle effect for sparkly balls
    if bt["sparkly"]:
        # White ring outline to distinguish from non-sparkly
        pygame.draw.circle(screen, (255, 255, 255), pos, BALL_RADIUS, 1)
        # Animated sparkle dots rotating around the ball
        num_sparkles = 3
        speed = 0.08
        base_angle = _frame_counter * speed + ball.ball_type * 0.7
        for i in range(num_sparkles):
            angle = base_angle + i * (2 * math.pi / num_sparkles)
            r = BALL_RADIUS + 2
            sx = pos[0] + int(r * math.cos(angle))
            sy = pos[1] + int(r * math.sin(angle))
            # Sparkle brightness pulses
            brightness = int(180 + 75 * math.sin(_frame_counter * 0.15 + i * 2.0))
            spark_color = (brightness, brightness, brightness)
            pygame.draw.circle(screen, spark_color, (sx, sy), 1)


def draw_pegs(screen, pegs):
    """Draw pegs with a subtle 3D effect."""
    for peg in pegs:
        pos = int(peg.body.position.x), int(peg.body.position.y)
        pygame.draw.circle(screen, (160, 160, 180), pos, 5)
        pygame.draw.circle(screen, (200, 200, 210), (pos[0] - 1, pos[1] - 1), 2)


def draw_speed_indicator(screen, font, speed_mult):
    """Draw current speed multiplier."""
    text = font.render(f"Speed: {speed_mult}x", True, (180, 180, 200))
    screen.blit(text, (MAZE_LEFT, MAZE_TOP - 25))


def draw_ball_counter(screen, font, num_balls):
    """Draw the current ball count vs limit."""
    color = (255, 80, 80) if num_balls >= BALL_LIMIT else (180, 180, 200)
    text = font.render(f"Balls: {num_balls}/{BALL_LIMIT}", True, color)
    screen.blit(text, (MAZE_LEFT + 350, MAZE_TOP - 25))


def draw_game_over(screen, font, winner_idx, wins, countdown_seconds):
    """Draw a game over overlay announcing the winner with wins history."""
    # Semi-transparent overlay
    overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    screen.blit(overlay, (0, 0))

    bt = BALL_TYPES[winner_idx]
    cx, cy = WIDTH // 2, HEIGHT // 2

    # Winner box (taller to fit wins)
    box_w, box_h = 400, 380
    box_rect = pygame.Rect(cx - box_w // 2, cy - box_h // 2, box_w, box_h)
    pygame.draw.rect(screen, (30, 30, 50), box_rect, border_radius=12)
    pygame.draw.rect(screen, bt["color"], box_rect, 3, border_radius=12)

    y_pos = cy - box_h // 2 + 20

    # "GAME OVER" title
    big_font = pygame.font.SysFont("consolas", 36, bold=True)
    title = big_font.render("GAME OVER", True, (220, 220, 240))
    screen.blit(title, (cx - title.get_width() // 2, y_pos))
    y_pos += 50

    # Winner announcement
    winner_text = font.render(f"{bt['name']} wins!", True, bt["color"])
    screen.blit(winner_text, (cx - winner_text.get_width() // 2, y_pos))
    y_pos += 30

    # Winner ball icon
    pygame.draw.circle(screen, bt["color"], (cx, y_pos + 10), 16)
    highlight = tuple(min(255, c + 80) for c in bt["color"])
    pygame.draw.circle(screen, highlight, (cx - 4, y_pos + 6), 5)
    y_pos += 35

    # Score
    score_text = font.render(f"Score: {bt['score']}", True, (255, 215, 0))
    screen.blit(score_text, (cx - score_text.get_width() // 2, y_pos))
    y_pos += 35

    # Divider
    pygame.draw.line(screen, (80, 80, 100), (cx - 150, y_pos), (cx + 150, y_pos), 1)
    y_pos += 10

    # Total wins
    wins_title = font.render("Total Wins", True, (200, 200, 220))
    screen.blit(wins_title, (cx - wins_title.get_width() // 2, y_pos))
    y_pos += 25

    small_font = pygame.font.SysFont("consolas", 15)
    sorted_wins = sorted(BALL_TYPES, key=lambda b: wins.get(b["name"], 0), reverse=True)
    for btype in sorted_wins:
        w = wins.get(btype["name"], 0)
        if w > 0:
            color = btype["color"]
            pygame.draw.circle(screen, color, (cx - 80, y_pos + 7), 6)
            win_text = small_font.render(f"{btype['name']}: {w}", True, (200, 200, 210))
            screen.blit(win_text, (cx - 68, y_pos))
            y_pos += 20

    # Countdown / restart hint
    y_pos = cy + box_h // 2 - 30
    countdown_text = font.render(f"Restarting in {countdown_seconds}s  (R to restart now)", True, (140, 140, 160))
    screen.blit(countdown_text, (cx - countdown_text.get_width() // 2, y_pos))


def draw_buckets(screen, font, small_font, bucket_counts):
    """Draw the scoring buckets at the bottom of the maze."""
    bucket_width = (MAZE_RIGHT - MAZE_LEFT) / BUCKET_COUNT
    bucket_top = MAZE_BOTTOM - BUCKET_HEIGHT

    for i in range(BUCKET_COUNT):
        left = MAZE_LEFT + i * bucket_width
        score = BUCKET_SCORES[i]
        label_text = BUCKET_LABELS[i]

        # Bucket background
        if score == 0:
            # Spawn bucket - green tint
            bg_color = (25, 50, 35)
        else:
            intensity = min(255, 25 + score * 6)
            bg_color = (intensity, intensity + 5, intensity + 15)
        rect = pygame.Rect(int(left) + 1, int(bucket_top) + 1,
                           int(bucket_width) - 2, BUCKET_HEIGHT - 2)
        pygame.draw.rect(screen, bg_color, rect)

        # Score label
        if score == 0:
            label_color = (100, 220, 130)
        elif score >= 10:
            label_color = (255, 215, 0)
        else:
            label_color = (200, 200, 220)
        label = font.render(label_text, True, label_color)
        lx = int(left + bucket_width / 2 - label.get_width() / 2)
        ly = int(bucket_top + BUCKET_HEIGHT / 2 - label.get_height() / 2)
        screen.blit(label, (lx, ly))

    # Divider lines
    for i in range(1, BUCKET_COUNT):
        x = int(MAZE_LEFT + i * bucket_width)
        pygame.draw.line(screen, (100, 100, 120), (x, int(bucket_top)), (x, MAZE_BOTTOM), 3)

    # Bottom line
    pygame.draw.line(screen, (100, 100, 120),
                     (MAZE_LEFT, MAZE_BOTTOM), (MAZE_RIGHT, MAZE_BOTTOM), 4)

    # Bucket hit counters below each bucket
    for i in range(BUCKET_COUNT):
        left = MAZE_LEFT + i * bucket_width
        count_label = small_font.render(str(bucket_counts[i]), True, (140, 140, 160))
        cx = int(left + bucket_width / 2 - count_label.get_width() / 2)
        screen.blit(count_label, (cx, MAZE_BOTTOM + 6))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("Physics Ball Race - Idle Game")
    game_surface = pygame.Surface((WIDTH, HEIGHT))
    fullscreen = False
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18, bold=True)
    small_font = pygame.font.SysFont("consolas", 15)

    # Physics space
    space = pymunk.Space()
    space.gravity = GRAVITY

    # Build the maze
    walls = create_walls(space)
    pegs = create_maze_pegs(space)
    platforms = create_platforms(space)
    bucket_dividers, bucket_sensors = create_buckets(space)

    # Ball tracking
    balls = []
    balls_to_respawn = []  # (ball_type_index,) tuples queued for respawn
    stuck_frames = {}  # shape -> consecutive frames with low speed
    bucket_counts = [0] * BUCKET_COUNT
    eliminated = set()  # indices of eliminated ball types
    game_over = False
    game_over_timer = 0  # frames since game over
    winner = None  # index of winning ball type
    wins = load_wins()
    selected_type = 0
    speed_mult = 1
    auto_spawn_timer = 0
    auto_spawn_interval = 90  # frames between auto-spawns

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
            if bucket_idx >= 0:
                bucket_counts[bucket_idx] += 1
            if bt_idx in eliminated:
                # Eliminated color - just remove, don't respawn
                space.add_post_step_callback(_remove_ball_post, ball_shape)
            elif bucket_idx == 0 or bucket_idx == BUCKET_COUNT - 1:
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
        spawn_ball(space, balls, i)

    global _frame_counter
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
                        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

                # Number keys to select ball type
                elif event.key in range(pygame.K_1, pygame.K_9):
                    idx = event.key - pygame.K_1
                    if idx < len(BALL_TYPES):
                        selected_type = idx

                # Space to add a wave of balls
                elif event.key == pygame.K_SPACE:
                    for i in range(len(BALL_TYPES)):
                        if len(balls) < BALL_LIMIT:
                            spawn_ball(space, balls, i)

                # R to reset scores
                elif event.key == pygame.K_r:
                    for bt in BALL_TYPES:
                        bt["score"] = 0
                    for i in range(BUCKET_COUNT):
                        bucket_counts[i] = 0
                    eliminated.clear()
                    game_over = False
                    game_over_timer = 0
                    winner = None
                    # Remove all balls and restart fresh
                    for ball in balls[:]:
                        remove_ball(space, ball, balls)
                    stuck_frames.clear()
                    balls_to_respawn.clear()
                    _sparkle_trails.clear()
                    for i in range(len(BALL_TYPES)):
                        spawn_ball(space, balls, i)

                # Speed controls
                elif event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS:
                    speed_mult = min(speed_mult + 1, 5)
                elif event.key == pygame.K_MINUS:
                    speed_mult = max(speed_mult - 1, 1)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Translate screen coords to game coords
                win_w, win_h = screen.get_size()
                scale = min(win_w / WIDTH, win_h / HEIGHT)
                offset_x = (win_w - int(WIDTH * scale)) // 2
                offset_y = (win_h - int(HEIGHT * scale)) // 2
                mx = (event.pos[0] - offset_x) / scale
                my = (event.pos[1] - offset_y) / scale
                if MAZE_LEFT < mx < MAZE_RIGHT and my < MAZE_TOP + 30:
                    if len(balls) < BALL_LIMIT:
                        spawn_ball(space, balls, selected_type)

        # Auto-spawn
        #auto_spawn_timer += 1
        #if auto_spawn_timer >= auto_spawn_interval:
        #    auto_spawn_timer = 0
        #    if len(balls) < BALL_LIMIT // 2:
        #        spawn_ball(space, balls, random.randint(0, len(BALL_TYPES) - 1))

        if game_over:
            balls_to_respawn.clear()

        # Respawn scored balls (skip eliminated colors)
        for bt_idx in balls_to_respawn:
            if bt_idx not in eliminated and len(balls) < BALL_LIMIT:
                spawn_ball(space, balls, bt_idx)
        balls_to_respawn.clear()

        # Elimination check: when ball limit reached, eliminate last place
        if not game_over and len(balls) >= BALL_LIMIT:
            # Find the lowest-scoring non-eliminated color
            active = [i for i in range(len(BALL_TYPES)) if i not in eliminated]
            if len(active) > 1:
                loser = min(active, key=lambda i: BALL_TYPES[i]["score"])
                eliminated.add(loser)
                # Remove all balls of the eliminated color
                for ball in balls[:]:
                    if ball.ball_type == loser:
                        remove_ball(space, ball, balls)
                        stuck_frames.pop(ball, None)

                # Despawn all but one ball of each remaining color
                active = [i for i in range(len(BALL_TYPES)) if i not in eliminated]
                for color_idx in active:
                    color_balls = [b for b in balls if b.ball_type == color_idx]
                    for ball in color_balls[1:]:
                        remove_ball(space, ball, balls)
                        stuck_frames.pop(ball, None)

            # Check for winner
            active = [i for i in range(len(BALL_TYPES)) if i not in eliminated]
            if len(active) == 1:
                game_over = True
                game_over_timer = 0
                winner = active[0]
                # Record the win
                wins[BALL_TYPES[winner]["name"]] = wins.get(BALL_TYPES[winner]["name"], 0) + 1
                save_wins(wins)

        # Auto-restart after game over
        if game_over:
            game_over_timer += 1
            if game_over_timer >= AUTO_RESTART_SECONDS * FPS:
                # Trigger reset
                for bt in BALL_TYPES:
                    bt["score"] = 0
                for i in range(BUCKET_COUNT):
                    bucket_counts[i] = 0
                eliminated.clear()
                game_over = False
                game_over_timer = 0
                winner = None
                for ball in balls[:]:
                    remove_ball(space, ball, balls)
                stuck_frames.clear()
                balls_to_respawn.clear()
                _sparkle_trails.clear()
                for i in range(len(BALL_TYPES)):
                    spawn_ball(space, balls, i)

        # Remove balls that fell way off screen
        for ball in balls[:]:
            if ball.body.position.y > HEIGHT + 100 or ball.body.position.x < -100 or ball.body.position.x > WIDTH + 100:
                balls_to_respawn.append(ball.ball_type)
                remove_ball(space, ball, balls)
                stuck_frames.pop(ball, None)

        # Nudge stuck balls and log the peg they're stuck at
        for ball in balls:
            speed = ball.body.velocity.length
            if speed < STUCK_SPEED:
                stuck_frames[ball] = stuck_frames.get(ball, 0) + 1
                if stuck_frames[ball] >= STUCK_THRESHOLD:
                    # Find nearest peg and log it
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

        # Step physics (multiple steps for speed multiplier)
        dt = 1.0 / FPS
        for _ in range(speed_mult):
            space.step(dt)

        # --- Draw to game surface ---
        _frame_counter += 1
        # Emit and age sparkle trail particles
        for ball in balls:
            emit_sparkle_trail(ball)
        update_sparkle_trails()
        game_surface.fill((20, 20, 30))

        # Maze border
        draw_maze_border(game_surface)

        # Maze background
        maze_bg = pygame.Rect(MAZE_LEFT, MAZE_TOP, MAZE_RIGHT - MAZE_LEFT, MAZE_BOTTOM - MAZE_TOP)
        pygame.draw.rect(game_surface, (25, 25, 38), maze_bg)

        # Draw buckets
        draw_buckets(game_surface, font, small_font, bucket_counts)

        # Draw walls and platforms
        for wall in walls:
            p1 = int(wall.a[0]), int(wall.a[1])
            p2 = int(wall.b[0]), int(wall.b[1])
            pygame.draw.line(game_surface, (100, 100, 120), p1, p2, 6)

        for plat in platforms:
            p1 = int(plat.a[0]), int(plat.a[1])
            p2 = int(plat.b[0]), int(plat.b[1])
            pygame.draw.line(game_surface, (130, 130, 150), p1, p2, 4)

        # Draw pegs
        draw_pegs(game_surface, pegs)

        # Draw sparkle trails (behind balls)
        draw_sparkle_trails(game_surface)

        # Draw balls
        for ball in balls:
            draw_ball(game_surface, ball)

        # Scoreboard
        total = sum(bt["score"] for bt in BALL_TYPES)
        ball_counts = {}
        for b in balls:
            name = BALL_TYPES[b.ball_type]["name"]
            ball_counts[name] = ball_counts.get(name, 0) + 1
        draw_scoreboard(game_surface, font, small_font, total, ball_counts, eliminated)

        # Speed indicator
        draw_speed_indicator(game_surface, small_font, speed_mult)

        # Ball counter
        draw_ball_counter(game_surface, small_font, len(balls))

        # Selected ball type indicator
        sel_text = small_font.render(f"Selected: {BALL_TYPES[selected_type]['name']}", True,
                                     BALL_TYPES[selected_type]["color"])
        game_surface.blit(sel_text, (MAZE_LEFT + 200, MAZE_TOP - 25))

        # Game over overlay
        if game_over and winner is not None:
            countdown = max(0, AUTO_RESTART_SECONDS - game_over_timer // FPS)
            draw_game_over(game_surface, font, winner, wins, countdown)

        # Scale game surface to window/fullscreen
        screen.fill((0, 0, 0))
        win_w, win_h = screen.get_size()
        scale = min(win_w / WIDTH, win_h / HEIGHT)
        scaled_w, scaled_h = int(WIDTH * scale), int(HEIGHT * scale)
        offset_x = (win_w - scaled_w) // 2
        offset_y = (win_h - scaled_h) // 2
        scaled_surface = pygame.transform.smoothscale(game_surface, (scaled_w, scaled_h))
        screen.blit(scaled_surface, (offset_x, offset_y))

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
