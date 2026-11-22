#!/usr/bin/env python3
"""One ripe strawberry, rendered procedurally with the Python standard library.

Writes /output/entry.png: a 1024x1024 RGB PNG, deterministic byte for byte.
No third-party packages, no network, no clock, no unseeded randomness.
"""

import binascii
import math
import os
import random
import struct
import zlib

W = 1024
H = 1024

buf = bytearray(W * H * 3)


def clamp255(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(v)


def put(x, y, r, g, b):
    i = (y * W + x) * 3
    buf[i] = clamp255(r)
    buf[i + 1] = clamp255(g)
    buf[i + 2] = clamp255(b)


def blend(x, y, r, g, b, a):
    if a <= 0.0:
        return
    if a > 1.0:
        a = 1.0
    i = (y * W + x) * 3
    ia = 1.0 - a
    buf[i] = clamp255(buf[i] * ia + r * a)
    buf[i + 1] = clamp255(buf[i + 1] * ia + g * a)
    buf[i + 2] = clamp255(buf[i + 2] * ia + b * a)


# ---------------------------------------------------------------- background
def paint_background():
    cx, cy = 512.0, 420.0
    dx2 = [(x - cx) * (x - cx) for x in range(W)]
    for y in range(H):
        dy = y - cy
        dy2 = dy * dy
        row = y * W * 3
        # table sheen low in the frame
        table = 0.0
        if y > 760:
            table = min(1.0, (y - 760) / 120.0)
        for x in range(W):
            d = math.sqrt(dx2[x] + dy2) / 760.0
            if d > 1.0:
                d = 1.0
            glow = (1.0 - d) ** 2.2
            r = 10 + 58 * glow + 14 * table * glow
            g = 7 + 30 * glow + 8 * table * glow
            b = 9 + 22 * glow + 6 * table * glow
            i = row + x * 3
            buf[i] = clamp255(r)
            buf[i + 1] = clamp255(g)
            buf[i + 2] = clamp255(b)


def paint_shadow():
    cx, cy, rx, ry = 512.0, 852.0, 300.0, 62.0
    x0, x1 = int(cx - rx), int(cx + rx)
    y0, y1 = int(cy - ry), int(cy + ry)
    for y in range(y0, y1):
        for x in range(x0, x1):
            u = (x - cx) / rx
            v = (y - cy) / ry
            q = u * u + v * v
            if q < 1.0:
                a = 0.55 * (1.0 - q) ** 1.5
                blend(x, y, 2, 1, 2, a)


def paint_halo():
    cx, cy, rx, ry = 512.0, 560.0, 430.0, 420.0
    x0, x1 = int(cx - rx), int(cx + rx)
    y0, y1 = int(cy - ry), int(cy + ry)
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            u = (x - cx) / rx
            v = (y - cy) / ry
            q = u * u + v * v
            if q < 1.0:
                a = 0.16 * (1.0 - q) ** 2
                blend(x, y, 120, 40, 30, a)


# ---------------------------------------------------------------- strawberry
TOP_Y = 296.0
BOT_Y = 838.0
MAX_HW = 292.0


def half_width(t):
    s = math.sin(math.pi * (0.04 + 0.96 * t))
    if s < 0.0:
        s = 0.0
    return MAX_HW * (s ** 0.5) * (1.0 - 0.22 * t)


def center_x(t):
    return 512.0 + 10.0 * math.sin(t * math.pi)


def paint_berry():
    # light from upper-left-front
    lx, ly, lz = -0.42, -0.52, 0.74
    inv = 1.0 / math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx * inv, ly * inv, lz * inv
    y0, y1 = int(TOP_Y), int(BOT_Y)
    for y in range(y0, y1):
        t = (y - TOP_Y) / (BOT_Y - TOP_Y)
        hw = half_width(t)
        if hw < 1.0:
            continue
        cx = center_x(t)
        x0, x1 = int(cx - hw), int(cx + hw)
        # vertical colour drift: tip a touch warmer/lighter
        tip = 0.0
        if t > 0.78:
            tip = (t - 0.78) / 0.22
        for x in range(x0, x1):
            u = (x - cx) / hw
            if u < -1.0 or u > 1.0:
                continue
            z2 = 1.0 - u * u
            z = math.sqrt(z2) if z2 > 0.0 else 0.0
            nx = u * 0.95
            ny = (t - 0.38) * 0.85
            nz = z
            nl = math.sqrt(nx * nx + ny * ny + nz * nz)
            if nl == 0.0:
                continue
            nx, ny, nz = nx / nl, ny / nl, nz / nl
            diff = nx * lx + ny * ly + nz * lz
            if diff < 0.0:
                diff = 0.0
            # specular: reflect light about normal, view along +z
            rxv = 2.0 * diff * nx - lx
            ryv = 2.0 * diff * ny - ly
            rzv = 2.0 * diff * nz - lz
            spec = rzv if rzv > 0.0 else 0.0
            gloss = (spec ** 50) * 0.78 + (spec ** 8) * 0.20
            shade = 0.30 + 0.85 * diff
            roundness = 0.62 + 0.38 * z
            base_r = 196 + 34 * tip
            base_g = 26 + 42 * tip
            base_b = 34 + 10 * tip
            r = base_r * shade * roundness + 255 * gloss
            g = base_g * shade * roundness + 245 * gloss
            b = base_b * shade * roundness + 240 * gloss
            put(x, y, r, g, b)


def berry_point(rng):
    t = 0.06 + 0.88 * rng.random()
    hw = half_width(t)
    u = (rng.random() * 2.0 - 1.0) * 0.86
    x = center_x(t) + u * hw
    y = TOP_Y + t * (BOT_Y - TOP_Y)
    return x, y, u, t


def paint_seeds():
    rng = random.Random(20261122)
    placed = []
    cell = 30
    grid = {}
    tries = 0
    while len(placed) < 120 and tries < 4000:
        tries += 1
        x, y, u, t = berry_point(rng)
        gx, gy = int(x // cell), int(y // cell)
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (px, py) in grid.get((gx + dx, gy + dy), ()):
                    if (px - x) ** 2 + (py - y) ** 2 < 26 ** 2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if not ok:
            continue
        grid.setdefault((gx, gy), []).append((x, y))
        placed.append((x, y))
    for (x, y) in placed:
        # pit shadow
        for yy in range(int(y - 8), int(y + 9)):
            for xx in range(int(x - 6), int(x + 7)):
                if 0 <= xx < W and 0 <= yy < H:
                    q = ((xx - x) / 5.0) ** 2 + ((yy - y) / 7.5) ** 2
                    if q < 1.0:
                        blend(xx, yy, 105, 8, 16, 0.55 * (1.0 - q))
        # seed body
        for yy in range(int(y - 6), int(y + 7)):
            for xx in range(int(x - 4), int(x + 5)):
                if 0 <= xx < W and 0 <= yy < H:
                    q = ((xx - x) / 3.1) ** 2 + ((yy - y) / 5.2) ** 2
                    if q < 1.0:
                        lit = 1.0 - 0.35 * q
                        blend(xx, yy, 248 * lit, 226 * lit, 150 * lit, 0.92)


def paint_droplets():
    rng = random.Random(77031)
    drops = []
    tries = 0
    while len(drops) < 16 and tries < 800:
        tries += 1
        x, y, u, t = berry_point(rng)
        r = 5.0 + rng.random() * 11.0
        if all((x - px) ** 2 + (y - py) ** 2 > (r + pr + 14) ** 2
               for (px, py, pr) in drops):
            drops.append((x, y, r))
    for (x, y, r) in drops:
        ri = int(r) + 2
        for yy in range(int(y - ri), int(y + ri + 1)):
            for xx in range(int(x - ri), int(x + ri + 1)):
                if not (0 <= xx < W and 0 <= yy < H):
                    continue
                dx = (xx - x) / r
                dy = (yy - y) / r
                q = dx * dx + dy * dy
                if q >= 1.0:
                    continue
                # glassy body: brighten toward pale blue-white
                a = 0.17 * (1.0 - q)
                blend(xx, yy, 215, 238, 250, a)
                # dark refraction crescent at the bottom rim
                if dy > 0.45:
                    blend(xx, yy, 90, 10, 18, 0.25 * (dy - 0.45))
                # specular sparkle upper-left
                sx = dx + 0.38
                sy = dy + 0.38
                s = math.exp(-(sx * sx + sy * sy) * 14.0)
                if s > 0.02:
                    blend(xx, yy, 255, 255, 255, min(1.0, s * 1.2))


# ---------------------------------------------------------------- leaves
def paint_leaf(ox, oy, angle_deg, length, width, dark):
    ang = math.radians(angle_deg)
    ca, sa = math.cos(ang), math.sin(ang)
    ext = int(length) + 4
    x0, x1 = int(ox - ext), int(ox + ext)
    y0, y1 = int(oy - ext), int(oy + ext)
    for y in range(max(0, y0), min(H, y1)):
        for x in range(max(0, x0), min(W, x1)):
            dx = x - ox
            dy = y - oy
            s = (dx * ca + dy * sa) / length
            if s < 0.0 or s > 1.0:
                continue
            p = (-dx * sa + dy * ca)
            hw = width * (math.sin(math.pi * (s ** 0.75)) ** 0.8)
            if hw < 0.5 or abs(p) > hw:
                continue
            edge = abs(p) / hw
            vein = 1.0 - min(1.0, abs(p) / 3.0)
            base = (34, 118, 44) if not dark else (22, 84, 32)
            tipc = (86, 186, 78) if not dark else (48, 130, 52)
            f = s * 0.8 + 0.1
            r = base[0] + (tipc[0] - base[0]) * f
            g = base[1] + (tipc[1] - base[1]) * f
            b = base[2] + (tipc[2] - base[2]) * f
            shade = (1.0 - 0.35 * edge) * (1.0 - 0.30 * vein)
            put(x, y, r * shade, g * shade, b * shade)


def paint_calyx_and_stem():
    ox, oy = 512.0, 302.0
    # back leaves first (darker), then front leaves
    paint_leaf(ox, oy, -115, 205, 52, True)
    paint_leaf(ox, oy, -65, 215, 54, True)
    paint_leaf(ox, oy, 180 + 65, 200, 50, True)
    paint_leaf(ox, oy, -150, 185, 48, False)
    paint_leaf(ox, oy, -90, 175, 50, False)
    paint_leaf(ox, oy, -30, 190, 50, False)
    paint_leaf(ox, oy, 180 + 30, 180, 48, False)
    paint_leaf(ox, oy, 180 + 90, 165, 46, False)
    # stem: short tapered stroke upward
    for i in range(70):
        f = i / 69.0
        x = 512 + 26 * f
        y = 300 - 66 * f
        rad = 7.0 * (1.0 - 0.45 * f)
        for yy in range(int(y - rad), int(y + rad + 1)):
            for xx in range(int(x - rad), int(x + rad + 1)):
                if 0 <= xx < W and 0 <= yy < H:
                    if (xx - x) ** 2 + (yy - y) ** 2 <= rad * rad:
                        put(xx, yy, 74 - 20 * f, 128 - 30 * f, 52 - 14 * f)


# ---------------------------------------------------------------- finish
def paint_vignette_and_grain():
    cx, cy = 512.0, 512.0
    for y in range(H):
        dy = (y - cy) / 512.0
        row = y * W * 3
        for x in range(W):
            dx = (x - cx) / 512.0
            q = dx * dx + dy * dy
            vig = 1.0 - 0.38 * (q ** 1.6)
            n = (((x * 374761393 + y * 668265263) >> 13) & 7) - 3
            i = row + x * 3
            buf[i] = clamp255(buf[i] * vig + n)
            buf[i + 1] = clamp255(buf[i + 1] * vig + n)
            buf[i + 2] = clamp255(buf[i + 2] * vig + n)


def write_png(path):
    raw = bytearray()
    prev = bytes(W * 3)
    for y in range(H):
        row = bytes(buf[y * W * 3:(y + 1) * W * 3])
        # filter type 2 (Up): store differences from the row above
        diff = bytes((a - b) & 0xFF for a, b in zip(row, prev))
        raw.append(2)
        raw.extend(diff)
        prev = row
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", binascii.crc32(tag + data) & 0xFFFFFFFF)
        return c

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", comp)
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)


def main():
    paint_background()
    paint_halo()
    paint_shadow()
    paint_berry()
    paint_seeds()
    paint_droplets()
    paint_calyx_and_stem()
    paint_vignette_and_grain()
    os.makedirs("/output", exist_ok=True)
    write_png("/output/entry.png")


if __name__ == "__main__":
    main()
