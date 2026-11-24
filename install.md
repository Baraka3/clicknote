# StepCraft 安装说明（给 AI 助手读）

你正在为一个用户安装 StepCraft。它是一个 Chrome 扩展加一组 Python 脚本，用来把网页操作录成图文教程素材。

请按顺序执行，每一步都有验证方法。**只有在涉及浏览器界面操作时才停下来让用户动手**，其余都由你自己完成。

---

## 0. 前置检查

先确认三件事，缺哪个先解决哪个，别往下走：

```bash
python --version     # 需要 3.9 以上
python -c "import PIL; print(PIL.__version__)"   # 需要 Pillow
```

- Python 低于 3.9：告诉用户升级，别尝试绕过。
- 没有 Pillow：`pip install pillow`（若报权限错，用 `pip install --user pillow`）。
- Windows 上 `python` 不识别时，依次试 `py -3`、`python3`。

再确认浏览器：用户需要 Chrome、Edge 或其他 Chromium 内核浏览器（版本 102 以上，因为扩展用了 Manifest V3）。**Firefox 不支持**，别试。

## 1. 取代码

```bash
git clone https://github.com/<你的用户名>/stepcraft.git
cd stepcraft
```

没有 git 的话，让用户从仓库页面下载 ZIP 解压，效果一样。

验证：`ls stepcraft/extension/manifest.json` 能看到文件。

## 2. 装依赖

```bash
pip install pillow
```

只需要 Pillow。脚本全部用标准库加 Pillow，不要额外装 numpy、opencv。

验证：

```bash
python scripts/import_capture.py --help 2>&1 | head -3
```

能打印用法即正常（该脚本没有 `--help`，报 `usage` 或 `JSON 里没有可用的步骤` 都算跑通了，只要不是 `ModuleNotFoundError`）。

## 3. 装浏览器扩展

**这一步要用户自己点，你把步骤念给他，然后等他回话。**

让用户做：

1. 在浏览器地址栏输入 `chrome://extensions`（Edge 是 `edge://extensions`）
2. 打开右上角的 **开发者模式**
3. 点左上角 **加载已解压的扩展程序**
4. 选择 `<仓库路径>/extension` 这个目录
5. 工具栏出现一个蓝色图标即为成功，可点拼图图标把它固定出来

用户确认装好后，继续下一步。

## 4. 自检

用仓库自带的最小示例跑一遍，确认管线通：

```bash
python scripts/import_capture.py examples/minimal/capture.json .tmp-check
python scripts/render.py .tmp-check/steps.json .tmp-check/out
ls .tmp-check/out/images | head
```

期望：`.tmp-check/out/` 下有 `tutorial.md`、`tutorial.html`、`images/step01.png`。

跑通就把 `.tmp-check` 删掉，告诉用户装好了，并给一句用法：

> 打开要演示的网页 → 点扩展图标「开始采集」→ 正常操作 → 「结束采集」→「导出素材」→ 把 JSON 路径发给我。

## 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `加载已解压的扩展程序` 报错 | 选错了目录 | 必须选到含 `manifest.json` 的 `extension/`，不是仓库根目录 |
| 扩展装了但角标不涨 | 当前页面是 `chrome://` 或扩展商店 | 内部页面无法注入脚本，换普通网页 |
| `ModuleNotFoundError: PIL` | Pillow 装到了别的 Python | 用 `python -m pip install pillow`，确保和运行脚本的是同一个解释器 |
| 导出的 JSON 里 `actions` 为空 | 采集期间没触发点击/输入 | 检查是否点了「开始采集」，以及是否切换到了别的域名（域名限定会忽略站外操作） |
| `stitch.py` 报「无 scrollY」 | 素材来自 1.0.0 版扩展 | 重新采集；旧素材没有滚动位置，无法拼接，脚本拒绝执行是正确的 |

## 边界

- 不要修改 `extension/` 里的代码来绕过安装问题，先排查环境。
- 不要在用户没确认的情况下清理他的浏览器扩展。
- 采集到的截图含用户隐私，**不要上传到任何地方**，报告路径即可。
