# 生成管线详解 + 质检清单 + 技术坑

## 环境依赖

- macOS（字体路径 `/System/Library/Fonts/Hiragino Sans GB.ttc` 实测可用；
  系统里**没有可直接读的 PingFang.ttc**，别去找）。
- Python 3 + Pillow（实测 12.3.0）。`python3 -c "from PIL import Image; print(Image.__version__)"`。
- `/usr/bin/sips -g pixelWidth -g pixelHeight <file>` 量尺寸。

## Stage 0 · 实测边框屏幕透明区（禁止猜）

```bash
python3 - <<'PY'
from PIL import Image
im = Image.open("边框.png").convert("RGBA")
print("size", im.size, "mode", im.mode)
x = im.width // 2
prev = None
for y in range(im.height):                    # 中线：找透明/不透明交替
    s = "OPAQUE" if im.getpixel((x,y))[3] > 128 else "transp"
    if s != prev: print("y=", y, s, im.getpixel((x,y))); prev = s
y = im.height // 2
prev = None
for xx in range(im.width):                   # 水平线：找左右边框内沿
    s = "OPAQUE" if im.getpixel((xx,y))[3] > 128 else "transp"
    if s != prev: print("x=", xx, s, im.getpixel((xx,y))); prev = s
PY
```

定稿结果：中线 y=69 起透明、y=2691 止；水平线 x=72 起透明、x=1278 止
→ `screen_box = [72,69,1278,2691]`。
再扫灵动岛：中间列 y=112..219 不透明黑块，x 约 535..815 → `island_clear=[420,85,930,360]`
（比岛本体大一圈，连淡阴影一起清）。

**换边框素材必须重扫**，不同机型几何不同。

## 生成命令

```bash
python3 ~/.workbuddy/skills/app-social-poster/scripts/make_posters.py \
  --config /abs/path/config.json
```

config 字段说明见 `examples/config.example.json` 与 `app-profiles.md`。
脚本做的事：读 config → 清旧编号 PNG → 逐张生成 → 输出 `00_整套总览.jpg`。
**定稿交付目录只读**，新 APP 一律写新 `out_dir`。

## 质检清单（Stage 4，逐条执行）

### 1. 目视总览
`00_整套总览.jpg`：标题不裁切、不重叠；品牌条只有 APP 名；序号连续；
底部四个圆按钮完整（标准档）；放大档底部是有意出血。

### 2. 「一 / 二」扁字
```bash
python3 - <<'PY'
from PIL import Image
im = Image.open("02_xxx.png")
box = (110, 200, 1250, 470)
im.crop(box).save("/tmp/check_yi.png")
PY
```
放大看那一横是否**居于字格中间**、与相邻汉字视觉重心齐平，而不是贴顶的上划线。

### 3. 阴影连续性（数值验证，不靠肉眼）
```bash
python3 - <<'PY'
from PIL import Image
im = Image.open("01_xxx.png").convert("RGB")
for y in (1200, 1500, 1900):
    vals = [int(sum(im.getpixel((x,y)))/3) for x in range(360, 580, 10)]
    diffs = [abs(vals[i+1]-vals[i]) for i in range(len(vals)-1)]
    print(y, vals, "max jump", max(diffs))
PY
```
定稿合格值：`117→94` 单调平滑，相邻 10px 跳变 ≤2（背景色本身随 y 变化，同一水平线恒定）。
出现 ≥20 的阶跃 = 阴影被硬裁，回去检查 `pad`。

### 4. 红线 grep（生成脚本 + config + 文案一起查）
```bash
grep -nE "YELLOW|FFE24A|255, ?226" 脚本 config
grep -nE "CLASS ASSISTANT|听课助手水课帮|助手水课帮|水课帮听课助手" config 发布文案.md
grep -nE "for ch in .*:.*d\.text|draw_segments" 脚本
```
前两条归零；第三条（逐字绘制）不得出现。

**文案两道检查**（用户第 5、6 轮返工，必做）：
```bash
# ① 原创：案例禁用短语逐条比对（清单见 copywriting-playbook.md §〇-B）
grep -nF -e "把上课交给AI，把时间还给自己" -e "谁懂啊" -e "线下课实时收音" \
         -e "一键开始摸鱼" -e "做了个防止课堂提问的小软件" 发布文案.md config.json
# ② 功能准确性：出现左边这些词即为写错，按 §〇-C 映射表改
grep -nE "小组件|没听清的题|智能分段|不保存课堂音频|不上传第三方" 发布文案.md config.json
```
两处都应归零（用户定稿句与用户点名钩子词除外）。

### 5. 交付清单
`ls` 输出目录：`01_..png` … `0N_..png`、`00_整套总览.jpg`、`发布文案.md`（七节）、可复跑脚本。

## 技术坑速查

| 坑 | 现象 | 解法 |
|---|---|---|
| 逐字符绘制 | 「一」变上划线 | 整行一次 `draw.text` |
| 在 `phone.size` 上模糊 | 阴影四边硬切断 | `pad = blur×3.2`，放大画布上模糊再贴回 |
| 边框自带岛 + 截图自带岛 | 两个灵动岛错位 | `keep_island=False` 时用 clean 边框 |
| 手机宽 1120 | 底部按钮被裁半截 | 标准档固定 1030 |
| 加深背景却没减光晕 | 顶部仍浅，像没改 | 光晕 fill 70/42、乘 0.30 |
| 截图尺寸不统一 | 屏幕内容被拉伸 | 统一 resize 到 `screen_box` 尺寸 |
| 圆角处露出方形截图角 | 屏幕四角发白/发灰 | 截图 alpha 乘圆角 mask（半径 145） |
| 换文案后旧图残留 | 目录里两套图 | `main()` 自动删 `^\d{2}_.*\.png$` |
| `anchor="lt"` 逐字 vs 整行 | 只有扁字错位 | 别混用两种绘制方式 |

## 交付后

- 诊断裁图、临时 config 用完即删，别留在交付目录。
- 在工作区 `.workbuddy/memory/YYYY-MM-DD.md` **追加**一段（append-only），
  记录本次 APP、文案方向、改动点与验证结果。

## 交付后 Finder 缩略图变黑（2026-11-10 实测，别误判成文件损坏）

**现象**：Finder 里 01/02/03 三张 PNG 的图标预览是纯黑方块，04/05/06 和总览 JPG 正常。

**先证伪"文件坏了"**（三步，全部只读）：
```bash
python3 - <<'PY'
from PIL import Image, ImageStat
import glob
for p in sorted(glob.glob("0[1-6]_*.png")):
    im = Image.open(p); st = ImageStat.Stat(im.convert("RGB"))
    print(p[:20], im.mode, im.size, [round(v) for v in st.mean],
          im.convert("RGB").getpixel((10,10)), list(im.info.keys()))
    Image.open(p).verify()          # PNG 完整性
PY
/usr/bin/sips -g pixelWidth -g pixelHeight 01_xxx.png        # macOS ImageIO 能否读
/usr/bin/sips -s format jpeg --out /tmp/t.jpg 01_xxx.png     # 转 JPG 后均值仍应是蓝色
```
定稿实测：6 张全 `RGB / 2160×2880`、均值约 `(94,147,225)`、左上角 `(48,136,244)`、
`verify()` 全 OK、无 ICC/gamma；sips 转 JPG 后颜色一致 → **文件与编码都没问题**。

**根因**：QuickLook 缩略图缓存里那几条记录坏了。反复重跑脚本**覆盖同名文件**时，
Finder 容易在写入中途抓到半成品帧（黑/空）并缓存下来；脚本按 01→06 顺序写，
最先写的几张最容易被抓到，所以恰好是 01/02/03。`com.apple.quarantine`（用"预览"打开过
留下的）不是共同原因，别去纠结它；`com.apple.provenance` 是 CLI 写文件自带的，无害。

**修法（两步，画面零改动）**：
```bash
qlmanage -r cache                 # 清系统缩略图缓存（本机执行成功）
# 再把 6 张原子重写，更新 inode + mtime，强制 Finder 重新抓缩略图：
python3 - <<'PY'
from PIL import Image, ImageChops
import os, glob, tempfile
for p in sorted(glob.glob("0[1-6]_*.png")):
    im = Image.open(p).convert("RGB"); before = im.copy()
    fd, tmp = tempfile.mkstemp(suffix=".png", dir="."); os.close(fd)
    im.save(tmp, "PNG", optimize=False)      # 换压缩参数 → 字节/哈希也变
    os.replace(tmp, p)                      # inode + mtime 都更新
    assert ImageChops.difference(before, Image.open(p).convert("RGB")).getbbox() is None
PY
```
重写后必须断言 `ImageChops.difference(...).getbbox() is None`（像素完全一致）。
若 Finder 仍没刷新，让用户在终端执行 `qlmanage -r cache && killall Finder`（Finder 会闪一下重开），
或直接切到别的文件夹再切回来。**不要**因此改设计、换配色或重新出图。

**预防**：以后脚本每次重跑都覆盖同名文件，交付后若用户反馈"预览黑"，先按本节证伪，
再清缓存 + 原子重写；也可直接同时输出一套 JPG（社交平台发布也更常用，缩略图最稳）。
