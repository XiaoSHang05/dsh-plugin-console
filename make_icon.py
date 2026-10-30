# -*- coding: utf-8 -*-
"""
生成插件管家图标（多尺寸 + 抗锯齿，纯 Python，无外部依赖）

v3 改进（针对「像素太低」）：
  ① 4×4 超采样抗锯齿 —— 原来逐像素硬切，边缘全是阶梯
  ② 立体感 —— 六边形环做「外缘高光 + 内缘暗」，中心球加高光点
  ③ 层次 —— 圆底加径向渐变，不再是死平
  ④ 小尺寸单独优化 —— 16/24/32 用更粗的环、去掉细节防糊
"""

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).parent / "icon.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]

SS = 4          # 超采样倍率（4×4 = 16 个样本/像素）


def _hex_r(dx, dy):
    """平顶六边形的等效半径（坐标相对中心）"""
    ax = abs(dx)
    ay = abs(dy)
    return max(ax * 0.8660254 + ay * 0.5, ay)


def _lerp(a, b, t):
    return a + (b - a) * t


def _clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def draw(size):
    """返回 RGBA bytes"""
    px = bytearray(size * size * 4)
    S = float(size)
    cx = cy = S / 2.0
    R_circle = S * 0.495

    small = size <= 32
    R_out = S * (0.435 if small else 0.425)
    ring_ratio = 0.46 if small else 0.40
    R_in = R_out * (1.0 - ring_ratio)
    dot_r = S * (0.085 if small else 0.070)

    n = SS
    step = 1.0 / n
    half = step / 2.0
    total = float(n * n)

    for y in range(size):
        for x in range(size):
            acc_r = acc_g = acc_b = 0.0
            acc_a = 0.0

            for sy in range(n):
                for sx in range(n):
                    fx = x + sx * step + half
                    fy = y + sy * step + half
                    dx = fx - cx
                    dy = fy - cy
                    dist = (dx * dx + dy * dy) ** 0.5

                    if dist > R_circle:
                        continue

                    t = _clamp(dist / R_circle)
                    r = _lerp(20, 8, t)
                    g = _lerp(30, 13, t)
                    b = _lerp(48, 22, t)
                    a = 255.0

                    hd = _hex_r(dx, dy)
                    if R_in <= hd <= R_out:
                        k = _clamp((hd - R_in) / max(1e-6, R_out - R_in))
                        if k > 0.72:
                            hk = (k - 0.72) / 0.28
                            r = _lerp(94, 214, hk)
                            g = _lerp(234, 253, hk)
                            b = _lerp(212, 255, hk)
                        elif k < 0.20:
                            dk = 1.0 - (k / 0.20)
                            r = _lerp(94, 26, dk * 0.55)
                            g = _lerp(234, 130, dk * 0.55)
                            b = _lerp(212, 150, dk * 0.55)
                        else:
                            mk = (k - 0.20) / 0.52
                            r = _lerp(52, 94, mk)
                            g = _lerp(190, 234, mk)
                            b = _lerp(190, 212, mk)
                        a = 255.0
                    elif not small and hd < R_in:
                        glow_d = R_in - hd
                        if glow_d < S * 0.05:
                            gk = 1.0 - glow_d / (S * 0.05)
                            gk = gk * gk * 0.42
                            r = _lerp(r, 34, gk)
                            g = _lerp(g, 211, gk)
                            b = _lerp(b, 238, gk)

                    if dist < dot_r:
                        lx = (dx + dot_r * 0.35) / dot_r
                        ly = (dy + dot_r * 0.35) / dot_r
                        lit = _clamp(1.0 - (lx * lx + ly * ly) * 0.42)
                        r = _lerp(150, 240, lit)
                        g = _lerp(240, 255, lit)
                        b = _lerp(250, 255, lit)
                        a = 255.0
                    elif not small and dist < dot_r * 1.85:
                        gd = (dist - dot_r) / (dot_r * 0.85)
                        gk = _clamp(1.0 - gd)
                        gk = gk * gk * 0.55
                        r = _lerp(r, 120, gk)
                        g = _lerp(g, 245, gk)
                        b = _lerp(b, 255, gk)

                    acc_r += r
                    acc_g += g
                    acc_b += b
                    acc_a += a

            if acc_a < 1.0:
                continue
            A = acc_a / total                 # 覆盖率 0..1
            cnt = acc_a / 255.0               # 有效覆盖的样本数
            inv = cnt if cnt > 0 else 1.0
            i = (y * size + x) * 4
            px[i] = int(_clamp(acc_r / inv, 0, 255))
            px[i + 1] = int(_clamp(acc_g / inv, 0, 255))
            px[i + 2] = int(_clamp(acc_b / inv, 0, 255))
            px[i + 3] = int(_clamp(A * 255.0, 0, 255))

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
    pngs = []
    for s in SIZES:
        print(f"  draw {s}x{s} ({SS*SS} samples/px)...")
        pngs.append((s, to_png(draw(s), s)))

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
    print(f"\nwrote {OUT}  ({len(ico)} bytes, {len(SIZES)} sizes)")

    for s in (32, 256):
        p = Path(__file__).parent / f"_prev_{s}.png"
        p.write_bytes(to_png(draw(s), s))
        print(f"preview: {p.name}")
