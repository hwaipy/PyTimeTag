命令行接口
==========

入口命令
--------

安装后可使用 ``pytimetag`` 命令。

.. code-block:: bash

   pytimetag --help

主要参数
--------

- ``--source``：数据源后端（如 ``simulator``、``swabian``）
- ``--save`` 与 ``--output-dir``：保存序列化后的 DataBlock
- ``--split-mode``、``--split-s``、``--split-channel``：切分策略
- ``--channel-count`` 与 ``--resolution``：采集设置
- ``--serial``：多设备场景下选择硬件序列号

仿真器相关参数
--------------

- ``--seed``
- ``--update-lo-s``
- ``--update-hi-s``
- ``--channel``：格式为 ``INDEX:key=value,...``，可重复

硬件相关参数
------------

- ``--hardware-buffer-size``
- ``--hardware-poll-s``
- ``--trigger-level``：格式为 ``INDEX:V``，可重复
- ``--deadtime-s``：格式为 ``INDEX:SECONDS``，可重复
