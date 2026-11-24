# 最小示例

两份文件，两步流程，数据全部虚构（Alex Chen / 221B Baker Street 都是假的）。

| 文件 | 说明 |
|---|---|
| `capture.json` | 模拟扩展导出的采集文件，含 2 帧、1 张内嵌截图 |
| `steps.example.json` | 补好标题与正文的 `steps.json`，演示字段怎么填 |

## 跑一遍

在仓库根目录执行：

```bash
python scripts/import_capture.py examples/minimal/capture.json demo
cp examples/minimal/steps.example.json demo/steps.json
python scripts/render.py demo/steps.json demo/out
```

`demo/out/` 下会出现 `tutorial.md`、`tutorial.html` 和 `images/step01.png`、`step02.png`。

`steps.json` 里的 `file` 字段写的是 `shots/step01.png` 这种相对路径，渲染时按 `steps.json` 所在目录解析，所以整个目录可以随便搬。

## 这个示例想说明什么

1. **打码靠坐标，不靠识别**：`redact` 里的 `[0.0625, 0.2597, 0.4375, 0.0611]` 就是那一栏输入框的位置，归一化后与分辨率无关。
2. **高亮框同样来自 DOM**：`highlight` 取的按钮真实边界，所以能贴边。
3. **文案是人写的**：`title` 是动作（"填收货人姓名"），`body` 写的是坑（"和持卡人不一致会被风控拦下"），不是复述图里看得见的东西。
