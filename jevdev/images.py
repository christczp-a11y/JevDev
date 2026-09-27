"""封面主图：优先用 Chris 的实拍；没有实拍时用 Codex（ChatGPT 会员）画一张插画。

规矩：
  - 不用别人拍的图（Google 地图 / 小红书 / Yelp 上的照片）：版权属于拍摄者，小红书按搬运处理，注明转载也不行
  - AI 图一律画成「一眼就是插画」的风格，并在图上标「AI 插画 · 仅示意」：画的是这类菜，不冒充这家店的实物
"""
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()  # iPhone 照片默认是 HEIC

CODEX_EXE = (Path.home() / "AppData/Roaming/npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64"
             / "vendor/x86_64-pc-windows-msvc/bin/codex.exe")
AI_LABEL = "AI 插画 · 仅示意"
PHOTO_LABEL = "实拍"
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}

STYLES = [
    ("扁平矢量插画（flat vector illustration）：粗深色描边，纯色平涂，最多 6 种颜色，"
     "没有写实的光影、油光、纹理和景深，像美食海报上的图标式插画，缩成小图也一眼看出是画的；"
     "明亮温暖的浅色纯色背景；食物是画面唯一的主角，俯视，构图饱满；"
     "画面里不要有任何文字、字母、logo、招牌、人物或手"),
    # 第一次画得太像照片时用：更极端的风格
    ("儿童绘本式蜡笔手绘插画：线条稚拙、不规则，颜色平涂、有明显的蜡笔笔触，完全不追求写实，"
     "绝对不能像照片；浅米色纸张背景；食物是画面唯一的主角；"
     "画面里不要有任何文字、字母、logo、招牌、人物或手"),
]


def dishes_of(draft):
    """从正文的「✅ 必点」那一行取菜名；没有就用标题。"""
    m = re.search(r"✅[^\n]*", draft["body"])
    return m.group(0).lstrip("✅ ").strip() if m else draft["title"]


def _to_jpeg(src, dst, width=1080):
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)))
    img.save(dst, quality=88)
    return str(dst)


def _generate(dishes, style, raw, timeout):
    raw.unlink(missing_ok=True)  # 旧图还在的话，生成失败会被误判成成功
    prompt = (f"用你的图片生成工具画一张横版 4:3 的美食插画（会放在小红书封面的上半部分）。\n"
              f"要画的菜：{dishes}\n"
              f"风格：{style}\n"
              f"画好后保存到当前目录，文件名 {raw.name}。只需要保存图片，不用解释。")
    # Chris 的 ChatGPT 额度有限：画图时用小模型 + 低推理（他本机默认是 gpt-6-sol + high）
    proc = subprocess.run([str(CODEX_EXE), "exec", "--skip-git-repo-check", "-s", "workspace-write",
                           "-m", "gpt-6-astra", "-c", 'model_reasoning_effort="low"',
                           "-C", str(raw.parent), "-"],
                          input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    if not raw.exists():
        raise RuntimeError(f"Codex 没有生成图片：{(proc.stdout or proc.stderr)[-400:]}")


REALISM_SCHEMA = {
    "type": "object",
    "properties": {
        "realism": {"type": "integer", "minimum": 1, "maximum": 5,
                    "description": "1=明显是简笔画或扁平图标；3=一看就是插画，但画得细致；5=和真实照片几乎分不出"},
        "mistaken_for_photo": {"type": "boolean",
                               "description": "普通用户在手机信息流里刷到这张小图时，会不会以为是真实拍摄的照片"},
    },
    "required": ["realism", "mistaken_for_photo"],
}


def looks_like_photo(path):
    """自检：缩成信息流缩略图（宽 300px）后，交给 Claude 看图判断会不会被当成实拍。
    只看原图没用：原图上看得出是画的，小图上就不一定了。"""
    import json
    from jevdev.writer import CLAUDE_EXE
    thumb = Path(path).with_name("thumb_check.jpg")
    img = Image.open(path).convert("RGB")
    img.resize((300, round(img.height * 300 / img.width))).save(thumb, quality=80)
    proc = subprocess.run(
        [str(CLAUDE_EXE), "-p", "--model", "claude-sonnet-5", "--output-format", "json", "--tools", "Read",
         "--allowedTools", "Read", "--add-dir", str(thumb.parent),
         "--json-schema", json.dumps(REALISM_SCHEMA, ensure_ascii=False)],
        input=f"用 Read 打开这张缩略图：{thumb}\n它会出现在小红书信息流里。判断它的写实程度，以及普通用户刷到时会不会以为是真实照片。",
        capture_output=True, text=True, encoding="utf-8", timeout=300)
    out = json.loads(proc.stdout).get("structured_output") or {}
    return bool(out.get("mistaken_for_photo")) or out.get("realism", 5) >= 4


def illustrate(draft, out_dir, timeout=600):
    """用 Codex 的图片生成画封面插画，返回 JPEG 路径。画得像照片就换更极端的风格重画一次；
    两次都像照片或生成失败时抛 RuntimeError（宁可用纯文字封面，也不发会被当成实拍的图）。"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / "cover_raw.png"
    for style in STYLES:
        _generate(dishes_of(draft), style, raw, timeout)
        jpg = _to_jpeg(raw, out_dir / "cover.jpg")
        if not looks_like_photo(jpg):
            return jpg
    raise RuntimeError("两次生成的插画都太像照片，没有采用")


def photos_in(photo_dir):
    """Chris 的实拍：文件夹里所有图片，按文件名排序；名字以 cover 开头的排第一张当封面。"""
    files = sorted(p for p in Path(photo_dir).iterdir() if p.suffix.lower() in PHOTO_EXT)
    return sorted(files, key=lambda p: not p.stem.lower().startswith("cover"))


def photo_pages(photos, out_dir, start):
    """封面之外的实拍图：裁成 3:4（1080×1440），接在信息卡后面，文件名接着 card_XX 编号。"""
    paths = []
    for i, p in enumerate(photos, start):
        img = ImageOps.fit(ImageOps.exif_transpose(Image.open(p)).convert("RGB"), (1080, 1440))
        dst = Path(out_dir) / f"card_{i:02d}.png"
        img.save(dst)
        paths.append(str(dst))
    return paths


def cover_image(draft, out_dir, photo_dir=None):
    """返回 (图片路径, 图上标注, 其余实拍列表)。有实拍用实拍，否则画插画。"""
    if photo_dir:
        photos = photos_in(photo_dir)
        if photos:
            return _to_jpeg(photos[0], Path(out_dir) / "cover.jpg"), PHOTO_LABEL, photos[1:]
    return illustrate(draft, out_dir), AI_LABEL, []


def dress_cover(draft, out_dir, photo_dir=None, log=print, credit=None):
    """给选中的草稿配封面，按优先级：照片文件夹 → 图库实物抠图（stock.py，Jev 选图）→ AI 插画 → 纯文字。
    照片文件夹：Chris 实拍（credit 为空），或已获授权的照片（credit = 出处，如「Tourism Richmond」）。
    直接修改 draft（cover、body），返回其余照片列表（接在信息卡后面）。"""
    from jevdev import cards, stock
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if photo_dir and photos_in(photo_dir):
        img, label, extra = cover_image(draft, out_dir, photo_dir)
        if credit:
            label = f"图片：{credit}"
            draft["body"] += f"\n📷 图片来源：{credit}（已获授权）"
        draft["cover"] = dict(draft["cover"], image=img, image_label=label)
        draft["cover_source"] = {"type": "licensed_photo" if credit else "photo", "dir": str(photo_dir), "credit": credit}
        return extra
    try:
        log("  图库找实物图 → Jev 选图 → 抠图 → 自检…")

        def render(cut):
            c = dict(draft["cover"], cutout=cut, image_label=stock.LABEL)
            return cards.render([c], out_dir / "check")[0]
        cut, meta = stock.make_cover(draft, out_dir / "stock", render)
        draft["cover"] = dict(draft["cover"], cutout=cut, image_label=stock.LABEL)
        draft["cover_source"] = dict(meta, type="stock")
        draft["body"] += "\n" + stock.BODY_NOTE
        return []
    except Exception as e:
        log(f"  图库这条路没成：{e}")
    try:
        log("  改用 Codex 画插画…")
        img = illustrate(draft, out_dir)
        draft["cover"] = dict(draft["cover"], image=img, image_label=AI_LABEL)
        draft["cover_source"] = {"type": "ai_illustration"}
        draft["body"] += "\n🎨 封面为 AI 插画，仅作示意"
    except Exception as e:  # 都失败时退回纯文字封面，草稿包照样生成，发布前人工会看到
        log(f"  ⚠ 插画也没成，暂用纯文字封面：{e}")
        draft["cover_source"] = {"type": "text_only"}
    return []
