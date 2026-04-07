# PyTimeTag

[![](https://img.shields.io/github/actions/workflow/status/hwaipy/PyTimeTag/tests.yml?branch=main)](https://github.com/hwaipy/PyTimeTag/actions?query=workflow%3ATests)
[![](https://img.shields.io/pypi/v/pytimetag)](https://pypi.org/project/pytimetag/)
[![](https://img.shields.io/pypi/pyversions/pytimetag)](https://pypi.org/project/pytimetag/)
[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hwaipy/PyTimeTag/python-coverage-comment-action-data/endpoint.json)](https://github.com/hwaipy/PyTimeTag/tree/python-coverage-comment-action-data)

量子光学实验里常用 **时间标签（time tagging）** 记录单光子到达时刻与通道；除了物理本身，往往还要处理 **时间戳的接收、分块、存储和简单监控**。PyTimeTag 提供一套 Python 库和命令行工具，把这些环节收拢起来，减少临时脚本和重复劳动。

我们正在把常见的各型 TimeTag 设备陆续集成进来；**目前已内置Swabian Instruments（Time Tagger）**。其它品牌或自研板卡也可以按同一套扩展方式 **自行增加设备接口**（实现方式见源码中 `device` 包与 CLI 插件注册）。

支持无硬件时的 **仿真**（`--source simulator`），也支持在选好 `--source` 后接入 **真实硬件**。

- **仓库**：<https://github.com/hwaipy/PyTimeTag>
- **PyPI**：<https://pypi.org/project/pytimetag/>
- **许可证**：GPL-3.0

---


## 环境要求

- **Python**：3.9 及以上（与 `setup.py` 中 `python_requires` 一致）。
- **依赖**：NumPy ≥ 1.25、msgpack、numba、rich（见 `setup.py` 的 `install_requires`）。

---

## 安装

### 仅库与 CLI（仿真，不连硬件）

```bash
python -m pip install -U pytimetag
```

安装完成后可使用入口命令 `pytimetag`；不带参数时与 `--help` 类似，只打印说明、不启动采集。也可显式执行：

```bash
python -m pytimetag --help
```

### 需要 Swabian Time Tagger 硬件时

请同时安装 **可选依赖** `swabian`（会拉取 PyPI 上的 `Swabian-TimeTagger`；另需本机已安装 Swabian 官方驱动/软件，见下文「硬件与 NumPy」）：

```bash
python -m pip install -U "pytimetag[swabian]"
```

> 建议始终用**当前解释器**的完整路径调用 pip，避免装到别的 Python：  
> `"/path/to/python.exe" -m pip install -U "pytimetag[swabian]"`（Windows 若路径含空格请加引号）。

### 从源码安装

```bash
git clone https://github.com/hwaipy/PyTimeTag.git
cd PyTimeTag
python -m pip install -e .
# 如需 Swabian 可选依赖：
python -m pip install -e ".[swabian]"
```

---

## 命令行（`pytimetag`）概览

**若不带任何参数**（命令行里在程序名后面什么也没有），程序**不会**启动采集：先打印完整用法（含英文 epilog），再在**标准输出末尾**附一段中文提示，提醒需指定 `--source` 或其它选项后才会真正运行。

**说明**：`pytimetag -h` / `pytimetag --help` 同样只显示帮助、不采集；它们属于「带了参数」，与「程序名后完全空白」不同。

查看全部参数：

```bash
pytimetag --help
```

### 数据源 `--source`

| 取值 | 含义 |
|------|------|
| `simulator` | 内置仿真器，无需硬件。在**已提供至少一个命令行参数**且未写 `--source` 时，默认使用该值。 |
| `swabian` | Swabian Instruments Time Tagger（需 `pip install "pytimetag[swabian]"` 及本机驱动；仅在选择该源时加载插件）。 |

### 常用参数

| 参数 | 说明 |
|------|------|
| `--output-dir` | 与 `--save` 配合：保存目录（默认 `./store_test`）。 |
| `--save` | 将每个 DataBlock 序列化为文件到输出目录下按日期/小时划分的子目录。 |
| `--split-s` | **按时间**切分时，每个块的时间窗口（秒），默认 `1.0`。 |
| `--split-mode` | `time`：按时间窗口；`channel`：按触发通道事件（见 `--split-channel`）。 |
| `--split-channel` | `split-mode=channel` 时使用的触发通道索引（0–15）。 |
| `--channel-count` | 使用的通道数（默认 8）。 |
| `--resolution` | 时间刻度（秒/ tick），默认 `1e-12`（1 ps）。 |
| `--serial` | **仅硬件源**：设备序列号；多设备时必须指定。 |
| `--hardware-buffer-size` | **仅硬件源**：流缓冲事件数上限（插件语义；Swabian 对应 `n_max_events`，默认 `1000000`）。 |
| `--hardware-poll-s` | **仅硬件源**：轮询间隔（秒；Swabian 默认 `0.002`）。 |
| `--channel` | 可重复；仿真器上配置某通道：`INDEX:key=value,...`（见下例）。 |
| `--trigger-level` / `--deadtime-s` | 可重复；硬件类源上按通道设置触发电平、死时间：`INDEX:值`。 |

仿真器专用：`--seed`、`--update-lo-s`、`--update-hi-s`（更新间隔随机范围）。

---

## CLI 示例（由简到繁）

以下示例在 Windows / Linux / macOS 上均可使用；请将 `pytimetag` 换成 `python -m pytimetag` 若你未把 Scripts 目录加入 PATH。

### 1. 不带参数：只显示帮助

```bash
pytimetag
```

不启动采集；效果与 `pytimetag --help` 接近（多一段文末中文提示），提醒需指定 `--source` 或其它选项。

### 2. 仿真源，不落盘、不保存

```bash
pytimetag --source simulator
```

终端会显示实时表格；按 `Ctrl+C` 结束。也可通过其它任意参数触发运行（例如下一节仅 `--save` 时未写 `--source` 也会默认用仿真器）。

### 3. 指定保存目录并写入 DataBlock 文件

```bash
pytimetag --save --output-dir ./my_data
```

文件会按块创建时间落在 `my_data/YYYY-MM-DD/HH/` 下，扩展名为 `.datablock`。

### 4. 按时间切分：每 2 秒一块

```bash
pytimetag --split-s 2.0 --resolution 1e-12
```

### 5. 按通道事件切分（例如通道 3 上发生事件时切块）

```bash
pytimetag --split-mode channel --split-channel 3
```

### 6. 仿真器：自定义通道与随机种子

默认仿真已对通道 0 使用 `Period`、其余通道 `Random`。若要显式改某一通道（例如通道 1 为 Random、50k 计数）：

```bash
pytimetag --channel "1:mode=Random,random_count=100000" --seed 123
```

可多次 `--channel` 指定多个索引。

### 7. 硬件：`swabian` 源（单台设备）

```bash
pytimetag --source swabian --save --output-dir ./runs
```

若本机只连一台 Time Tagger，通常无需 `--serial`。

### 8. 硬件：多台设备时必须指定序列号

```bash
pytimetag --source swabian --serial YOUR_SERIAL_HERE
```

### 9. 硬件：调大缓冲与轮询间隔（按插件语义）

```bash
pytimetag --source swabian --hardware-buffer-size 2000000 --hardware-poll-s 0.005
```

### 10. 硬件：按通道设置触发电平与死时间（单位与驱动一致）

```bash
pytimetag --source swabian --trigger-level "0:-0.2" --deadtime-s "1:5e-08"
```

---

## 作为库使用（简要）

安装后可在代码中导入 `pytimetag` 包，例如 `DataBlock`、`device_type_manager`、`TimeTagSimulator` 等。若需直接使用 Swabian 设备类，可从子模块导入（**不会**随 `import pytimetag.device` 自动加载 Swabian）：

```python
from pytimetag.device.SwabianTimeTag import SwabianTimeTag
```

具体 API 以各模块文档字符串与测试为准。

---

## 故障排查

| 现象 | 建议 |
|------|------|
| 只输入 `pytimetag` 没有开始采数 | 属预期行为：须带至少一个参数，例如 `pytimetag --source simulator` 或 `pytimetag --save`。 |
| `Unknown device type` / 硬件源未注册 | 确认已 `pip install "pytimetag[swabian]"` 且 `--source` 拼写为 `swabian`。 |
| 多设备报错要求 `--serial` | 使用 `--serial` 与设备管理器显示的序列号一致。 |
| NumPy / `_TimeTagger` 导入错误 | 见上文「硬件与 NumPy」；优先升级 Swabian 软件与 pip 包，或降级 NumPy 至 1.x。 |
| 终端无颜色或乱码 | 使用 Windows Terminal 或现代终端；若重定向到文件，Rich 可能降级为无颜色。 |

---

## 开发与测试

克隆仓库后：

```bash
python -m pip install -e ".[swabian]"
python -m unittest discover -s tests -p 'test*.py'
```

CI 配置见 `.github/workflows/`。
