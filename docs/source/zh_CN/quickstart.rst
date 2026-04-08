快速使用
========

环境与依赖
----------

- **Python**：3.9 及以上（与 ``setup.py`` 中 ``python_requires`` 一致）。
- **核心依赖**：NumPy、msgpack、numba、rich、duckdb（见 ``setup.py`` / ``requirements.txt``）。

安装
----

从 PyPI 安装（仅库与 CLI，不含 Swabian 驱动侧可选包）：

.. code-block:: bash

   python -m pip install -U pytimetag

需要连接 Swabian Time Tagger 时，安装可选依赖（会拉取 PyPI 上的 ``Swabian-TimeTagger``；本机仍需厂商驱动/软件）：

.. code-block:: bash

   python -m pip install -U "pytimetag[swabian]"

从源码可编辑安装：

.. code-block:: bash

   git clone https://github.com/hwaipy/PyTimeTag.git
   cd PyTimeTag
   python -m pip install -e .
   python -m pip install -e ".[swabian]"

入口命令为 ``pytimetag``；也可使用 ``python -m pytimetag``。

第一条命令
----------

查看全部参数：

.. code-block:: bash

   pytimetag --help

若命令行在程序名之后完全没有任何参数，程序只打印帮助并在文末给出中文提示，不会启动采集。带任意参数（例如 ``--save``）才会进入运行逻辑；未写 ``--source`` 时默认使用仿真器 ``simulator``。

运行仿真（终端实时表格，Ctrl+C 结束）：

.. code-block:: bash

   pytimetag --source simulator

保存 DataBlock 文件
-------------------

.. code-block:: bash

   pytimetag --save --output-dir ./my_data

或使用别名 ``--datablock-dir``。文件按块创建时间写入 ``my_data/YYYY-MM-DD/HH/*.datablock``。

在线处理与 DuckDB（默认开启）
------------------------------

开启在线处理时，分析结果会写入 DuckDB，默认路径为 ``./store_test/pytimetag.duckdb``。可自定义：

.. code-block:: bash

   pytimetag --save --output-dir ./blocks --storage-db ./analytics/run.duckdb

关闭在线处理：

.. code-block:: bash

   pytimetag --no-post-process

常用切分示例
------------

按时间窗口（例如每 2 秒一块）：

.. code-block:: bash

   pytimetag --split-s 2.0 --resolution 1e-12

按通道事件切块（例如在通道 3 上出现事件时切块）：

.. code-block:: bash

   pytimetag --split-mode channel --split-channel 3

下一步
------

完整参数与行为说明见 :doc:`cli`；离线回放分析见 :doc:`offline_processing`；序列化文件格式与体积估算见 :doc:`datablock_format`。
