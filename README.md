# PyTimeTag

[![](https://img.shields.io/github/actions/workflow/status/hwaipy/PyTimeTag/tests.yml?branch=main)](https://github.com/hwaipy/PyTimeTag/actions?query=workflow%3ATests)
[![](https://img.shields.io/pypi/v/pytimetag)](https://pypi.org/project/pytimetag/)
[![](https://img.shields.io/pypi/pyversions/pytimetag)](https://pypi.org/project/pytimetag/)
[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/hwaipy/PyTimeTag/python-coverage-comment-action-data/endpoint.json)](https://github.com/hwaipy/PyTimeTag/tree/python-coverage-comment-action-data)

量子光学实验里常用 **时间标签（time tagging）** 记录单光子到达时刻与通道；PyTimeTag 提供 Python 库与命令行工具，覆盖时间戳的接收、分块（DataBlock）、序列化/落盘、简单监控与在线处理（含可选 DuckDB 落库）。已内置 **Swabian Instruments（Time Tagger）** 可选接入；无硬件时可用 **仿真**（`--source simulator`）。

- **仓库**：<https://github.com/hwaipy/PyTimeTag>
- **PyPI**：<https://pypi.org/project/pytimetag/>
- **许可证**：GPL-3.0

---

## 文档结构（Sphinx）

完整文档在仓库 `docs/source/`，中英双语。建议阅读顺序：

| 章节 | 中文 | English |
|------|------|---------|
| 1. 简介 | [zh_CN/introduction.rst](docs/source/zh_CN/introduction.rst) | [en/introduction.rst](docs/source/en/introduction.rst) |
| 2. 快速使用 | [zh_CN/quickstart.rst](docs/source/zh_CN/quickstart.rst) | [en/quickstart.rst](docs/source/en/quickstart.rst) |
| 3. CLI 详细手册 | [zh_CN/cli.rst](docs/source/zh_CN/cli.rst) | [en/cli.rst](docs/source/en/cli.rst) |
| 4. 数据离线处理 | [zh_CN/offline_processing.rst](docs/source/zh_CN/offline_processing.rst) | [en/offline_processing.rst](docs/source/en/offline_processing.rst) |
| 5. 自行扩展 | [zh_CN/extending.rst](docs/source/zh_CN/extending.rst) | [en/extending.rst](docs/source/en/extending.rst) |
| 6. DataBlock 存储格式 | [zh_CN/datablock_format.rst](docs/source/zh_CN/datablock_format.rst) | [en/datablock_format.rst](docs/source/en/datablock_format.rst) |

本地构建 HTML（需 `requirements-docs.txt`）：

```bash
make -C docs html-en
make -C docs html-zh
```

输出目录：`docs/build/html/en/` 与 `docs/build/html/zh_CN/`。说明见 [docs/README.md](docs/README.md)。

---

## 环境要求

- **Python**：3.9 及以上。
- **依赖**：NumPy、msgpack、numba、rich、duckdb 等（见 `setup.py`）。

---

## 安装

```bash
python -m pip install -U pytimetag
```

Swabian 硬件（可选）：

```bash
python -m pip install -U "pytimetag[swabian]"
```

从源码：

```bash
git clone https://github.com/hwaipy/PyTimeTag.git
cd PyTimeTag
python -m pip install -e ".[swabian]"
```

入口命令：`pytimetag` 或 `python -m pytimetag`。**若命令行在程序名后无任何参数**，只打印帮助、不启动采集。

---

## 命令行速览

```bash
pytimetag --help
```

常用示例：

```bash
pytimetag --source simulator
pytimetag --save --output-dir ./my_data
pytimetag --save --storage-db ./analytics/run.duckdb
```

参数说明（含在线处理开关 `--post-process` / `--storage-db`、`--datablock-dir`、切分模式、硬件选项等）见上文 **CLI 详细手册** 链接。

---

## Web GUI（Vue + Quasar）

已提供内置 GUI 服务端（FastAPI + WebSocket + Celery）与前端工程骨架（`webui/`）。

启动 API + GUI（默认仅监听本机 `127.0.0.1:8787`）：

```bash
pytimetag gui --host 127.0.0.1 --port 8787
```

离线任务使用 Celery，需单独启动 worker（默认 Redis）：

```bash
celery -A pytimetag.gui.worker:celery_app worker --loglevel=INFO
```

若控制台出现 `No supported WebSocket library detected`，请补装：

```bash
python -m pip install websockets wsproto
```

前端源码在 `webui/`（Quasar）：

```bash
cd webui
npm install
npm run dev
npm run build
```

`npm run build` 产物将输出到 `pytimetag/gui/webui_dist/`，并可随 `pip` 安装包一起发布。

关键接口：

- `GET /api/v1/meta`
- `GET /api/v1/sources`
- `GET /api/v1/session/status`
- `POST /api/v1/session/start`
- `POST /api/v1/session/stop`
- `GET /api/v1/analyzers`
- `PUT /api/v1/analyzers/{name}`
- `GET /api/v1/settings`
- `PUT /api/v1/settings`
- `GET /api/v1/datablocks`
- `POST /api/v1/offline/process`
- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/logs`
- `WS /ws/metrics`
- `WS /ws/logs`
- `GET /healthz`
- `GET /readyz`

Docker 一键启动（Redis + API + Worker）：

```bash
docker compose up --build
```

默认访问：`http://127.0.0.1:8787`

---

## 作为库使用

安装后可 `import pytimetag`，使用 `DataBlock`、`device_type_manager`、`TimeTagSimulator` 等。Swabian 设备类需从子模块导入（不会随 `import pytimetag.device` 自动加载）：

```python
from pytimetag.device.SwabianTimeTag import SwabianTimeTag
```

API 由 Sphinx AutoAPI 生成，见各语言文档中的 **API 参考** 章节。

---

## 开发与测试

```bash
python -m pip install -e ".[swabian]"
python -m unittest discover -s tests -p 'test*.py'
```

CI 见 `.github/workflows/`。
