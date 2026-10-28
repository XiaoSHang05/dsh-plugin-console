# -*- coding: utf-8 -*-
"""
生成插件管家的 .ico 图标（纯 Python 画，不依赖外部库）
设计：深空底 + 青色六边形 + 中心亮点，跟界面同风格
"""

import struct
import zlib
from pathlib import Path

SIZE = 256


def make_rgba():
    """画 256x256 的 RGBA 像素"""
    px = bytearray(SIZE * SIZE * 4)

    cx = cy = SIZE / 2.0
    R = SIZE * 0.42          # 六边形外接圆半径
    Rin = R * 0.78           # 描边内侧

    def put(x, y, r, g, b, a):
        if 0 <= x < SIZE and 0 <= y < SIZE:
            i = (y * SIZE + x) * 4
            # 简单 alpha 混合
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

    # ---- 六边形判定（平顶六边形）
    def hex_dist(x, y):
        dx = abs(x - cx)
        dy = abs(y - cy)
        # 六边形 SDF 近似
        k = 0.8660254037844386  # sqrt(3)/2
        d = max(dx * 0.866025 + dy * 0.5, dy)
        return d

    # ---- 背景：深空渐变 + 圆角
    for y in range(SIZE):
        for x in range(SIZE):
            # 圆形裁剪（做圆角图标）
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy > (SIZE * 0.5) ** 2:
                continue
            # 垂直渐变 #0a0e17 → #121a2b
            t = y / SIZE
            r = int(10 + (18 - 10) * t)
            g = int(14 + (26 - 14) * t)
            b = int(23 + (43 - 23) * t)
            put(x, y, r, g, b, 255)

    # ---- 六边形描边（青色，带外发光）
    for y in range(SIZE):
        for x in range(SIZE):
            d = hex_dist(x, y)
            if abs(d - R) < 1.6:
                # 主描边
                put(x, y, 94, 234, 212, 255)
            elif abs(d - R) < 5.0:
                # 外发光
                k = 1.0 - abs(d - R) / 5.0
                put(x, y, 34, 211, 238, int(80 * k * k))
            elif R * 0.62 < d < R * 0.62 + 1.2:
                # 内圈细线
                put(x, y, 34, 211, 238, 150)

    # ---- 中心亮点
    for y in range(SIZE):
        for x in range(SIZE):
            dx = x - cx
            dy = y - cy
            dist2 = dx * dx + dy * dy
            # 实心圆
            if dist2 < (SIZE * 0.045) ** 2:
                put(x, y, 165, 243, 252, 255)
            elif dist2 < (SIZE * 0.11) ** 2:
                k = 1.0 - (dist2 ** 0.5 - SIZE * 0.045) / (SIZE * 0.065)
                put(x, y, 34, 211, 238, int(150 * max(0.0, k) ** 2))

    return bytes(px)


def make_png(rgba, size):
    """RGBA → PNG 字节"""
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filter type 0
        raw.extend(rgba[y * size * 4:(y + 1) * size * 4])

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    return png


def make_ico(png_bytes, size):
    """单张 PNG 装进 ICO 容器"""
    # ICO 头：reserved(2) type(2) count(2)
    header = struct.pack("<HHH", 0, 1, 1)
    # 目录项：w(1) h(1) colors(1) reserved(1) planes(2) bpp(2) size(4) offset(4)
    w = 0 if size >= 256 else size
    h = 0 if size >= 256 else size
    entry = struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(png_bytes), 6 + 16)
    return header + entry + png_bytes


if __name__ == "__main__":
    out = Path(__file__).parent / "icon.ico"
    rgba = make_rgba()
    png = make_png(rgba, SIZE)
    ico = make_ico(png, SIZE)
    out.write_bytes(ico)
    print(f"已生成 {out}  ({len(ico)} bytes)")
