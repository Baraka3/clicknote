# AGENTS.md

给 AI 编码助手读的项目说明。人不用看，看 README。

## 这个项目是什么

Clicknote 把浏览器操作录成素材（JSON），再由 AI 或人补写文案，渲染成带打码和高亮的图文教程。

三条链路，别搞混：

| 产物 | 谁生成 | 谁消费 |
|---|---|---|
| `tutorial-capture-*.json` | Chrome 扩展（`extension/`） | `scripts/import_capture.py` |
| `steps.json` | import 脚本 + 人或 AI 补写 | `scripts/render.py` |
| `tutorial.md` / `.html` | render 脚本 | 最终读者 |

## 目录

```
extension/          Manifest V3 扩展，纯原生 JS，无构建步骤，改完在 chrome://extensions 点刷新即生效
scripts/            Python，只依赖 Pillow
  import_capture.py JSON → shots/ + steps.json + pages.json
  render.py         steps.json → 打码、高亮、排版 → md + html
  stitch.py         按 scrollY 拼整页长图
  extract_steps.py  录屏视频抽帧（不装扩展时的备选）
SKILL.md            给 AI 的步骤判定与文案规范，这是本项目的核心资产
docs/               采集协议、打码判据
examples/minimal/   虚构数据的可跑示例
```

## 改代码前必须知道的

1. **坐标全部是归一化 0~1**，原点在视口左上角，不是页面左上角。要换算页面坐标得加 `scrollY`。
2. **`box` 是对象，`redact` 是数组的数组**。类型搞反会让 `render.py` 在 `int()` 处报 `invalid literal for int()`。
3. **`actions[i].index` 不等于数组下标**。导出时丢弃的帧会让 index 不连续，取第 N 张图要用 `actions[N-1]`。
4. **打码判断看「能否指向具体个人」，不看控件类型**。下拉框选出来的学历、州一样要遮。判据在 `docs/redaction-rules.md`。
5. **扩展不要引入打包工具、不要引第三方库**。源文件即加载文件，这是刻意的设计。

## 改完怎么验证

```bash
python scripts/import_capture.py examples/minimal/capture.json demo
cp examples/minimal/steps.example.json demo/steps.json
python scripts/render.py demo/steps.json demo/out
```

期望 `demo/out/` 下有 `tutorial.md`、`tutorial.html` 和两张图。跑完删掉 `demo/`。

改了渲染的，打开 `demo/out/images/step02.png` 看两件事：遮挡块有没有盖住姓名那一行、高亮框有没有贴住 Place order 按钮。

## 不要做的事

- 不要为了兼容旧素材去改采集协议。缺 `scrollY` 的素材由 `stitch.py` 显式拒绝，这是有意的。
- 不要把图片内容或用户采集的截图上传到任何地方。
- 不要在示例里使用真实业务数据，连按钮文案都不要沿用真实场景的。
- 不要给 `render.py` 加 GUI 或交互式提示，它要能在脚本里无人值守跑完。

## 提交约定

一个 PR 做一件事。改渲染逻辑附上改前改后对比图。改采集逻辑说明用什么网站、什么操作验证的。
