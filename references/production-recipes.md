# 生产配方：三条流水线

> 来源：2026-10-07 对 dososo/chinese-traditional-patterns（Wényàng）与 liantze/pgfornament-han 的技术考古（报告存 `D:\Claude\项目\08 临时调用\`，归档后见迭代记录）。以下每条均实证可用。

## 配方 A：pgf → SVG 矢量纹（已完成，直接用）

**状态**：转换器 `scripts/pgf2svg.py` 已实测 78/78 成功 + 渲染抽查 5 类纹（几何/回纹/团寿贝塞尔/云纹/鸟形）视觉正确（2026-10-07）。

**重跑/扩充**：

```bash
python D:/Claude/配置/.claude/skills/chinese-patterns/scripts/pg2svg.py   # 默认 skill 内 assets/pgf → assets/svg
python scripts/pgf2svg.py --src <pgf目录> --dst <输出目录>    # 自定义输入输出
python scripts/pgf2svg.py --force                            # 允许覆盖已存在同名 SVG（默认跳过防误覆）
```
只转单个文件：临时建目录软链/复制该 .pgf 进空目录再 --src 指向它。

**映射规则**（新增 .pgf 文件时用）：`\m→M`、`\l→L`、`\c x1 y1 x2 y2 x3 y3→C`（参数序一致）、`\r→<rect>`、`\o→Z`、`\s→fill+stroke`（SVG fill 自动闭合，不加 Z）、`\pgfsetrectcap→stroke-linecap:square`；bp=1/72 英寸直映 viewBox；遇 `\endinput` 截断（防 han19 式死代码）。

**三个已实踩的坑（2026-10-07 修）**：
1. **Y 轴必须翻转**：pgf Y 轴向上、SVG 向下。按官方尺寸表 `pgflibraryhan.code.tex` 的 `\@pgfornamenthanDim` 高度翻转（脚本自动解析该文件；缺失时回退 bbox 并警告）。对称纹样（寿/回/角点）不翻也看不出来，最容易漏——本次是福字/云带全黑暴露的。
2. **`\r`+`\ubb` 不绘制**：`\ubb`=`\pgfusepath{use as bounding box}`（sty L52），其前 `\r` 矩形仅声明边界盒。han55/58/60/64/66/68/70/76 共 8 个文件有；不跳过会垫一个全幅黑矩形。
3. **stroke 出血**：viewBox 外扩 1 单位防边缘笔画裁切（直线类 han29–32 最敏感）。

**合规**：产物派生自 LPPL 1.3c 库，商用 OK；**对外再分发**需：署名"图样 张晨南 / 库代码 LianTze Lim"、附 LPPL 协议、改动文件改名或声明。

**参考调用**（LaTeX 用户）：`\pgfornamenthan[color=red,width=1.5cm]{56}`；TikZ `to[ornamenthan=19]` 可拉伸纹样但会改变高度，慎用。

## 配方 B：AI 生纹样素材（学 wenyang，避其坑）

**教训先行**：wenyang 的图片是 GPT Image 2.0 生成（PNG 内嵌 C2PA 实锤），提示词未公开；其知识文案为 LLM 模板批量生成、**零参考文献、段落互抄**（001 与 011 简介逐字相同、祥云纹关联纹样列出自己）。**学它的流程，不抄它的文案。**

**生图提示词骨架**（通用于 ComfyUI/Kolors/FLUX/GPT Image）：
```
中国传统{纹样名}，{视觉关键词，如：连续藤蔓/放射对称/方折回旋}，
构图：单元纹或二方连续，居中，纯色深底（藏青/赭石/墨黑），
配色：新中式三色以内——石青、赭石、金（或朱砂点缀），
风格：平面化矢量感，线条均匀，留白克制，博物馆图录质感，
要求：无文字、无水印、无透视，可直接做四方连续
```
**铁律**（分工：铁律 1–3 管"素材底图"，铁律 4 管"图鉴整卡"，适用对象不同，勿混用于同一张图）：
1. **只生素材不生整卡**——纹样底图与文字卡片分开（文字后期排版烧进，保证可改）
2. 一次出双稿：彩色主图 + 黑白线描稿（线稿可当 SVG 描摹底/激光雕刻稿）
3. 产出必须过"可连续化"检查：单元边缘要能对接，否则重出
4. 构图公式（仅图鉴卡片用）：半圆开光主图 + 深色地 + 青绿/靛蓝/金三色系——wenyang 全部 100 卡通用此式，辨识度极高
5. 生图执行走 visual-deliver skill：本地 ComfyUI 优先，云端 Kolors 兜底

**批量组织**（照抄 wenyang 数据契约的优点）：
- 编号全局唯一三位补零；按 10 条一批推进，每批一个独立 LLM 会话
- 每条 meta 字段：`id, name_cn, name_en, category, summary, meaning, visual_keywords[], period(约), region, carriers[], composition, modern, colors[](受控色卡), related[], batch, source_note, sha256`
- 受控词表用 select 枚举（寓意族/色名/类目），**杜绝自由文本脏数据**——这是 wenyang CMS 设计里最值得照抄的一条

**考据核实路径**（把"常识"升"据"时走这条）：
1. 首选博物馆官网藏品数据库：故宫博物院数字文物库、国家博物馆、上海博物馆、金沙/三星堆/各地考古所官网（带藏品号截图存档）
2. 图录：《中国纹样史》（田自秉/吴淑生/田青）、《中国古建筑装饰纹样》系列、沈从文《中国古代服饰研究》、原田治《中国の文様》
3. 石窟壁画：敦煌研究院数字敦煌（高清洞窟图像可核时代）
4. 存证格式：`来源机构+藏品名+年代+链接+抓取日期` 记入该纹样 meta 的 `sources[]`

## 配方 C：图录式卡片合成（HTML → 截图）

wenyang 工艺：固定 HTML 模板（1080×1440 poster，思源宋体竖排图录样式）→ Playwright/Chromium 无头截图 → 3:4 卡片 PNG（文字"烧进图"）。

**本机简化版**：
1. 写 HTML 卡片模板（参考尺寸 1080×1440，Source Han Serif SC，竖排中文名大字 + 英文名 + 一句话简介 + 主图位）
2. Playwright 截图：
```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width":1080,"height":1440})
    pg.goto("file:///绝对路径/card.html")
    pg.screenshot(path="card.png", full_page=True)
```
3. 缩略图派生：`480px WebP`（网站用，~45KB/张）
4. 需要"报纸版+瑞士版"双版式交付时，叠加 editorial-design skill 的设计规范

**适用**：纹样图鉴、命理客户档案卡、课程知识卡等"图录感"交付物。
