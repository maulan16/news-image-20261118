#!/usr/bin/env python3
"""World News front page -- Wednesday 18 November 2026.

A one-page newspaper summing up the day's four biggest world stories,
drawn procedurally with the Python standard library only.

Stories (all reported on 18 Nov 2026):
  1. DIPLOMACY -- Trump lands in Manila for Quad talks, ahead of APEC.
  2. WAR IN UKRAINE -- Ukraine strikes the Crimea bridge a second day
     as Russia pounds bridges in Kyiv.
  3. MIDDLE EAST -- Iran drones hit a US military radar in Bahrain;
     Kuwait reports drone interceptions.
  4. WEATHER -- Cyclone Akvan intensifies over the Bay of Bengal;
     Andhra Pradesh and Odisha on high alert.

Deterministic: no clock, no network, no random. The same bytes are
written on every run.
Run:  MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
"""
import math
import os
import struct
import zlib

W = H = 1024
pix = bytearray(W * H * 3)

# ---------------------------------------------------------------- palette
PAPER = (247, 243, 232)
INK = (18, 18, 18)
RED = (179, 32, 44)
GRAY = (90, 90, 90)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
NAVY = (16, 32, 64)


def _clamp(v):
    return 255 if v > 255 else (0 if v < 0 else v)


def set_px(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        pix[i], pix[i + 1], pix[i + 2] = c


def fill_rect(x0, y0, x1, y1, c):
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(W, int(x1)); y1 = min(H, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    r, g, b = c
    for y in range(y0, y1):
        base = y * W * 3
        for x in range(x0, x1):
            i = base + x * 3
            pix[i] = r; pix[i + 1] = g; pix[i + 2] = b


def vgrad(x0, y0, x1, y1, c0, c1):
    """Vertical gradient fill of a rect."""
    h = max(1, y1 - y0)
    for y in range(y0, y1):
        t = (y - y0) / h
        c = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
        fill_rect(x0, y, x1, y + 1, c)


def fill_circle(cx, cy, r, c):
    r = int(r)
    if r <= 0:
        return
    for dy in range(-r, r + 1):
        dx = int((r * r - dy * dy) ** 0.5)
        fill_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)


def add_circle(cx, cy, r, c, strength=1.0):
    """Additive soft glow disk."""
    r = int(r)
    if r <= 0:
        return
    r2 = r * r
    for dy in range(-r, r + 1):
        yy = cy + dy
        if yy < 0 or yy >= H:
            continue
        dx = int((r2 - dy * dy) ** 0.5)
        for x in range(cx - dx, cx + dx + 1):
            if 0 <= x < W:
                d2 = (x - cx) ** 2 + dy * dy
                f = (1.0 - d2 / r2) ** 2 * strength
                i = (yy * W + x) * 3
                pix[i] = _clamp(pix[i] + int(c[0] * f))
                pix[i + 1] = _clamp(pix[i + 1] + int(c[1] * f))
                pix[i + 2] = _clamp(pix[i + 2] + int(c[2] * f))


def line(x0, y0, x1, y1, c, w=1):
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy), 1)
    rad = max(1, w // 2)
    for i in range(steps + 1):
        t = i / steps
        fill_circle(int(x0 + dx * t), int(y0 + dy * t), rad, c)


def poly(pts, c):
    """Scanline polygon fill (even-odd)."""
    if len(pts) < 3:
        return
    ys = range(max(0, min(p[1] for p in pts)),
               min(H, max(p[1] for p in pts) + 1))
    n = len(pts)
    for y in ys:
        xs = []
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                if y1 != y0:
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            fill_rect(int(xs[k]), y, int(xs[k + 1]) + 1, y + 1, c)


def arc(cx, cy, r, a0, a1, c, w=2):
    steps = max(8, int(abs(a1 - a0) * r / 6))
    prev = None
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        p = (int(cx + r * math.cos(a)), int(cy + r * math.sin(a)))
        if prev:
            line(prev[0], prev[1], p[0], p[1], c, w)
        prev = p


def frame(x0, y0, x1, y1, c, w=3):
    fill_rect(x0, y0, x1, y0 + w, c)
    fill_rect(x0, y1 - w, x1, y1, c)
    fill_rect(x0, y0, x0 + w, y1, c)
    fill_rect(x1 - w, y0, x1, y1, c)


# ---------------------------------------------------------------- 5x7 font
# Each glyph: 7 rows, each a 5-bit int (bit 4 = leftmost column).
FONT = {
    'A': [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    'B': [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    'C': [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
    'D': [0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E],
    'E': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    'F': [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    'G': [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F],
    'H': [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    'I': [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    'J': [0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C],
    'K': [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    'L': [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    'M': [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
    'N': [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
    'O': [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    'P': [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
    'Q': [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D],
    'R': [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    'S': [0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E],
    'T': [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    'U': [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    'V': [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
    'W': [0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11],
    'X': [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
    'Y': [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    'Z': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
    '0': [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    '1': [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    '2': [0x0E, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1F],
    '3': [0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E],
    '4': [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    '5': [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    '6': [0x0E, 0x10, 0x10, 0x1E, 0x11, 0x11, 0x0E],
    '7': [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
    '8': [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
    '9': [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x01, 0x0E],
    ' ': [0, 0, 0, 0, 0, 0, 0],
    '.': [0, 0, 0, 0, 0, 0x0C, 0x0C],
    ',': [0, 0, 0, 0, 0x0C, 0x04, 0x08],
    ':': [0, 0x0C, 0x0C, 0, 0x0C, 0x0C, 0],
    ';': [0, 0x0C, 0x0C, 0, 0x0C, 0x04, 0x08],
    '!': [0x04, 0x04, 0x04, 0x04, 0x04, 0, 0x04],
    '?': [0x0E, 0x11, 0x01, 0x02, 0x04, 0, 0x04],
    '-': [0, 0, 0, 0x0E, 0, 0, 0],
    "'": [0x04, 0x04, 0x08, 0, 0, 0, 0],
    '(': [0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02],
    ')': [0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08],
    '/': [0x01, 0x02, 0x02, 0x04, 0x08, 0x08, 0x10],
    '&': [0x0C, 0x12, 0x14, 0x08, 0x15, 0x12, 0x0D],
    '+': [0, 0x04, 0x04, 0x0E, 0x04, 0x04, 0],
    '%': [0x19, 0x1A, 0x02, 0x04, 0x08, 0x0B, 0x13],
    '=': [0, 0, 0x1F, 0, 0x1F, 0, 0],
    '_': [0, 0, 0, 0, 0, 0, 0x1F],
    '"': [0x0A, 0x0A, 0, 0, 0, 0, 0],
    '*': [0, 0x15, 0x0E, 0x15, 0, 0, 0],
}


def text_w(s, txt):
    return len(txt) * 6 * s - s


def draw_text(x, y, s, c, txt):
    txt = txt.upper()
    cx = x
    for ch in txt:
        g = FONT.get(ch, FONT[' '])
        for row in range(7):
            bits = g[row]
            for col in range(5):
                if bits & (1 << (4 - col)):
                    fill_rect(cx + col * s, y + row * s,
                              cx + (col + 1) * s, y + (row + 1) * s, c)
        cx += 6 * s
    return cx


def center_text(cx, y, s, c, txt):
    draw_text(cx - text_w(s, txt) // 2, y, s, c, txt)


def wrap(txt, max_chars):
    words = txt.split(' ')
    lines, cur = [], ''
    for wd in words:
        nxt = wd if not cur else cur + ' ' + wd
        if len(nxt) <= max_chars:
            cur = nxt
        else:
            if cur:
                lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- illustrations
def draw_summit(x, y, w, h):
    """Four flags + plane: Trump lands in Manila for Quad talks."""
    vgrad(x, y, x + w, y + h, (168, 205, 232), (232, 242, 248))
    fill_circle(x + w - 52, y + 34, 22, (255, 214, 90))
    # ground
    fill_rect(x, y + h - 26, x + w, y + h, (74, 140, 78))
    fill_rect(x, y + h - 30, x + w, y + h - 26, (52, 110, 60))
    # plane (top right, side view silhouette)
    px, py = x + w - 150, y + 26
    poly([(px, py + 10), (px + 118, py + 4), (px + 132, py + 8),
          (px + 118, py + 12), (px + 30, py + 18), (px + 6, py + 16)],
         (38, 52, 84))
    poly([(px + 78, py + 4), (px + 96, py - 12), (px + 104, py - 12),
          (px + 92, py + 4)], (38, 52, 84))
    poly([(px + 8, py + 8), (px + 2, py - 6), (px + 10, py - 6),
          (px + 18, py + 8)], (38, 52, 84))
    line(px - 40, py + 14, px - 2, py + 12, (255, 255, 255), 2)
    # four flags
    fw, fh = 64, 40
    gap = (w - 4 * fw - 2 * 14) // 3
    fx = x + 14
    fy = y + h - 30 - fh - 46
    for kind in ('us', 'ph', 'jp', 'au'):
        # pole
        fill_rect(fx + fw // 2 - 2, fy - 8, fx + fw // 2 + 2, y + h - 30,
                  (60, 60, 60))
        fill_circle(fx + fw // 2, fy - 8, 4, (212, 175, 55))
        if kind == 'us':
            for s in range(7):
                fill_rect(fx, fy + s * 6, fx + fw, fy + (s + 1) * 6,
                          (178, 34, 52) if s % 2 == 0 else WHITE)
            fill_rect(fx, fy, fx + 27, fy + 21, (32, 48, 120))
            for r in range(3):
                for cc in range(3):
                    fill_circle(fx + 5 + cc * 9, fy + 4 + r * 7, 1, WHITE)
        elif kind == 'ph':
            fill_rect(fx, fy, fx + fw, fy + 20, (0, 82, 165))
            fill_rect(fx, fy + 20, fx + fw, fy + 40, (206, 17, 38))
            poly([(fx, fy), (fx, fy + 40), (fx + 28, fy + 20)], WHITE)
            fill_circle(fx + 8, fy + 20, 3, (255, 205, 0))
        elif kind == 'jp':
            fill_rect(fx, fy, fx + fw, fy + 40, WHITE)
            fill_circle(fx + 32, fy + 20, 10, (188, 0, 45))
        else:  # au
            fill_rect(fx, fy, fx + fw, fy + 40, (0, 36, 106))
            fill_circle(fx + 14, fy + 28, 3, WHITE)
            fill_circle(fx + 46, fy + 12, 2, WHITE)
            fill_circle(fx + 52, fy + 22, 2, WHITE)
            fill_circle(fx + 40, fy + 30, 2, WHITE)
            fill_circle(fx + 50, fy + 34, 2, WHITE)
            line(fx + 6, fy + 8, fx + 22, fy + 8, WHITE, 2)
            line(fx + 14, fy + 2, fx + 14, fy + 14, WHITE, 2)
        fx += fw + gap


def draw_bridge(x, y, w, h):
    """Crimea bridge under fire: deck, towers, explosion, smoke."""
    vgrad(x, y, x + w, y + h, (94, 104, 122), (52, 60, 78))
    # smoke clouds
    fill_circle(x + 90, y + 26, 17, (104, 110, 122))
    fill_circle(x + 150, y + 18, 13, (112, 118, 130))
    fill_circle(x + 350, y + 30, 15, (104, 110, 122))
    # water
    wy = y + h - 52
    fill_rect(x, wy, x + w, y + h, (24, 52, 88))
    for i in range(6):
        line(x + 20 + i * 74, wy + 12 + (i % 2) * 14,
             x + 66 + i * 74, wy + 12 + (i % 2) * 14, (120, 170, 210), 2)
    # bridge deck + towers
    dy = wy - 34
    fill_rect(x + 8, dy, x + w - 8, dy + 8, (28, 28, 30))
    for tx in (x + 96, x + w - 112):
        fill_rect(tx, dy - 66, tx + 14, dy, (40, 40, 44))
        fill_rect(tx - 6, dy - 66, tx + 20, dy - 60, (40, 40, 44))
        line(tx + 7, dy - 62, x + 14, dy, (200, 200, 200), 2)
        line(tx + 7, dy - 62, x + w - 14, dy, (200, 200, 200), 2)
        line(tx + 7, dy - 62, tx + 7, dy, (200, 200, 200), 2)
    # explosion on the deck (centre) -- jagged flame burst
    ex, ey = x + w // 2, dy - 6
    add_circle(ex, ey, 78, (255, 122, 26), 0.85)
    outer = []
    for i in range(16):
        a = math.radians(i * 22.5)
        r = 36 if i % 2 == 0 else 19
        outer.append((int(ex + r * math.cos(a)),
                      int(ey + r * math.sin(a) * 0.85)))
    poly(outer, (255, 140, 30))
    inner = []
    for i in range(12):
        a = math.radians(i * 30 + 15)
        r = 21 if i % 2 == 0 else 11
        inner.append((int(ex + r * math.cos(a)),
                      int(ey + r * math.sin(a) * 0.85)))
    poly(inner, (255, 205, 60))
    fill_circle(ex, ey, 9, (255, 240, 170))
    # smoke puffs rising
    fill_circle(ex - 30, ey - 48, 11, (58, 58, 62))
    fill_circle(ex + 2, ey - 60, 14, (48, 48, 52))
    fill_circle(ex + 28, ey - 42, 9, (66, 66, 70))
    fill_circle(ex + 12, ey - 72, 8, (56, 56, 60))
    # fire glow on the water
    add_circle(ex, wy + 18, 44, (255, 140, 40), 0.7)


def draw_drones(x, y, w, h):
    """Night over the Gulf: radar dish, drones, radar screen."""
    vgrad(x, y, x + w, y + h, (10, 22, 52), (26, 54, 104))
    # stars
    for sx, sy in ((30, 22), (90, 40), (150, 16), (210, 34), (280, 20),
                   (330, 44), (390, 26), (60, 62), (250, 58), (180, 52),
                   (420, 60), (120, 74)):
        fill_circle(x + sx, y + sy, 2, WHITE)
    # sea
    sy = y + h - 44
    fill_rect(x, sy, x + w, y + h, (8, 42, 66))
    line(x + 16, sy + 12, x + 120, sy + 12, (70, 130, 170), 2)
    line(x + 220, sy + 26, x + 330, sy + 26, (70, 130, 170), 2)
    # land strip + radar pedestal
    fill_rect(x + 30, sy - 6, x + 170, sy, (52, 58, 66))
    bx, by = x + 100, sy - 6
    fill_rect(bx - 8, by - 34, bx + 8, by, (120, 124, 130))
    # radar dish (parabola bowl)
    pts = []
    for i in range(-38, 39, 4):
        pts.append((bx + i, by - 34 - int(18 * (1 - (i / 38.0) ** 2))))
    poly(pts + [(bx + 38, by - 34), (bx - 38, by - 34)], (200, 204, 210))
    line(bx, by - 34, bx + 30, by - 66, (220, 224, 230), 3)
    # sweep beam
    line(bx, by - 48, bx + 88, by - 108, (90, 255, 140), 3)
    add_circle(bx + 88, by - 108, 16, (90, 255, 140), 0.6)
    # drones (dark silhouettes with rotor blur + red light)
    for dx, dy, sc in ((x + 250, y + 52, 1.0), (x + 320, y + 92, 0.85),
                       (x + 200, y + 110, 0.7)):
        s = int(16 * sc)
        fill_rect(dx - s, dy - 4, dx + s, dy + 4, (12, 12, 14))
        fill_rect(dx - 4, dy - s // 2, dx + 4, dy + s // 2, (12, 12, 14))
        line(dx - s - 8, dy - s // 2 - 2, dx + s + 8, dy - s // 2 - 2,
             (180, 180, 180), 2)
        line(dx - s - 8, dy + s // 2 + 2, dx + s + 8, dy + s // 2 + 2,
             (180, 180, 180), 2)
        fill_circle(dx, dy + 8, 3, (255, 60, 60))
    # radar screen (top-right)
    rx, ry, rr = x + w - 62, y + 46, 34
    fill_circle(rx, ry, rr, (6, 40, 18))
    frame(rx - rr, ry - rr, rx + rr + 1, ry + rr + 1, (60, 200, 110), 2)
    line(rx, ry, rx + 24, ry - 20, (90, 255, 140), 2)
    fill_circle(rx - 12, ry + 10, 3, (140, 255, 170))
    fill_circle(rx + 10, ry + 14, 2, (140, 255, 170))


def draw_cyclone(x, y, w, h):
    """Cyclone Akvan: spiral bands over the Bay of Bengal."""
    vgrad(x, y, x + w, y + h, (110, 132, 158), (64, 84, 118))
    # rain streaks
    for i in range(14):
        rx = x + 18 + i * 31
        line(rx, y + 12 + (i % 3) * 8, rx - 10, y + 34 + (i % 3) * 8,
             (190, 210, 230), 2)
    # sea
    sy = y + h - 46
    fill_rect(x, sy, x + w, y + h, (22, 62, 110))
    for i in range(5):
        arc(x + 40 + i * 84, sy + 14 + (i % 2) * 12, 18, math.pi, 2 * math.pi,
            (200, 225, 245), 2)
    # cyclone spiral (banded)
    cx, cy = x + w // 2 - 30, y + h // 2 - 6
    cols = [WHITE, (205, 232, 245), WHITE, (180, 215, 238)]
    steps = 220
    prev = None
    for i in range(steps + 1):
        a = (i / steps) * 4.6 * math.pi
        r = 8 + (96 - 8) * (i / steps)
        px = int(cx + r * math.cos(a))
        py = int(cy + r * math.sin(a) * 0.82)
        if prev:
            line(prev[0], prev[1], px, py, cols[(i // 14) % 4], 11)
        prev = (px, py)
    fill_circle(cx, cy, 13, (30, 48, 78))
    fill_circle(cx, cy, 13, (30, 48, 78))
    arc(cx, cy, 16, 0, 2 * math.pi, WHITE, 3)
    # coastline (India east coast, bottom-right)
    poly([(x + w - 150, y + h), (x + w - 118, sy + 6), (x + w - 84, sy + 18),
          (x + w - 52, sy + 10), (x + w - 20, sy + 22), (x + w, sy + 16),
          (x + w, y + h)], (196, 178, 130))
    # warning triangles on the coast
    for tx in (x + w - 128, x + w - 88, x + w - 48):
        poly([(tx, sy + 2), (tx + 9, sy + 18), (tx - 9, sy + 18)],
             (200, 30, 30))
        draw_text(tx - 2, sy + 8, 1, WHITE, '!')
    # HIGH ALERT strip
    fill_rect(x, y + h - 24, x + w, y + h, (179, 32, 44))
    center_text(x + w // 2, y + h - 19, 2, WHITE, 'HIGH ALERT')


# ---------------------------------------------------------------- layout
STORIES = [
    ("DIPLOMACY - ASIA", "TRUMP IN MANILA", "FOR QUAD TALKS",
     "US PRESIDENT OPENS ASIA TOUR; APEC",
     "SUMMIT WITH XI AND PUTIN FOLLOWS.", draw_summit),
    ("WAR IN UKRAINE", "UKRAINE STRIKES", "CRIMEA BRIDGE",
     "SECOND STRIKE IN TWO DAYS AS RUSSIAN",
     "MISSILES POUND BRIDGES IN KYIV.", draw_bridge),
    ("MIDDLE EAST", "IRAN DRONES HIT US", "RADAR IN BAHRAIN",
     "GULF ON ALERT AFTER DRONE ATTACK ON",
     "US RADAR; KUWAIT REPORTS INTERCEPTS.", draw_drones),
    ("WEATHER - INDIA", "CYCLONE AKVAN", "THREATENS INDIA",
     "BAY OF BENGAL STORM INTENSIFIES;",
     "ANDHRA AND ODISHA ON HIGH ALERT.", draw_cyclone),
]


def draw_panel(px, py, story):
    kicker, h1, h2, s1, s2, draw = story
    pw, ph = 480, 388
    fill_rect(px, py, px + pw, py + ph, WHITE)
    frame(px, py, px + pw, py + ph, INK, 3)
    draw_text(px + 16, py + 12, 3, RED, kicker)
    draw(px + 16, py + 38, 448, 210, )
    fill_rect(px + 16, py + 256, px + pw - 16, py + 258, (200, 200, 200))
    draw_text(px + 16, py + 268, 4, INK, h1)
    draw_text(px + 16, py + 302, 4, INK, h2)
    draw_text(px + 16, py + 342, 2, GRAY, s1)
    draw_text(px + 16, py + 362, 2, GRAY, s2)


def build():
    fill_rect(0, 0, W, H, PAPER)
    # masthead
    center_text(W // 2, 26, 9, INK, "WORLD NEWS")
    fill_rect(60, 100, W - 60, 106, RED)
    center_text(W // 2, 114, 4, INK, "WEDNESDAY, 18 NOVEMBER 2026")
    center_text(W // 2, 148, 2, GRAY, "FOUR STORIES THAT SHAPED THE DAY")
    # panels
    positions = [(20, 182), (524, 182), (20, 588), (524, 588)]
    for (px, py), story in zip(positions, STORIES):
        draw_panel(px, py, story)
    # footer
    fill_rect(60, 992, W - 60, 994, (180, 175, 160))
    center_text(W // 2, 1000, 2, GRAY,
                "18 NOVEMBER 2026 - THE WORLD IN ONE PAGE")
    # thin outer frame
    frame(8, 8, W - 8, H - 8, INK, 2)


# ---------------------------------------------------------------- PNG encode
def png_bytes():
    raw = bytearray()
    prev = bytearray(W * 3)
    for y in range(H):
        row = pix[y * W * 3:(y + 1) * W * 3]
        if y == 0:
            raw.append(0)
            raw += row
        else:
            raw.append(2)  # Up filter
            raw += bytes((b - p) & 0xFF for b, p in zip(row, prev))
        prev = row
    comp = zlib.compress(bytes(raw), 6)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp)
            + chunk(b"IEND", b""))


def main():
    build()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    data = png_bytes()
    with open(os.path.join(out_dir, "entry.png"), "wb") as fh:
        fh.write(data)


if __name__ == "__main__":
    main()
