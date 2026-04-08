自行扩展
========

概述
----

扩展点主要有三类：

#. **CLI 硬件数据源**：在 ``pytimetag.device.source_registry`` 中登记名称 → 插件模块，由 ``device_type_manager.create_device_for_cli_source`` 动态加载。
#. **设备类型与工厂**：向 ``device_type_manager`` 注册 :class:`~pytimetag.device.base.TimeTagDeviceFactory` 子类，实现发现与连接。
#. **分析器**：继承 :class:`~pytimetag.Analyser.Analyser`，实现 ``analysis``，由 CLI 或自建管线调用 ``dataIncome``。

CLI 数据源插件
--------------

映射表位于 ``pytimetag/device/source_registry.py`` 中的 ``CLI_SOURCE_PLUGINS``：键为 ``--source`` 取值，值为可导入的模块路径（仅在选中该源时 ``import``）。

插件模块需暴露如下函数（签名示意）：

.. code-block:: python

   def create_device(manager, args, console, live, on_words) -> Optional[TimeTagDevice]:
       ...

- ``manager``：全局 ``device_type_manager``，用于 ``connect(device_type, serial_number, dataUpdate=..., **kwargs)``。
- ``on_words``：回调 ``(words, live) -> None``，应将设备送来的打包时间戳流交给上层（与仿真器相同约定）。
- 返回 ``None`` 表示放弃启动（例如已打印帮助、ABI 不匹配）。

参考实现：``pytimetag/device/sources/swabian.py``（在模块内 ``import`` 对应工厂以完成注册，再 ``connect``）。

设备工厂注册
------------

``pytimetag.device.manager.DeviceTypeManager`` 维护 ``device_type`` 到 Factory 的映射。工厂类应设置类属性 ``device_type``，并实现 ``discover()``、``connect()`` 等（见 ``pytimetag.device.base``）。

新厂商设备通常步骤：

#. 实现 ``TimeTagDevice`` / ``TimeTagDeviceFactory``。
#. 在包导入时 ``device_type_manager.register(MyFactory)`` （参见 Swabian 工厂注册方式）。
#. 若需 CLI：在 ``CLI_SOURCE_PLUGINS`` 增加条目，并在插件 ``create_device`` 里 ``connect`` 你的设备类型字符串。

分析器
------

``Analyser`` 通过 ``turnOn`` / ``turnOff`` 控制是否参与 ``dataIncome``；``dataIncome`` 内调用 ``analysis(dataBlock)``，并将配置写入返回字典的 ``Configuration`` 字段。

CLI 在开启 ``--post-process``（在线处理）时实例化内置分析器并将每次 ``dataIncome`` 的返回写入 DuckDB（集合名与类名一致）。自建程序可直接实例化子类并调用 ``dataIncome``，或注册进 ``pytimetag/__main__.py`` 中的列表（维护上游时需同步修改）。

测试与质量
----------

仓库 ``tests/`` 下含单元测试；新增扩展时请为关键逻辑补充测试，并运行：

.. code-block:: bash

   python -m unittest discover -s tests -p 'test*.py'
