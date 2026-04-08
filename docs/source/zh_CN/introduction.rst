简介
====

PyTimeTag 面向 **时间标签（time tagging）** 实验与工程：记录单光子（或其它事件）的到达时刻与通道索引。库与命令行工具覆盖 **数据接入 → 按策略切块（DataBlock）→ 序列化/落盘 → 在线处理与监控** 的常见路径，减少一次性脚本与重复胶水代码。

**当前能力概览**

- **数据源**：内置 **仿真器**（无硬件即可跑通流程）；**Swabian Instruments Time Tagger** 通过可选依赖接入（按需加载，不污染最小安装）。
- **切块**：按时间窗口或按指定通道上的事件将连续时间戳流切分为多个 :class:`~pytimetag.datablock.DataBlock`。
- **存储**：可将 DataBlock 序列化为扩展名 ``.datablock`` 的文件；CLI 在在线处理开启时可将分析结果写入 DuckDB（路径可配置）。
- **扩展**：新硬件可通过设备工厂注册与 CLI 插件模块接入；分析逻辑可基于 :class:`~pytimetag.Analyser.Analyser` 扩展。

**仓库与发布**

- 源码：<https://github.com/hwaipy/PyTimeTag>
- PyPI：<https://pypi.org/project/pytimetag/>
- 许可证：GPL-3.0

文档其余章节：:doc:`quickstart` → :doc:`cli` → :doc:`offline_processing` → :doc:`extending` → :doc:`datablock_format`；API 参考见 :doc:`api`。
