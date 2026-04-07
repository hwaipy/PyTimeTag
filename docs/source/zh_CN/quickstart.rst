快速开始
========

查看命令帮助
------------

.. code-block:: bash

   pytimetag --help

运行仿真数据源
--------------

.. code-block:: bash

   pytimetag --source simulator

保存 DataBlock 文件
-------------------

.. code-block:: bash

   pytimetag --save --output-dir ./my_data

按时间窗口切分
--------------

.. code-block:: bash

   pytimetag --split-s 2.0 --resolution 1e-12

按通道事件切分
--------------

.. code-block:: bash

   pytimetag --split-mode channel --split-channel 3
