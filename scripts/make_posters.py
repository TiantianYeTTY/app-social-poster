# Designed by TiantianYe
# -*- coding: utf-8 -*-
"""【参考实现·APP 社交平台宣传图】按 JSON 配置生成 4–6 张 3:4 竖版宣传图 + 总览图。

换 APP 时必须按以下步骤适配：
1. 复制 examples/config.example.json 到本次工作目录，替换所有 /ABS/PATH 占位路径；
2. 重写 posters（4–6 张）；文案按 references/copywriting-playbook.md 写，
   正式名称只进 official_name，营销别称禁止与品牌拼成「听课助手水课帮」这类组合；
3. frame.screen_box / island_clear 必须用 references/pipeline.md 的像素扫描法实测，
   不同机型几何不同，禁止照抄；
4. 校验：主标题整行绘制（禁止逐字符）、双层带 pad 高斯阴影、全白文字、
   品牌条只画 app_name、标准档手机宽 1030（1120 会把底部按钮裁半截）；
5. 用法：python3 make_posters.py --config /abs/path/config.json
   可选 --out 覆盖输出目录。定稿交付物只读，新 APP 一律写新目录。
"""
import argparse
import json
import math
import os
import re

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

WHITE = (255, 255, 255, 255)

DEFAULTS = {
    "canvas": [2160, 2880],
    "margin": 140,
    "colors": {
        "top": [30, 126, 244],
        "bottom": [8, 74, 202],
        "glow": {
            "ellipse1": [-620, -780, 1250, 880], "fill1": 70,
            "ellipse2": [1250, 1750, 2950, 3450], "fill2": 42,
            "blur": 210, "opacity": 0.30,
        },
        "rings": [[1480, -520, 2860, 860, 26, 4], [1640, -360, 2700, 700, 18, 3]],
    },
    "font": {
        "path": "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "bold_index": 2, "regular_index": 0,
    },
    "layout": {
        "brand_y": 88, "brand_size": 88,
        "index_y": 136, "index_size": 44,
        "headline_y": [225, 465], "headline_size": 208, "headline_stroke": 2,
        "bar_top": 715, "bar_bottom": 727, "bar_width": 122,
        "sub_y": 755, "sub_size": 76, "sub_stroke": 1,
        "phone_top": 870,
        "footer_y": [2735, 2805], "footer_sizes": [48, 30],
    },
    "frame": {
        "size": [1350, 2760],
        "screen_box": [72, 69, 1278, 2691],
        "screen_radius": 145,
        "island_clear": [420, 85, 930, 360],
    },
    "shadow": {
        "layers": [[88, 0.40, 8, 56, [2, 20, 62]], [24, 0.18, 4, 20, [1, 14, 48]]],
    },
    "footer_lines": [],
}


def deep_merge(base, override):
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def validate(cfg):
    for key in ("app_name", "official_name", "src_dir", "out_dir", "frame_path"):
        if not cfg.get(key):
            raise SystemExit(f"[配置错误] 缺少必需字段: {key}")
    posters = cfg.get("posters", [])
    if not 4 <= len(posters) <= 6:
        raise SystemExit(f"[配置错误] posters 必须 4–6 张，当前 {len(posters)} 张")
    for i, p in enumerate(posters, 1):
        for key in ("name", "shot", "l1", "l2", "sub", "width"):
            if key not in p:
                raise SystemExit(f"[配置错误] 第 {i} 张缺字段 {key}")
        shot = os.path.join(cfg["src_dir"], p["shot"])
        if not os.path.exists(shot):
            raise SystemExit(f"[配置错误] 第 {i} 张截图不存在: {shot}")
        # 品牌用词红线：营销别称不得与品牌拼成产品名
        brand = re.escape(cfg["app_name"])
        for key in ("l1", "l2", "sub"):
            t = p[key]
            if re.search(r"[\u4e00-\u9fa5]{2,6}助手" + brand, t) or re.search(brand + r"[\u4e00-\u9fa5]{0,4}助手", t):
                raise SystemExit(f"[品牌红线] 第 {i} 张 {key} 出现别称与品牌拼接: {t}")
    if not os.path.exists(cfg["frame_path"]):
        raise SystemExit(f"[配置错误] 边框素材不存在: {cfg['frame_path']}")


def font(cfg, size, bold=True):
    f = cfg["font"]
    idx = f["bold_index"] if bold else f["regular_index"]
    return ImageFont.truetype(f["path"], size, index=idx)


def make_bg(cfg):
    W, H = cfg["canvas"]
    c = cfg["colors"]
    im = Image.new("RGBA", (W, H))
    d = ImageDraw.Draw(im)
    top, bot = c["top"], c["bottom"]
    for y in range(H):
        t = y / (H - 1)
        col = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=col + (255,))

    g = c["glow"]
    m = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(m)
    md.ellipse(tuple(g["ellipse1"]), fill=g["fill1"])
    md.ellipse(tuple(g["ellipse2"]), fill=g["fill2"])
    m = m.filter(ImageFilter.GaussianBlur(g["blur"]))
    glow = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    glow.putalpha(m.point(lambda v: int(v * g["opacity"])))
    im = Image.alpha_composite(im, glow)

    d = ImageDraw.Draw(im, "RGBA")
    for x0, y0, x1, y1, alpha, width in c["rings"]:
        d.ellipse((x0, y0, x1, y1), outline=(255, 255, 255, alpha), width=width)
    return im


def load_frames(cfg):
    frame = Image.open(cfg["frame_path"]).convert("RGBA")
    clean = frame.copy()
    px = clean.load()
    x0, y0, x1, y1 = cfg["frame"]["island_clear"]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(frame.width, x1), min(frame.height, y1)
    for y in range(y0, y1):
        for x in range(x0, x1):
            r, g, b, a = px[x, y]
            if a:
                px[x, y] = (r, g, b, 0)
    return frame, clean


def build_phone(cfg, shot_name, width, frame, clean, keep_island):
    fr = cfg["frame"]
    x0, y0, x1, y1 = fr["screen_box"]
    sw, sh = x1 - x0, y1 - y0
    shot = Image.open(os.path.join(cfg["src_dir"], shot_name)).convert("RGBA")
    shot = shot.resize((sw, sh), Image.LANCZOS)
    sm = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(sm).rounded_rectangle((0, 0, sw - 1, sh - 1),
                                         radius=fr["screen_radius"], fill=255)
    shot.putalpha(ImageChops.multiply(shot.getchannel("A"), sm))

    fw, fh = fr["size"]
    base = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    base.paste(shot, (x0, y0))
    base = Image.alpha_composite(base, frame if keep_island else clean)
    return base.resize((width, round(width * fh / fw)), Image.LANCZOS)


def composite_at(base, overlay, x, y):
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(overlay, (x, y))
    return Image.alpha_composite(base, layer)


def soft_shadow(canvas, phone, x, y, blur, opacity, dx, dy, color):
    """高斯柔化阴影：先给 alpha 四周留 pad，避免模糊在图像边界被硬裁断。"""
    pad = int(blur * 3.2)
    big = Image.new("L", (phone.width + 2 * pad, phone.height + 2 * pad), 0)
    big.paste(phone.getchannel("A"), (pad, pad))
    sa = big.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * opacity))
    shadow = Image.new("RGBA", big.size, tuple(color) + (0,))
    shadow.putalpha(sa)
    return composite_at(canvas, shadow, x + dx - pad, y + dy - pad)


def add_phone(cfg, canvas, phone, x, y):
    for blur, opacity, dx, dy, color in cfg["shadow"]["layers"]:
        canvas = soft_shadow(canvas, phone, x, y, blur, opacity, dx, dy, color)
    return composite_at(canvas, phone, x, y)


def draw_line(d, x, y, text, fnt, color, stroke=2):
    """整行一次绘制。

    禁止逐字符：Pillow 对单字符按该字形自己的墨迹顶部对齐锚点，
    「一 / 二」等扁字会被顶到字格最上方，变成一条上划线。
    """
    d.text((x, y), text, font=fnt, fill=color, anchor="lt",
           stroke_width=stroke, stroke_fill=color)


def make_poster(cfg, p, idx, total, frame, clean):
    W, H = cfg["canvas"]
    L = cfg["layout"]
    M = cfg["margin"]
    im = make_bg(cfg)
    d = ImageDraw.Draw(im, "RGBA")

    # 品牌条：只画 app_name，不加副名 / 英文
    d.text((M, L["brand_y"]), cfg["app_name"], font=font(cfg, L["brand_size"]),
           fill=WHITE, anchor="lt", stroke_width=1, stroke_fill=WHITE)
    d.text((W - M, L["index_y"]), f"{idx:02d} / {total:02d}",
           font=font(cfg, L["index_size"]), fill=(255, 255, 255, 215), anchor="rm")

    hf = font(cfg, L["headline_size"])
    draw_line(d, M, L["headline_y"][0], p["l1"], hf, WHITE, L["headline_stroke"])
    draw_line(d, M, L["headline_y"][1], p["l2"], hf, WHITE, L["headline_stroke"])
    d.rounded_rectangle((M, L["bar_top"], M + L["bar_width"], L["bar_bottom"]),
                        radius=6, fill=WHITE)
    d.text((M + 2, L["sub_y"]), p["sub"], font=font(cfg, L["sub_size"]),
           fill=WHITE, anchor="lt", stroke_width=L["sub_stroke"], stroke_fill=WHITE)

    phone = build_phone(cfg, p["shot"], p["width"], frame, clean,
                        p.get("keep_island", True))
    px = (W - p["width"]) // 2 + p.get("dx", 0)
    im = add_phone(cfg, im, phone, px, p.get("top", L["phone_top"]))

    lines = cfg.get("footer_lines", [])
    if p.get("footer") and lines:
        d = ImageDraw.Draw(im, "RGBA")
        d.text((W // 2, L["footer_y"][0]), lines[0],
               font=font(cfg, L["footer_sizes"][0]), fill=(255, 255, 255, 235),
               anchor="mt", stroke_width=1, stroke_fill=(255, 255, 255, 235))
        if len(lines) > 1:
            d.text((W // 2, L["footer_y"][1]), lines[1],
                   font=font(cfg, L["footer_sizes"][1], False),
                   fill=(255, 255, 255, 165), anchor="mt")

    path = os.path.join(cfg["out_dir"], f"{idx:02d}_{p['name']}.png")
    im.convert("RGB").save(path, "PNG", optimize=True)
    print("saved:", os.path.basename(path), f"{os.path.getsize(path)/1024/1024:.2f} MB")
    return path


def make_sheet(cfg, paths):
    tw, th = 360, 480
    cols = 3
    rows = math.ceil(len(paths) / cols)
    sheet = Image.new("RGB", (tw * cols + (cols + 1) * 10,
                              th * rows + (rows + 1) * 10), (245, 247, 250))
    for i, p in enumerate(paths):
        thumb = Image.open(p).resize((tw, th), Image.LANCZOS)
        sheet.paste(thumb, (10 + (i % cols) * (tw + 10),
                            10 + (i // cols) * (th + 10)))
    out = os.path.join(cfg["out_dir"], "00_整套总览.jpg")
    sheet.save(out, "JPEG", quality=90)
    print("saved: 00_整套总览.jpg")


def main():
    ap = argparse.ArgumentParser(description="APP 社交平台宣传图生成器")
    ap.add_argument("--config", required=True, help="config.json 绝对路径")
    ap.add_argument("--out", default=None, help="覆盖输出目录")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as fp:
        raw = json.load(fp)
    cfg = deep_merge(DEFAULTS, raw)
    if args.out:
        cfg["out_dir"] = args.out
    validate(cfg)

    os.makedirs(cfg["out_dir"], exist_ok=True)
    # 换文案后清掉上一版编号图，避免目录残留
    for fn in os.listdir(cfg["out_dir"]):
        if re.match(r"^\d{2}_.*\.png$", fn):
            os.remove(os.path.join(cfg["out_dir"], fn))

    frame, clean = load_frames(cfg)
    posters = cfg["posters"]
    paths = [make_poster(cfg, p, i, len(posters), frame, clean)
             for i, p in enumerate(posters, 1)]
    make_sheet(cfg, paths)
    print(f"done: {len(paths)} posters -> {cfg['out_dir']}")


if __name__ == "__main__":
    main()
