# Designed by TiantianYe
# -*- coding: utf-8 -*-
"""【参考实现·APP 社交平台宣传图 v2 去AI化版】按 JSON 配置生成 4–6 张 3:4 竖版宣传图 + 总览图。

换 APP 时必须按以下步骤适配：
1. 复制 examples/config.example.json 到本次工作目录，替换所有 /ABS/PATH 占位路径；
2. 重写 posters（4–6 张）；大字行1 ≤5 字、行2 ≤9 字，贴纸词 2–5 字；
   文案按 references/copywriting-playbook.md 写，正式名称只进 official_name；
3. **防限流**：图上文字禁出现 APP / App Store / 下载 / 链接 / 安装（validate 会拦）；
4. frame.screen_box / island_clear 必须用 references/pipeline.md 的像素扫描法实测；
5. 去AI化六件套由脚本内建：得意黑大字、无序号无光晕、马克笔抖动线、
   白色贴纸（品牌 + 每张一个功能词，同图不与品牌重复）、手机微旋转 + 左右交替、背景噪点；
6. 用法：python3 make_posters.py --config /abs/path/config.json
   可选 --out 覆盖输出目录。定稿交付物只读，新 APP 一律写新目录。
"""
import argparse
import json
import os
import random
import re

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

WHITE = (255, 255, 255, 255)
DEFAULT_INK = [18, 78, 190]

DEFAULTS = {
    "canvas": [2160, 2880],
    "colors": {
        "top": [30, 126, 244],
        "bottom": [8, 74, 202],
        "ink_blue": DEFAULT_INK,
        "noise_sigma": 9,
    },
    "font": {
        "smiley": "/Users/tiantianye/Library/Fonts/smiley-sans-v2/SmileySans-Oblique.ttf",
        "hei": "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "hei_bold_index": 2,
    },
    "frame": {
        "size": [1350, 2760],
        "screen_box": [72, 69, 1278, 2691],
        "screen_radius": 145,
        "island_clear": [420, 85, 930, 360],
    },
    "shadow": {"blur": 80, "opacity": 0.38, "dx": 6, "dy": 48, "color": [2, 20, 62]},
    "sticker": {
        "pad_x": 52, "pad_y": 30, "radius": 40, "fill": [255, 255, 255, 246],
        "shadow_blur": 14, "shadow_opacity": 0.28,
    },
}


def deep_merge(base, override):
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


BANNED_ON_IMAGE = re.compile(r"\bapp\b|app\s*store|下载|链接|安装|上架", re.I)


def validate(cfg):
    for key in ("app_name", "official_name", "src_dir", "out_dir", "frame_path"):
        if not cfg.get(key):
            raise SystemExit(f"[配置错误] 缺少必需字段: {key}")
    posters = cfg.get("posters", [])
    if not 4 <= len(posters) <= 6:
        raise SystemExit(f"[配置错误] posters 必须 4–6 张，当前 {len(posters)} 张")
    brand = cfg["app_name"]
    for i, p in enumerate(posters, 1):
        for key in ("name", "shot", "l1", "l2", "width"):
            if key not in p:
                raise SystemExit(f"[配置错误] 第 {i} 张缺字段 {key}")
        if not os.path.exists(os.path.join(cfg["src_dir"], p["shot"])):
            raise SystemExit(f"[配置错误] 第 {i} 张截图不存在: {p['shot']}")
        # 防限流红线：图上任何文字不得出现引流词
        for key in ("l1", "l2", "tag", "name"):
            t = p.get(key) or ""
            if BANNED_ON_IMAGE.search(t):
                raise SystemExit(f"[防限流红线] 第 {i} 张 {key} 含限流词: {t}")
        # 品牌用词红线：营销别称不得与品牌拼成产品名
        pat = re.escape(brand)
        for key in ("l1", "l2", "tag"):
            t = p.get(key) or ""
            if re.search(r"[\u4e00-\u9fa5]{2,6}助手" + pat, t) or re.search(pat + r"[\u4e00-\u9fa5]{0,4}助手", t):
                raise SystemExit(f"[品牌红线] 第 {i} 张 {key} 出现别称与品牌拼接: {t}")
        # 同图贴纸词不得与品牌重复
        if p.get("tag") == brand:
            raise SystemExit(f"[去AI化红线] 第 {i} 张功能贴纸与品牌贴纸文字重复: {brand}")
    if not os.path.exists(cfg["frame_path"]):
        raise SystemExit(f"[配置错误] 边框素材不存在: {cfg['frame_path']}")


def fs(cfg, size):
    """得意黑：v2 主字体（社媒感、自带倾斜）。"""
    return ImageFont.truetype(cfg["font"]["smiley"], size)


def make_bg(cfg):
    W, H = cfg["canvas"]
    c = cfg["colors"]
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    top, bot = c["top"], c["bottom"]
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)],
               fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    # 细噪点：正负半对称叠加，亮度均值不变（注意 RGB 通道匹配，曾因写错整图变黑）
    noise = Image.effect_noise((W, H), c.get("noise_sigma", 9)).convert("RGB")
    mid = Image.new("RGB", (W, H), (128, 128, 128))
    im = ImageChops.add(im, ImageChops.subtract(noise, mid))
    im = ImageChops.subtract(im, ImageChops.subtract(mid, noise))
    return im.convert("RGBA")


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
    """带 pad 高斯阴影：模糊在放大画布上做，四边自然衰减到 0，禁止硬边。"""
    pad = int(blur * 3.2)
    big = Image.new("L", (phone.width + 2 * pad, phone.height + 2 * pad), 0)
    big.paste(phone.getchannel("A"), (pad, pad))
    sa = big.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * opacity))
    shadow = Image.new("RGBA", big.size, tuple(color) + (0,))
    shadow.putalpha(sa)
    return composite_at(canvas, shadow, x + dx - pad, y + dy - pad)


def add_phone(cfg, canvas, phone, x, y, tilt=0):
    """v2：手机微旋转 + 单层柔影；阴影跟随旋转后的轮廓。"""
    if tilt:
        phone = phone.rotate(tilt, expand=True, resample=Image.BICUBIC)
    s = cfg["shadow"]
    canvas = soft_shadow(canvas, phone, x, y, s["blur"], s["opacity"],
                         s["dx"], s["dy"], s["color"])
    return composite_at(canvas, phone, x, y)


def hand_line(d, p1, p2, width, color, seed, wobble=7):
    """马克笔抖动线：固定 seed 可复现，模拟手画下划线。"""
    rnd = random.Random(seed)
    n = 26
    pts = []
    for i in range(n + 1):
        t = i / n
        pts.append((p1[0] + (p2[0] - p1[0]) * t + rnd.uniform(-wobble, wobble),
                    p1[1] + (p2[1] - p1[1]) * t + rnd.uniform(-wobble, wobble)))
    d.line(pts, fill=color, width=width, joint="curve")


def make_sticker(cfg, text, size, tilt):
    """白色贴纸：白底圆角 + 深蓝得意黑字 + 微旋转。

    居中做法：textbbox 返回墨迹精确 bbox，卡片 = 墨迹 + 四边等宽 padding，
    文字锚点反推 → 上下左右严格居中。严禁高度再「+N 留余量」：
    余量全落底部，文字会整体偏上（错误档案 #23）。
    """
    st = cfg["sticker"]
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    box = tmp.textbbox((0, 0), text, font=fs(cfg, size))
    tw, th = box[2] - box[0], box[3] - box[1]
    card = Image.new("RGBA", (tw + st["pad_x"] * 2, th + st["pad_y"] * 2), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0, 0, card.width - 1, card.height - 1),
                         radius=st["radius"], fill=tuple(st["fill"]))
    cd.text((st["pad_x"] - box[0], st["pad_y"] - box[1]), text,
            font=fs(cfg, size), fill=tuple(cfg["colors"]["ink_blue"]))
    return card.rotate(tilt, expand=True, resample=Image.BICUBIC)


def paste_sticker(cfg, canvas, sticker, x, y):
    """贴纸带淡投影。composite_at 返回新图，调用方必须接收返回值。"""
    st = cfg["sticker"]
    pad = 26
    big = Image.new("L", (sticker.width + 2 * pad, sticker.height + 2 * pad), 0)
    big.paste(sticker.getchannel("A"), (pad, pad))
    sa = big.filter(ImageFilter.GaussianBlur(st["shadow_blur"])).point(
        lambda v: int(v * st["shadow_opacity"]))
    sh = Image.new("RGBA", big.size, (2, 20, 62, 0))
    sh.putalpha(sa)
    canvas = composite_at(canvas, sh, x - pad + 4, y - pad + 12)
    return composite_at(canvas, sticker, x, y)


def draw_line(d, x, y, text, fnt, color, stroke=2):
    """整行一次绘制。禁止逐字符：扁字「一」会被顶成上划线。"""
    d.text((x, y), text, font=fnt, fill=color, anchor="lt",
           stroke_width=stroke, stroke_fill=color)


def make_poster(cfg, p, idx, total, frame, clean):
    W, H = cfg["canvas"]
    im = make_bg(cfg)
    d = ImageDraw.Draw(im, "RGBA")
    rnd = random.Random(20261110 + idx)

    # 大字：得意黑，行1大行2小，每张不同 tx/ty（字号错落 + 位置微歪）
    tx, ty = p.get("tx", 140), p.get("ty", 300)
    s1 = fs(cfg, p.get("size1", 236))
    s2 = fs(cfg, p.get("size2", 176))
    draw_line(d, tx, ty, p["l1"], s1, WHITE, 2)
    draw_line(d, tx + p.get("l2_dx", 24), ty + p.get("size1", 236) + 64,
              p["l2"], s2, WHITE, 2)

    # 马克笔下划线
    y_line = ty + p.get("size1", 236) + 64 + p.get("size2", 176) + 66
    x2 = tx + p.get("l2_dx", 24) + s2.getlength(p["l2"])
    hand_line(d, (tx + p.get("l2_dx", 24) + 6, y_line),
              (x2 + rnd.uniform(30, 90), y_line + rnd.uniform(-8, 8)),
              16, WHITE, seed=1000 + idx, wobble=6)

    # 贴纸：品牌（每张必有）+ 功能词（可选，同图不与品牌重复）
    brand = make_sticker(cfg, cfg["app_name"], 96, -4)
    im = paste_sticker(cfg, im, brand, 128, 108)
    if p.get("tag"):
        tag = make_sticker(cfg, p["tag"], 96, p.get("tag_tilt", -5))
        im = paste_sticker(cfg, im, tag, p.get("tag_x", tx + 40),
                           p.get("tag_y", y_line + 130))

    # 手机：微旋转 + 单层柔影
    phone = build_phone(cfg, p["shot"], p["width"], frame, clean,
                        p.get("keep_island", True))
    px = p.get("px", (W - p["width"]) // 2)
    im = add_phone(cfg, im, phone, px, p.get("top", 1150), tilt=p.get("tilt", 0))

    # 收尾卡：右下角得意黑落款（不居中、不拉条）
    if p.get("footer"):
        d = ImageDraw.Draw(im, "RGBA")
        d.text((W - 170, 2680), cfg["app_name"], font=fs(cfg, 110), fill=WHITE,
               anchor="rt", stroke_width=2, stroke_fill=WHITE)

    path = os.path.join(cfg["out_dir"], f"{idx:02d}_{p['name']}.png")
    im.convert("RGB").save(path, "PNG", optimize=True)
    print("saved:", os.path.basename(path), f"{os.path.getsize(path)/1024/1024:.2f} MB")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None, help="覆盖输出目录（默认用 config.out_dir）")
    args = ap.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = deep_merge(DEFAULTS, json.load(f))
    if args.out:
        cfg["out_dir"] = args.out
    validate(cfg)
    os.makedirs(cfg["out_dir"], exist_ok=True)
    for fn in os.listdir(cfg["out_dir"]):
        if re.match(r"^\d{2}_.*\.png$", fn):
            os.remove(os.path.join(cfg["out_dir"], fn))

    frame, clean = load_frames(cfg)
    paths = []
    total = len(cfg["posters"])
    for i, p in enumerate(cfg["posters"], 1):
        paths.append(make_poster(cfg, p, i, total, frame, clean))

    # 总览联系表
    tw, th = 360, 480
    sheet = Image.new("RGB", (tw * 3 + 40, ((total + 2) // 3) * (th + 10) + 20),
                      (245, 247, 250))
    for i, p in enumerate(paths):
        thumb = Image.open(p).resize((tw, th), Image.LANCZOS)
        sheet.paste(thumb, (10 + (i % 3) * (tw + 10), 10 + (i // 3) * (th + 10)))
    sheet.save(os.path.join(cfg["out_dir"], "00_整套总览.jpg"), "JPEG", quality=90)
    print("saved: 00_整套总览.jpg")


if __name__ == "__main__":
    main()
