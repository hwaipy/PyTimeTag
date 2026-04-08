命令行详细手册（CLI）
======================

入口与帮助
----------

安装包后提供命令 ``pytimetag``（等价 ``python -m pytimetag``）。

.. code-block:: bash

   pytimetag --help

**无参数行为**：若 ``argv`` 在程序名后为空，只打印帮助和文末中文提示，**不启动采集**。``pytimetag -h`` / ``--help`` 属于“有参数”，同样不采集。

数据源 ``--source``
--------------------

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - 取值
     - 含义
   * - ``simulator``
     - 内置仿真器；在已提供至少一个其它参数且未写 ``--source`` 时为默认值。
   * - ``swabian``
     - Swabian Instruments Time Tagger；需 ``pip install "pytimetag[swabian]"`` 与本机驱动；仅在选择该源时加载插件。

多设备时硬件源通常需要 ``--serial`` 指定序列号。

DataBlock 文件与目录
--------------------

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - 参数
     - 说明
   * - ``--save``
     - 将每个 DataBlock 序列化写入磁盘。
   * - ``--output-dir`` / ``--datablock-dir``
     - 保存根目录，默认 ``./store_test``。实际路径为 ``根目录/YYYY-MM-DD/HH/时间戳.datablock``。
   * - ``--split-s``
     - ``--split-mode time`` 时，每个块的时间窗口（秒），默认 ``1.0``。
   * - ``--split-mode``
     - ``time``：按时间窗口；``channel``：按触发通道上的事件切块。
   * - ``--split-channel``
     - ``split-mode=channel`` 时使用的通道索引（0–15），默认 ``0``。
   * - ``--channel-count``
     - 通道数，默认 ``8`` （内部打包仍为 16 通道布局）。
   * - ``--resolution``
     - 秒/tick，默认 ``1e-12`` （1 ps）。

在线处理与 DuckDB
------------------

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - 参数
     - 说明
   * - ``--post-process`` / ``--no-post-process``
     - 是否启用在线处理（运行内置分析器并对结果落库）；默认 **开启**。
   * - ``--storage-db``
     - DuckDB 数据库文件路径，默认 ``./store_test/pytimetag.duckdb``。仅在开启后处理时连接；父目录会自动创建。

关闭在线处理时不会打开 DuckDB。

硬件相关（依赖具体 ``--source`` 插件）
--------------------------------------

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - 参数
     - 说明
   * - ``--serial``
     - 设备序列号；多设备时常必填。
   * - ``--hardware-buffer-size``
     - 流缓冲事件数上限（插件语义；Swabian 对应 ``n_max_events``，默认 ``1000000``）。
   * - ``--hardware-poll-s``
     - 轮询间隔（秒；Swabian 默认 ``0.002``）。
   * - ``--trigger-level``
     - 可重复。格式 ``INDEX:V``，按通道触发电平。
   * - ``--deadtime-s``
     - 可重复。格式 ``INDEX:SECONDS``，按通道死时间。

仿真器专用
----------

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - 参数
     - 说明
   * - ``--seed``
     - RNG 种子，默认 ``42``。
   * - ``--update-lo-s`` / ``--update-hi-s``
     - 仿真批次更新间隔随机范围（秒）。
   * - ``--channel``
     - 可重复。格式 ``INDEX:key=value,...``，配置该通道模式与参数（如 ``mode=Random,random_count=50000``）。

示例（由简到繁）
----------------

只打印帮助：

.. code-block:: bash

   pytimetag

仿真、不落盘：

.. code-block:: bash

   pytimetag --source simulator

保存到目录并自定义 DuckDB：

.. code-block:: bash

   pytimetag --save --datablock-dir ./my_data --storage-db ./my_data/meta.duckdb

每 2 秒一块：

.. code-block:: bash

   pytimetag --split-s 2.0

按通道 3 事件切块：

.. code-block:: bash

   pytimetag --split-mode channel --split-channel 3

Swabian 单台设备：

.. code-block:: bash

   pytimetag --source swabian --save --output-dir ./runs

多台设备指定序列号：

.. code-block:: bash

   pytimetag --source swabian --serial YOUR_SERIAL

仿真器改写某通道：

.. code-block:: bash

   pytimetag --channel "1:mode=Random,random_count=100000" --seed 123

硬件触发电平与死时间：

.. code-block:: bash

   pytimetag --source swabian --trigger-level "0:-0.2" --deadtime-s "1:5e-08"

故障排查提示
------------

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - 现象
     - 建议
   * - 只输入 ``pytimetag`` 不采数
     - 预期行为；请加参数，如 ``--source simulator`` 或 ``--save``。
   * - 硬件源未注册 / Unknown device
     - 确认已安装 ``pytimetag[swabian]`` 且 ``--source`` 拼写正确。
   * - 要求提供 ``--serial``
     - 多设备时用与设备管理器一致的序列号。

更底层的数据布局见 :doc:`datablock_format`；扩展 CLI 与设备见 :doc:`extending`。
