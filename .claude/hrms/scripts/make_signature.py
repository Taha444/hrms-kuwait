#!/usr/bin/env python3
"""
مولّد صورة توقيع اصطناعية لاختبار مسار التوقيع.
لا يمثّل توقيع أي شخص حقيقي — خط منحنٍ عشوائي فقط.

  python3 make_signature.py -o /tmp/AUDIT_sig_v1.png
  python3 make_signature.py -o /tmp/AUDIT_sig_v2.png --seed 7
"""
import argparse, random, math, struct, zlib, sys

def png(w, h, px):
    raw = b"".join(b"\x00" + bytes(px[y*w*3:(y+1)*w*3]) for y in range(h))
    def ch(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n"
            + ch(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + ch(b"IDAT", zlib.compress(raw, 9)) + ch(b"IEND", b""))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("-w", type=int, default=400)
    ap.add_argument("-H", type=int, default=140)
    a = ap.parse_args()
    if not a.out.split("/")[-1].startswith("AUDIT_"):
        print("!! يفضّل أن يبدأ اسم الملف بـ AUDIT_ ليسهل تنظيفه لاحقا", file=sys.stderr)
    random.seed(a.seed)
    w, h = a.w, a.H
    px = bytearray([255] * (w * h * 3))
    def dot(x, y):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                xx, yy = int(x) + dx, int(y) + dy
                if 0 <= xx < w and 0 <= yy < h:
                    i = (yy * w + xx) * 3
                    px[i] = px[i+1] = 20; px[i+2] = 60
    x, y = 30.0, h / 2
    phase = random.uniform(0, 6.28)
    amp = random.uniform(18, 32)
    while x < w - 30:
        y = h/2 + amp*math.sin(phase) + random.uniform(-3, 3)
        dot(x, y)
        for k in range(1, 4):
            dot(x, y + random.uniform(-2, 2))
        x += 0.7
        phase += random.uniform(0.05, 0.12)
    open(a.out, "wb").write(png(w, h, px))
    print(f"تم: {a.out}  ({w}x{h})")

if __name__ == "__main__":
    main()
