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
Rendering is supersampled 3x (3072x3072) and box-downsampled to
1024x1024, so text and shapes get smooth anti-aliased edges instead of
the blocky pixel look. The harness is standard-library only, so no
Pillow or external fonts are used.
Run:  MAKEFUN_OUTPUT_DIR=out python3 -P -s main.py
"""
import math
import os
import struct
import zlib

# Supersampling: render at 3x, then box-downsample to 1024 for smooth
# anti-aliased edges.
SS = 3
W = H = 1024
SW = SH = W * SS
pix = bytearray(SW * SH * 3)

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


def _blit_rect(x0, y0, x1, y1, c):
    """Fill a rect in supersampled coordinates (direct pixel writes)."""
    x0 = max(0, int(x0)); y0 = max(0, int(y0))
    x1 = min(SW, int(x1)); y1 = min(SH, int(y1))
    if x1 <= x0 or y1 <= y0:
        return
    row = bytes(c) * (x1 - x0)
    for y in range(y0, y1):
        base = (y * SW + x0) * 3
        pix[base:base + len(row)] = row


def set_px(x, y, c):
    _blit_rect(int(x * SS), int(y * SS),
              int((x + 1) * SS), int((y + 1) * SS), c)


def fill_rect(x0, y0, x1, y1, c):
    """Fill a rect in logical (1024) coordinates; scaled to SS inside."""
    _blit_rect(int(x0 * SS), int(y0 * SS),
              int(x1 * SS), int(y1 * SS), c)


def vgrad(x0, y0, x1, y1, c0, c1):
    """Vertical gradient fill of a rect (smooth: one step per subpixel row)."""
    y0s, y1s = int(y0 * SS), int(y1 * SS)
    x0s, x1s = int(x0 * SS), int(x1 * SS)
    h = max(1, y1s - y0s)
    for sy in range(max(0, y0s), min(SH, y1s)):
        t = (sy - y0s) / h
        c = tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))
        _blit_rect(x0s, sy, x1s, sy + 1, c)


def fill_circle(cx, cy, r, c):
    """Filled circle; edge computed at supersampled resolution."""
    cx, cy, r = int(cx * SS), int(cy * SS), int(r * SS)
    if r <= 0:
        return
    for dy in range(-r, r + 1):
        dx = int((r * r - dy * dy) ** 0.5)
        _blit_rect(cx - dx, cy + dy, cx + dx + 1, cy + dy + 1, c)


def add_circle(cx, cy, r, c, strength=1.0):
    """Additive soft glow disk (computed at supersampled resolution)."""
    cx, cy, r = int(cx * SS), int(cy * SS), int(r * SS)
    if r <= 0:
        return
    r2 = r * r
    for dy in range(-r, r + 1):
        yy = cy + dy
        if yy < 0 or yy >= SH:
            continue
        dx = int((r2 - dy * dy) ** 0.5)
        for x in range(cx - dx, cx + dx + 1):
            if 0 <= x < SW:
                d2 = (x - cx) ** 2 + dy * dy
                f = (1.0 - d2 / r2) ** 2 * strength
                i = (yy * SW + x) * 3
                pix[i] = _clamp(pix[i] + int(c[0] * f))
                pix[i + 1] = _clamp(pix[i + 1] + int(c[1] * f))
                pix[i + 2] = _clamp(pix[i + 2] + int(c[2] * f))


def line(x0, y0, x1, y1, c, w=1):
    dx, dy = x1 - x0, y1 - y0
    steps = max(int(abs(dx)), int(abs(dy)), 1)
    rad = max(1, w // 2)
    for i in range(steps + 1):
        t = i / steps
        fill_circle(x0 + dx * t, y0 + dy * t, rad, c)


def poly(pts, c):
    """Scanline polygon fill (even-odd); edges computed at SS resolution."""
    if len(pts) < 3:
        return
    spts = [(p[0] * SS, p[1] * SS) for p in pts]
    ys = range(max(0, int(min(p[1] for p in spts))),
               min(SH, int(max(p[1] for p in spts)) + 1))
    n = len(spts)
    for y in ys:
        xs = []
        for i in range(n):
            x0, y0 = spts[i]
            x1, y1 = spts[(i + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                if y1 != y0:
                    xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            _blit_rect(int(xs[k]), y, int(xs[k + 1]) + 1, y + 1, c)


def arc(cx, cy, r, a0, a1, c, w=2):
    steps = max(8, int(abs(a1 - a0) * r / 6))
    prev = None
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        p = (cx + r * math.cos(a), cy + r * math.sin(a))
        if prev:
            line(prev[0], prev[1], p[0], p[1], c, w)
        prev = p


def frame(x0, y0, x1, y1, c, w=3):
    fill_rect(x0, y0, x1, y0 + w, c)
    fill_rect(x0, y1 - w, x1, y1, c)
    fill_rect(x0, y0, x0 + w, y1, c)
    fill_rect(x1 - w, y0, x1, y1, c)


# ---------------------------------------------------------------- stroke font
# Single-stroke vector font on a 10x12 grid (x 0..10, y 0..12, y=0 top).
# Each glyph is a list of strokes; a stroke is a list of (x, y) points.
# A one-point stroke is a dot. Strokes are drawn with the anti-aliased
# line primitive, so letterforms are smooth curves and diagonals instead
# of the blocky 5x7 bitmap rectangles. Cap height is 12 grid units.
def _arc(cx, cy, rx, ry, a0, a1, n=10):
    """Points along an ellipse arc. Angles in degrees, y-down
    (0=east, 90=south, 180=west, 270=north); goes from a0 to a1."""
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((round(cx + rx * math.cos(a), 2),
                    round(cy + ry * math.sin(a), 2)))
    return pts


STROKES = {
    'A': [[(1, 12), (5, 0), (9, 12)], [(3, 8), (7, 8)]],
    'B': [[(1, 0), (1, 12)],
          [(1, 0), (6, 0)] + _arc(6, 3, 2.5, 3, -90, 90, 8) + [(6, 6), (1, 6)],
          [(1, 6), (6, 6)] + _arc(6, 9, 2.5, 3, -90, 90, 8) + [(6, 12), (1, 12)]],
    'C': [_arc(5, 6, 4.5, 6, 50, 310, 14)],
    'D': [[(1, 0), (1, 12)],
          [(1, 0), (6, 0)] + _arc(6, 6, 3, 6, -90, 90, 10) + [(6, 12), (1, 12)]],
    'E': [[(1, 0), (1, 12)], [(1, 0), (9, 0)], [(1, 6), (7, 6)], [(1, 12), (9, 12)]],
    'F': [[(1, 0), (1, 12)], [(1, 0), (9, 0)], [(1, 6), (7, 6)]],
    'G': [_arc(5, 6, 4.5, 6, 50, 310, 14), [(9, 6), (5, 6), (5, 10)]],
    'H': [[(1, 0), (1, 12)], [(9, 0), (9, 12)], [(1, 6), (9, 6)]],
    'I': [[(2, 0), (8, 0)], [(5, 0), (5, 12)], [(2, 12), (8, 12)]],
    'J': [[(8, 0), (8, 10)] + _arc(5, 10, 3, 2, 0, 180, 8) + [(2, 8)]],
    'K': [[(1, 0), (1, 12)], [(9, 0), (1, 6)], [(3.5, 7.5), (9, 12)]],
    'L': [[(1, 0), (1, 12)], [(1, 12), (9, 12)]],
    'M': [[(1, 12), (1, 0), (5, 8), (9, 0), (9, 12)]],
    'N': [[(1, 12), (1, 0), (9, 12), (9, 0)]],
    'O': [_arc(5, 6, 4.5, 6, 0, 360, 16)],
    'P': [[(1, 0), (1, 12)],
          [(1, 0), (6, 0)] + _arc(6, 3, 2.5, 3, -90, 90, 8) + [(6, 6), (1, 6)]],
    'Q': [_arc(5, 6, 4.5, 6, 0, 360, 16), [(7, 9), (10, 12)]],
    'R': [[(1, 0), (1, 12)],
          [(1, 0), (6, 0)] + _arc(6, 3, 2.5, 3, -90, 90, 8) + [(6, 6), (1, 6)],
          [(4.5, 6), (9, 12)]],
    'S': [_arc(5, 3, 4, 3, 330, 90, 12), _arc(5, 9, 4, 3, 270, 585, 12)],
    'T': [[(1, 0), (9, 0)], [(5, 0), (5, 12)]],
    'U': [[(1, 0), (1, 8)] + _arc(5, 8, 4, 4, 180, 0, 10) + [(9, 8), (9, 0)]],
    'V': [[(1, 0), (5, 12), (9, 0)]],
    'W': [[(1, 0), (2.5, 12), (5, 4), (7.5, 12), (9, 0)]],
    'X': [[(1, 0), (9, 12)], [(9, 0), (1, 12)]],
    'Y': [[(1, 0), (5, 6), (9, 0)], [(5, 6), (5, 12)]],
    'Z': [[(1, 0), (9, 0), (1, 12), (9, 12)]],
    '0': [_arc(5, 6, 3.5, 6, 0, 360, 14), [(3, 3), (7, 9)]],
    '1': [[(3, 3), (6, 0)], [(5, 0), (5, 12)], [(2, 12), (8, 12)]],
    '2': [_arc(5, 4, 3.5, 4, 180, 360, 10), [(8.5, 4), (1, 12)], [(1, 12), (9, 12)]],
    '3': [[(2, 0), (6, 0), (8, 2), (8, 4), (5, 6)],
          [(5, 6), (8, 6), (8, 10), (6, 12), (2, 12)]],
    '4': [[(8, 0), (1, 8)], [(1, 8), (9, 8)], [(7, 0), (7, 12)]],
    '5': [[(9, 0), (1, 0), (1, 6)],
          [(1, 6), (6, 6), (8, 7), (8, 10), (6, 12), (2, 12)]],
    '6': [[(8, 0), (5, 1), (3, 4), (3, 6)], _arc(5, 8, 3.5, 4, 0, 360, 14)],
    '7': [[(1, 0), (9, 0)], [(9, 0), (3, 12)]],
    '8': [_arc(5, 3.5, 3, 3.5, 0, 360, 12), _arc(5, 8.5, 3.5, 3.5, 0, 360, 12)],
    '9': [_arc(5, 4, 3.5, 4, 0, 360, 14), [(8, 4), (8, 12)]],
    ' ': [],
    '.': [[(5, 11)]],
    ',': [[(5, 10), (4.5, 12), (3.5, 14)]],
    ':': [[(5, 4)], [(5, 10)]],
    ';': [[(5, 4)], [(5, 9), (4.5, 11), (3.5, 13)]],
    '!': [[(5, 0), (5, 8)], [(5, 11)]],
    '?': [_arc(5, 3.5, 3.5, 3.5, 222, 402, 10),
          [(7.7, 5.8), (5, 7), (5, 8.5)], [(5, 11)]],
    '-': [[(1, 6), (9, 6)]],
    "'": [[(6, 0), (5, 3)]],
    '(': [[(7, 0), (5, 2), (4, 6), (5, 10), (7, 12)]],
    ')': [[(3, 0), (5, 2), (6, 6), (5, 10), (3, 12)]],
    '/': [[(8, 0), (2, 12)]],
    '&': [[(8, 1), (5, 0), (2, 2), (2, 5), (5, 7)],
          [(5, 7), (8, 5), (8, 8), (5, 11), (2, 10)]],
    '+': [[(5, 2), (5, 10)], [(1, 6), (9, 6)]],
    '%': [[(8, 0), (2, 12)], [(3, 3)], [(7, 9)]],
    '=': [[(1, 4), (9, 4)], [(1, 8), (9, 8)]],
    '_': [[(1, 12), (9, 12)]],
    '"': [[(3, 0), (3, 3)], [(7, 0), (7, 3)]],
    '*': [[(5, 1), (5, 11)], [(1, 4), (9, 8)], [(9, 4), (1, 8)]],
}

TRACK = 2.0  # tracking between glyphs, in grid units


def _glyph_w(ch):
    if ch == ' ':
        return 4.0
    g = STROKES.get(ch)
    if not g:
        return 4.0
    return max((p[0] for st in g for p in st), default=0.0)


def text_w(s, txt):
    """Pixel width of txt at scale s (cap height 7*s)."""
    sc = (7 * s) / 12.0
    tot = 0.0
    for ch in txt.upper():
        tot += (_glyph_w(ch) + TRACK) * sc
    if tot > 0:
        tot -= TRACK * sc
    return int(round(tot))


def draw_text(x, y, s, c, txt):
    """Draw txt with cap top at y, cap height 7*s. Returns end x."""
    txt = txt.upper()
    em = 7 * s
    sc = em / 12.0
    sw = max(1, int(round(em * 0.15)))
    cx = float(x)
    for ch in txt:
        g = STROKES.get(ch)
        if g:
            for st in g:
                if len(st) == 1:
                    px, py = st[0]
                    fill_circle(cx + px * sc, y + py * sc,
                                max(sw * 0.6, 1.0), c)
                else:
                    prev = None
                    for (gx, gy) in st:
                        p = (cx + gx * sc, y + gy * sc)
                        if prev is not None:
                            line(prev[0], prev[1], p[0], p[1], c, sw)
                        prev = p
        cx += (_glyph_w(ch) + TRACK) * sc
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
def downsample():
    """Box-filter the 3x buffer down to 1024x1024 (anti-aliasing)."""
    out = bytearray(W * H * 3)
    n = SS * SS
    src = pix
    for oy in range(H):
        for ox in range(W):
            r = g = b = 0
            for dy in range(SS):
                base = ((oy * SS + dy) * SW + ox * SS) * 3
                for dx in range(SS):
                    i = base + dx * 3
                    r += src[i]; g += src[i + 1]; b += src[i + 2]
            o = (oy * W + ox) * 3
            out[o] = r // n; out[o + 1] = g // n; out[o + 2] = b // n
    return bytes(out)


def png_bytes():
    data = downsample()
    raw = bytearray()
    prev = bytearray(W * 3)
    for y in range(H):
        row = data[y * W * 3:(y + 1) * W * 3]
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
