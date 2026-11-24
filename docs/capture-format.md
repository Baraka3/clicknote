# 采集格式说明

扩展导出的 `tutorial-capture-*.json` 是这套工具的**唯一输入协议**。任何能产出这个格式的东西都能接进来——自己写脚本采集、从测试框架导出、或者手工拼一个。

## 顶层结构

```json
{
  "generator": "tutorial-maker-extension/1.1.0",
  "exported_at": "2026-11-24T02:05:45.455Z",
  "pages": ["https://example.com/apply"],
  "viewport": { "w": 1920, "h": 1031 },
  "actions": [ ... ],
  "dropped": 35
}
```

| 字段 | 说明 |
|---|---|
| `generator` | 产出者标识，含版本号。`1.0.0` 没有 `scrollY`，`1.1.0` 起有 |
| `pages` | 去重后的页面 URL 列表，仅供人看 |
| `viewport` | 采集时的视口尺寸。**仅供参考**，每帧自带 `viewport`，以帧为准 |
| `dropped` | 因截图限速被丢弃的帧数。这些帧没有图，导出时已剔除 |
| `actions` | 帧数组，按时间顺序 |

## actions[] 单帧

```json
{
  "index": 12,
  "kind": "click",
  "tag": "button",
  "text": "Place order",
  "sensitive": null,
  "box": { "x": 0.0625, "y": 0.8424, "w": 0.1688, "h": 0.0722 },
  "redact": [[0.0625, 0.2597, 0.4375, 0.0611]],
  "scrollY": 0,
  "docH": 720,
  "viewport": { "w": 1280, "h": 720 },
  "page_url": "https://demo.example.com/checkout",
  "shot": "data:image/png;base64,..."
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `index` | int | **采集时**的序号。注意：导出时被丢弃的帧会让序号不连续，**不要拿它当数组下标** |
| `kind` | string | `click` / `input` / `submit` / `scroll` |
| `tag` | string | 被操作元素的标签名，小写 |
| `text` | string | 元素文字或 placeholder。敏感字段会被替换成 `••••`、`手机号` 这类占位 |
| `sensitive` | string\|null | `password` / `otp` / `phone` / `email` / `idcard` / `bankcard` |
| `box` | object\|null | 被操作元素的边界，**对象**。`scroll` 帧没有 |
| `redact` | array | 当屏所有敏感输入框的边界，**数组的数组** |
| `scrollY` | int | 截图瞬间的页面滚动位置，1.1.0 起有 |
| `docH` | int | 截图瞬间的文档总高度 |
| `viewport` | object | 该帧的视口尺寸 |
| `page_url` | string | 完整 URL，用于分页拼接 |
| `shot` | string | `data:image/png;base64,...` |

### box 和 redact 的类型不一样

这是最容易踩的坑：

- `box` 是**对象** `{"x":..,"y":..,"w":..,"h":..}`，因为它只有一个
- `redact` 是**数组的数组** `[[x,y,w,h], ...]`，因为一屏可能有多个敏感框

`render.py` 遇到类型错的 `redact` 会在 `int()` 处报 `invalid literal for int()`，看到这个错就是格式写错了。

### 坐标约定

全部是**归一化到 0~1** 的值，因此与分辨率无关：

- x / w 除以视口宽度 `innerWidth`
- y / h 除以视口高度 `innerHeight`
- **原点在视口左上角，不是页面左上角**。要换算成页面坐标，得自己加 `scrollY`

这一点直接决定了能不能拼长图：

```
页面坐标 y = 该帧 scrollY + 归一化 y × 视口高度
```

### scroll 帧的特殊之处

`kind: "scroll"` 的帧是滚动补采的，没有 `box`（没有可点元素），它的作用有两个：

1. 补上纯阅读段落的内容，避免整段缺图
2. 提供 `scrollY`，让 `stitch.py` 能算出位置

`import_capture.py` 会把 scroll 帧单独存成 `shots/scrollNN.png`，不放进 `steps.json`，避免污染教程步骤。

## 中间产物：steps.json

`import_capture.py` 输出的可编辑文件，`render.py` 的输入。

```json
{
  "doc": { "title": "", "intro": "", "meta": "", "outro": "" },
  "steps": [
    {
      "index": 1,
      "title": "点击提交",
      "body": "正文写为什么和注意什么。",
      "file": "capture/shots/step01.png",
      "redact": [[0.0625, 0.2597, 0.4375, 0.0611]],
      "highlight": [[0.0625, 0.8424, 0.1688, 0.0722]],
      "arrows": [[0.5, 0.9, 0.55, 0.72]],
      "notes": ["补充说明"],
      "badge": null
    }
  ]
}
```

| 字段 | 说明 |
|---|---|
| `index` | 决定渲染顺序与图片文件名，**改这里就是重排步骤** |
| `title` | 动作型标题，10 字内。由人补写，不由脚本生成 |
| `body` | 2~3 句，超过就拆进 `notes` |
| `redact` | 打码区，坐标与采集格式一致 |
| `highlight` | 高亮框。默认取采集来的 `box`，可手工覆盖 |
| `arrows` | `[x1,y1,x2,y2]`，可选 |
| `notes` | 图下方的要点 |
| `badge` | 图上序号徽标，默认不画（序号由标题承担） |

渲染时会忽略任何以 `_` 开头的字段，所以 `_kind`、`_page`、`_scroll_y` 这些调试信息可以留着。

## 版本差异

| 版本 | 变化 |
|---|---|
| 1.0.0 | 只有 `click` / `input` / `submit`，无 `scrollY` / `docH` |
| 1.1.0 | 加 `scroll` 帧、`scrollY`、`docH`，支持整页拼接 |

遇到没有 `scrollY` 的旧素材，`stitch.py` 会直接拒绝执行。这是有意的——图像匹配在表单页上算不准，硬拼会拼出错位的图，不如不做。
