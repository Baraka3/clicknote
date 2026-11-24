# 变更记录

格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.1.0] - 2026-11-24

### 新增

- **滚动分段补采**：滚停 420ms 且幅度超过半屏时补拍一帧，标记为 `kind: "scroll"`。解决长页面纯阅读段落整段缺图的问题
- **每帧记录 `scrollY` / `docH`**：用于把同页多帧按页面坐标拼成整页长图。图像匹配做不到这件事——表单插入报错提示会让布局变化，算不准
- `scripts/stitch.py`：按 `scrollY` 精确拼接整页长图。打码在拼接后统一执行，取所有帧 `redact` 的并集，避免某一帧漏标就露
- `import_capture.py` 输出 `pages.json`，按页面归组帧清单供拼接使用
- 首屏自动补拍一张，页面打开即有一屏内容时不会漏
- 弹窗显示「含滚动补采 N 张」

### 改进

- `render.py` 的高亮框描边从 3px 收到 2px、填充透明度从 30% 降到 18%，框不再比被框元素显得「胖」
- `render.py` 的实心遮挡色从 `rgb(226,232,240)` 加深到 `rgb(176,190,207)`，在白色表单上能明确看出遮挡
- `render.py` 支持正文内空行分段，Markdown 与 HTML 都能正确渲染成多段
- `render.py` 的图片路径改为相对 `steps.json` 所在目录解析，找不到再回退当前目录。整个素材目录可以任意搬动
- `import_capture.py` 把 `scroll` 帧单独存为 `shots/scrollNN.png`，不混进教程步骤
- 步骤序号改为连续编号，不再受导出时丢弃帧的影响

### 修复

- 旧版本导出的素材缺少 `scrollY`，拼接脚本会明确拒绝并提示原因，不做猜测

## [1.0.0] - 2026-11-23

### 首次发布

- Chrome 扩展（Manifest V3）：点击、输入、提交三类动作自动截图，记录被操作元素的 DOM 边界
- 域名限定：只采集开始时的站点，站外操作自动忽略
- 暂停 / 继续：跨域流程可中断
- 悬停预截图：鼠标停留 320ms 先拍，拿到点击前的原貌
- 敏感字段自动识别：密码、验证码、手机号、邮箱、身份证、银行卡
- `import_capture.py`：JSON 解码为截图与 `steps.json`
- `render.py`：打码、高亮、生成 `tutorial.md` 与单文件 `tutorial.html`
- `extract_steps.py`：录屏视频抽帧（不装扩展时的备选路径）
