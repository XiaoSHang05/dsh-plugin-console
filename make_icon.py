# -*- coding: utf-8 -*-
"""
生成插件管家的 .ico（多尺寸，纯 Python 画，无外部依赖）

★ 关键：Windows 资源管理器/任务栏会按需选尺寸。
  只给一张 256x256 PNG 的 ICO，很多场景会显示成白纸（读不出来）。
  必须打包 16/24/32/48/64/128/256 七种尺寸。
"""

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).parent / "icon.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]


def draw(size):
    """画一张 size x size 的 RGBA 图（返回 bytes）"""
    px = bytearray(size * size * 4)
    S = float(size)
    cx = cy = S / 2.0

    R = S * 0.42
    stroke_w = max(1.0, S * 0.055)
    dot_r = S * 0.045

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

    def hex_sdf(x, y):
        dx = abs(x - cx + 0.5)
        dy = abs(y - cy + 0.5)
        return max(dx * 0.8660254 + dy * 0.5, dy)

    rad = S * 0.5

    # ---- 背景
    for y in range(size):
        for x in range(size):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            if dx * dx + dy * dy > rad * rad:
                continue
            t = y / S
            put(x, y,
                int(10 + (18 - 10) * t),
                int(14 + (26 - 14) * t),
                int(23 + (43 - 23) * t),
                255)

    # ---- 六边形描边 + 内圈
    inner_ring = R * 0.62
    for y in range(size):
        for x in range(size):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            if dx * dx + dy * dy > rad * rad:
                continue
            d = hex_sdf(x, y)
            if abs(d - R) < stroke_w:
                put(x, y, 94, 234, 212, 255)
            elif abs(d - R) < stroke_w * 3.2:
                k = 1.0 - abs(d - R) / (stroke_w * 3.2)
                put(x, y, 34, 211, 238, int(90 * k * k))
            elif size >= 32 and inner_ring - stroke_w * 0.35 < d < inner_ring + stroke_w * 0.35:
                put(x, y, 34, 211, 238, 140)

    # ---- 中心亮点
    for y in range(size):
        for x in range(size):
            dx = x - cx + 0.5
            dy = y - cy + 0.5
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < dot_r:
                put(x, y, 165, 243, 252, 255)
            elif dist < dot_r * 2.4:
                k = 1.0 - (dist - dot_r) / (dot_r * 1.4)
                put(x, y, 34, 211, 238, int(160 * max(0.0, k) ** 2))

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


def build_ico():
    pngs = []
    for s in SIZES:
        print(f"  画 {s}x{s}…")
        pngs.append((s, to_png(draw(s), s)))

    header = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries = b""
    for s, data in pngs:
        w = 0 if s >= 256 else s
        h = 0 if s >= 256 else s
        entries += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)

    return header + entries + b"".join(d for _, d in pngs)


if __name__ == "__main__":
    print(f"生成 {len(SIZES)} 个尺寸的 ICO…")
    ico = build_ico()
    OUT.write_bytes(ico)
    print(f"\n已写 {OUT}  ({len(ico)} bytes)")

    d = OUT.read_bytes()
    r, typ, cnt = struct.unpack("<HHH", d[:6])
    print(f"校验：type={typ}（1=ICO） 尺寸数={cnt}")
    for i in range(cnt):
        w, h, c, res, planes, bpp, sz, off = struct.unpack("<BBBBHHII", d[6 + i * 16: 22 + i * 16])
        print(f"  #{i+1}: {w or 256}x{h or 256}  {bpp}bpp  {sz}B")
