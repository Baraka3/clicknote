# Clicknote · 点击笔记

简体中文 | [English](README.en.md)

**把浏览器操作录成素材，让 AI 写出准确、脱敏、可复现的图文教程。**

- **采集**：Chrome / Edge 扩展，点击、输入、滚动都记，坐标来自 DOM 而非图像识别，误差 ≤1px
- **生成**：Python 脚本打码、高亮、排版，输出 Markdown 与单文件 HTML
- **判断**：`SKILL.md` 定义哪一帧算一步、标题怎么写、哪里必须打码
- **适用**：需要维护大量操作文档、且已经在用 Claude Code / Cursor / WorkBuddy 的人

> **维护模式**：接受 bug 修复与文档纠错，不承诺新功能排期。这个项目的价值在判断标准，不在功能数量。

---

## 这不是又一个截图录屏工具

[Scribe](https://scribehow.com)、[Tango](https://tango.us)、[Mimik](https://github.com/westpoint-io/mimik) 都是好工具，它们解决的是「录完自动出一份文档」。它们的文案是模板生成的（"Click Submit"），你能改，但改起来比写还慢。

Clicknote 走另一条路：**只负责把原始素材采集准，判断交给 AI。**

| | 模板式工具 | Clicknote |
|---|---|---|
| 谁决定哪一帧算一步 | 规则 | AI，按你给的规范 |
| 文案怎么写 | 模板填充 | AI 按你的项目语气重写，或你直接指定 |
| 打码 | 关键词识别 | 按「能否指向具体个人」逐项判断，坐标来自 DOM |
| 产物 | 成品文档 | 中间格式 JSON + steps.json，可反复重写 |
| 门槛 | 装完就能用 | 需要一个 AI 助手配合 |

代价很清楚：**它不能开箱即用**。你得有 Claude Code / Cursor / WorkBuddy 这类能读文件、能跑命令的 AI 助手，才能发挥价值。如果你只想要一个录完就出 PDF 的工具，去用 Mimik，别用这个。

## 它准在哪

普通截图工具靠图像识别找元素，误差几个像素到几十像素。这套东西的坐标直接来自 `getBoundingClientRect()`，实测误差 ≤1px，所以高亮框能严丝合缝套住按钮，不会「呲」出去一圈。

打码同理：靠 DOM 定位而不是 OCR，不会漏字、不会把相邻文字一起糊掉。

## 工作流

```
① 装扩展 → 点开始采集 → 正常操作网页 → 导出 JSON
② python scripts/import_capture.py capture.json capture
③ 补写每步标题与正文（人或 AI 做）
④ python scripts/render.py capture/steps.json 产出目录
   ↓
   images/step01.png … + tutorial.md + tutorial.html
```

第 ③ 步是质量分水岭。Skill 里写了判断标准：标题必须是动作（"点击提交"而不是"提交页面"）、正文写为什么和坑（验证码有效期、必填项、跳转到哪）、不写"如图所示"这类废话。

## 安装

### 方式一：让 AI 帮你装

在 Claude Code / Cursor / WorkBuddy 里粘这段：

```
帮我安装 Clicknote：先读
https://raw.githubusercontent.com/Baraka3/clicknote/main/install.md
按里面的步骤把浏览器扩展和 Python 脚本装好，装完跑一次自检。
```

AI 会自己检查环境、下载、装依赖，只在需要你点浏览器按钮时停下来问你。

### 方式二：手动装

```bash
git clone https://github.com/Baraka3/clicknote.git
cd clicknote
pip install pillow

# 扩展：Chrome 打开 chrome://extensions → 右上角开「开发者模式」
# → 左上角「加载已解压的扩展程序」→ 选 clicknote/extension 目录
```

Edge 一样：`edge://extensions` → 开发人员模式 → 加载解压缩的扩展。

## 采集格式

扩展导出的 JSON 每一帧长这样：

```json
{
  "index": 12,
  "kind": "click",
  "tag": "button",
  "text": "Place order",
  "box": { "x": 0.0625, "y": 0.8424, "w": 0.1688, "h": 0.0722 },
  "redact": [[0.0625, 0.2597, 0.4375, 0.0611]],
  "scrollY": 480,
  "docH": 1180,
  "viewport": { "w": 1280, "h": 720 },
  "page_url": "https://demo.example.com/checkout",
  "shot": "data:image/png;base64,..."
}
```

`box` 是被点元素的归一化边界，`redact` 是当屏所有敏感输入框，`scrollY` / `docH` 用于把同页多帧拼成整页长图。字段全表见 [`docs/capture-format.md`](docs/capture-format.md)。

## 三个采集期能力

| 能力 | 解决什么 |
|---|---|
| 域名限定 | 切去查资料、看邮箱时自动忽略，导出文件不会混进无关浏览 |
| 滚动分段补采 | 长页面里纯阅读的段落没有点击，不补采就整段缺图。滚停 420ms 且幅度过半个屏幕时补一帧 |
| 悬停预截图 | 点击会把选项置灰、跳走。鼠标停留 320ms 先拍一张，拿到点击前的原貌 |

## 打码规则

判断标准是**这一项能否指向具体某个人**，不是控件类型。

- 必遮：姓名、地址全要素（含州、邮编）、生日、证件号、邮箱、电话、职位、收入、学历、账户情况
- 可留：Employment status、citizenship、residency status 这类几千万人共享的类别声明

详细判据和踩过的坑写在 [`docs/redaction-rules.md`](docs/redaction-rules.md)。

一句话概括我们踩过的教训：**别按「下拉框还是输入框」判断，要按「这个值能不能缩小到某个人」判断。**

## 已知局限

1. **截图有硬上限**：Chrome 限制每秒 2 次截图。操作过快时该步保留记录但没有图。每次操作间隔 0.5 秒以上。
2. **只采主文档**，iframe 内的操作不记录。
3. **预截图可能早于点击几百毫秒**：若这期间页面滚动过，`box` 会和画面对不上，高亮坐标需复核。
4. **滚动补采不是自动长截图**：只在停留处补帧。页面中途插入报错提示会让布局变化，此时 `stitch.py` 拼出的长图会错位。旧素材没记 `scrollY` 时脚本会直接拒绝，不瞎猜。
5. **需要 AI 助手**：没有 AI 配合，你得自己写 `steps.json` 里的文案。

## 目录

```
extension/          Chrome 扩展（Manifest V3，纯原生 JS，无构建）
scripts/
  import_capture.py  JSON → 截图 + steps.json + pages.json
  render.py          打码、高亮、排版 → md/html
  stitch.py          按 scrollY 拼整页长图
  extract_steps.py   录屏视频抽帧（不想装扩展时用）
SKILL.md             给 AI 的判断规范（本仓库即一个 skill 包）
AGENTS.md            给 AI 编码助手的项目约定
llms.txt             结构化索引，供 LLM 检索与摘要
docs/                采集格式、打码判据
examples/minimal/    最小可跑示例
```

## 许可证

MIT。随便用，包括商用，保留版权声明即可。

---

如果这东西帮你省了半天截图，点个 Star 能让更多人找到它。
