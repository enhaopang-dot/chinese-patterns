# -*- coding: utf-8 -*-
"""pgf2svg.py — 把 pgfornament-han 的 .pgf 路径数据批量转成独立 SVG 文件。

映射规则（2026-10-07 考古实证，同日修 Y 轴翻转 bug 后复验）：
  \\m x y          -> M x (Y-y)    (moveto；pgf Y 轴向上，SVG 向下，按官方尺寸表高度翻转)
  \\l x y          -> L x (Y-y)    (lineto)
  \\c x1 y1 x2 y2 x3 y3 -> C ...   (三次贝塞尔，参数顺序与 SVG 一致，所有 y 翻转)
  \\r x1 y1 x2 y2  -> <rect>       (对角点矩形，y 翻转后重算)
  \\s              -> fill+stroke 收尾 (pgf usepathqfillstroke；SVG fill 自动闭合开放路径，无需 Z)
  \\o              -> Z            (pathclose)
  bp 单位 = 1/72 英寸 = SVG 用户单位
  \\pgfsetrectcap  -> stroke-linecap:square
注意：
  - han19.pgf 在 \\endinput 后有 pstricks 死代码，遇 \\endinput 即停。
  - \\r 后紧跟 \\ubb（=\\pgfusepath{use as bounding box}，定义见 pgfornament-han.sty L52）的矩形
    仅声明边界盒不绘制（han55/58/60/64/66/68/70/76 共 8 个文件），必须跳过，否则全幅黑矩形垫底。
  - 原生尺寸表在 assets/pgf/pgflibraryhan.code.tex（\@pgfornamenthanDim），
    是 viewBox 与 Y 翻转的权威依据；文件缺失时回退 bbox 翻转并警告。

用法：
  python pgf2svg.py                          # 默认：skill 内 assets/pgf -> assets/svg
  python pgf2svg.py --src <pgf目录> --dst <输出目录>
  python pgf2svg.py --force                  # 允许覆盖已存在同名 SVG（默认跳过防误覆）
"""
import argparse
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent

# 编号 -> 纹类对照（来自 pgfornament-han 文档"纹样列表"章）
def classify(n: int) -> str:
    if 1 <= n <= 18: return "角点符号"
    if 19 <= n <= 28: return "回纹角点"
    if 29 <= n <= 32: return "直线"
    if 33 <= n <= 54: return "回字纹"
    if n == 55: return "福字纹"
    if 56 <= n <= 57: return "寿字纹"
    if 58 <= n <= 77: return "云纹"
    if n == 78: return "动物"
    return "未知"

def parse_dims(tex_path: Path) -> dict[int, tuple[float, float]]:
    """从 pgflibraryhan.code.tex 解析原生尺寸表 {n: (X, Y)}，bp 单位。"""
    t = tex_path.read_text(encoding="utf-8", errors="replace")
    dims = {}
    for m in re.finditer(
        r"\\or\\def\\@pgfornamentX\{([\d.]+)\}\\def\\@pgfornamentY\{([\d.]+)\}%\s*(\d+)", t
    ):
        dims[int(m.group(3))] = (float(m.group(1)), float(m.group(2)))
    return dims

def convert(text: str, dim: tuple[float, float] | None) -> str:
    # 去注释、截断到 \endinput
    lines = []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("%") or not ln:
            continue
        if "\\endinput" in ln:
            break
        ln = re.sub(r"%.*$", "", ln).strip()
        if ln:
            lines.append(ln)
    body = " ".join(lines)

    d_parts: list[str] = []
    rects: list[str] = []
    square_cap = False

    def fy(y: float) -> float:
        return (dim[1] if dim else max_y_holder[0]) - y
    max_y_holder = [0.0]  # dim 缺失时两轮解析：先扫一遍求 max y

    def nums(seg: str, count: int) -> list[float]:
        vals = [float(v) for v in re.findall(r"-?\d+\.?\d*", seg)[:count]]
        if len(vals) < count:
            raise ValueError(f"参数不足: need {count} got {len(vals)} in {seg[:60]!r}")
        return vals

    parts = re.split(r"\\(pgfsetrectcap|m|l|c|r|s|o|p)\b", body)
    segs = [(parts[j], parts[j + 1]) for j in range(1, len(parts) - 1, 2)]

    if not dim:  # 回退：先扫所有 y 求最大
        ys = []
        for cmd, seg in segs:
            k = {"m": 2, "l": 2, "c": 6, "r": 4}.get(cmd)
            if k:
                v = nums(seg, k)
                ys += v[1::2]
        max_y_holder[0] = max(ys) if ys else 200.0

    for cmd, seg in segs:
        if cmd == "pgfsetrectcap":
            square_cap = True
        elif cmd == "m":
            x, y = nums(seg, 2); d_parts.append(f"M{x} {fy(y)}")
        elif cmd == "l":
            x, y = nums(seg, 2); d_parts.append(f"L{x} {fy(y)}")
        elif cmd == "c":
            v = nums(seg, 6)
            d_parts.append(f"C{v[0]} {fy(v[1])} {v[2]} {fy(v[3])} {v[4]} {fy(v[5])}")
        elif cmd == "r":
            x1, y1, x2, y2 = nums(seg, 4)
            if "\\ubb" in seg:
                continue  # \ubb=\pgfusepath{use as bounding box}：矩形仅声明边界盒，不绘制
            rx, ry2 = min(x1, x2), max(y1, y2)
            rects.append(
                f'<rect x="{rx}" y="{fy(ry2)}" width="{abs(x2-x1)}" height="{abs(y2-y1)}"/>'
            )
        elif cmd == "o":
            d_parts.append("Z")
        # \s = fill+stroke 收尾（样式在根元素），\p 孤立点忽略

    if dim:
        w, h = dim
    else:
        allnums = [float(v) for v in re.findall(r"-?\d+\.?\d*", " ".join(d_parts))]
        xs, ys2 = allnums[0::2], allnums[1::2]
        w = max(xs) if xs else 200.0
        h = max(ys2) if ys2 else 200.0

    cap = ' stroke-linecap="square"' if square_cap else ""
    path = (f'<path d="{" ".join(d_parts)}" fill="currentColor" stroke="currentColor" '
            f'stroke-width="2"{cap}/>') if d_parts else ""
    # viewBox 外扩 1 单位防 stroke 出血裁切
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1 -1 {w+2} {h+2}" '
           f'width="{w}" height="{h}">\n{path}\n' + "\n".join(rects) + "\n</svg>\n")
    return svg

def main() -> None:
    ap = argparse.ArgumentParser(description="pgf → SVG 批量转换（pgfornament-han 数据）")
    ap.add_argument("--src", default=str(SKILL_DIR / "assets" / "pgf"),
                    help="pgf 源目录（默认 skill 内 assets/pgf）")
    ap.add_argument("--dst", default=str(SKILL_DIR / "assets" / "svg"),
                    help="SVG 输出目录（默认 skill 内 assets/svg）")
    ap.add_argument("--force", action="store_true", help="覆盖目标目录已存在的同名文件")
    args = ap.parse_args()

    src, dst = Path(args.src), Path(args.dst)
    if not src.is_dir():
        sys.exit(f"SRC 不存在: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    if hasattr(sys.stdout, "reconfigure"):  # Windows GBK 终端防中文乱码
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    tex = src / "pgflibraryhan.code.tex"
    dims = parse_dims(tex) if tex.exists() else {}
    if not dims:
        print("WARN 尺寸表缺失，回退 bbox 翻转（角点/带纹可能错位），建议把 pgflibraryhan.code.tex 放进 --src 目录")

    ok, skipped, fail = 0, 0, []
    for f in sorted(src.glob("*.pgf")):
        n = int(re.search(r"(\d+)", f.name).group(1))
        out = dst / f"han{n:02d}_{classify(n)}.svg"
        if out.exists() and not args.force:
            skipped += 1
            continue
        try:
            out.write_text(convert(f.read_text(encoding="utf-8", errors="replace"), dims.get(n)), encoding="utf-8")
            ok += 1
        except Exception as e:
            fail.append(f"{f.name}: {e}")
    print(f"converted={ok} skipped(exists, use --force)={skipped} failed={len(fail)} dst={dst}")
    for s in fail:
        print("FAIL", s)

if __name__ == "__main__":
    main()
