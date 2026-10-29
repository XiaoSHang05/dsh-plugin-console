# -*- coding: utf-8 -*-
"""
生成插件管家图标（多尺寸，纯 Python，无依赖）

设计要点（针对小尺寸优化）：
  · 32px 下细描边会糊 → 改用「实心六边形环」，够粗够亮
  · 圆底用深空渐变，六边形用青色渐变（外亮内暗，做出立体感）
  · 中心亮点作为识别点
"""

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).parent / "icon.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw(size):
    px = bytearray(size * size * 4)
    S = float(size)
    cx = cy = S / 2.0
    rad = S * 0.5

    R_out = S * 0.40
    R_in = R_out * (0.50 if size >= 32 else 0.42)
    dot_r = S * (0.055 if size >= 32 else 0.075)

    def put(x, y, r, g, b, a):
        if not (0 <= x < size and 0 <= y < size):
            return
        i = (y * size + x) * 4
        if a >= 255:
            px[i] = r; px[i + 1] = g; px[i + 2] = b; px[i + 3] = 255
        else:
            oa = px[i + 3]
            na = a + oa * (255 - a) // 255
            if na > 0:
                px[i] = (r * a + px[i] * oa * (255 - a) // 255) // na
                px[i + 1] = (g * a + px[i + 1] * oa * (255 - a) // 255) // na
                px[i + 2] = (b * a + px[i + 2] * oa * (255 - a) // 255) // na
                px[i + 3] = na

    def hex_r(x, y):
        dx = abs(x - cx + 0.5)
        dy = abs(y - cy + 0.5)
        return max(dx * 0.8660254 + dy * 0.5, dy)

    # ---- 圆底：深空渐变
    for y in range(size):
        for x in range(size):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            if dx * dx + dy * dy > rad * rad:
                continue
            t = y / S
            put(x, y, int(8 + 10 * t), int(13 + 14 * t), int(22 + 22 * t), 255)

    # ---- 实心六边形环
    for y in range(size):
        for x in range(size):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            if dx * dx + dy * dy > rad * rad:
                continue
            d = hex_r(x, y)
            if d > R_out or d < R_in:
                continue
            k = (d - R_in) / max(1e-6, R_out - R_in)
            put(x, y,
                int(94 + (165 - 94) * k),
                int(234 + (243 - 234) * k),
                int(212 + (252 - 212) * k),
                255)

    # ---- 中心亮点
    for y in range(size):
        for x in range(size):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < dot_r:
                put(x, y, 186, 250, 255, 255)
            elif dist < dot_r * 1.9 and size >= 32:
                k = 1.0 - (dist - dot_r) / (dot_r * 0.9)
                put(x, y, 94, 234, 212, int(150 * max(0.0, k) ** 2))

    return bytes(px)


def to_png(rgba, size):
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        raw.extend(rgba[y * size * 4:(y + 1) * size * 4])

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


def build():
    pngs = [(s, to_png(draw(s), s)) for s in SIZES]
    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries = b""
    for s, data in pngs:
        w = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(d for _, d in pngs)


if __name__ == "__main__":
    ico = build()
    OUT.write_bytes(ico)
    print(f"已写 {OUT}  ({len(ico)} bytes, {len(SIZES)} 个尺寸)")
    for s in (32, 256):
        p = Path(__file__).parent / f"_prev_{s}.png"
        p.write_bytes(to_png(draw(s), s))
        print(f"预览: {p.name}")
