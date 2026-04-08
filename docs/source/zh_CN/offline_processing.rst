数据离线处理
============

概述
----

在线采集阶段写出的 ``.datablock`` 文件可以在事后反复加载，并使用各类 analyser 进行离线分析。
这适用于批处理、参数回放、以及不连接硬件时的复现实验。

离线处理基本流程
----------------

#. 扫描目录中的 ``*.datablock`` 文件（按时间排序）。
#. 逐个读取字节并 ``DataBlock.deserialize``。
#. 创建 analyser，必要时 ``turnOn`` 并配置参数。
#. 对每个 DataBlock 调用 ``dataIncome``，收集结果。

示例：批量加载并运行两个 analyser
---------------------------------

.. code-block:: python

   from pathlib import Path

   from pytimetag import CounterAnalyser, HistogramAnalyser, DataBlock


   def run_offline(datablock_root: str):
       files = sorted(Path(datablock_root).rglob("*.datablock"))
       if not files:
           print("no datablock files found")
           return

       counter = CounterAnalyser()
       counter.turnOn()

       hist = HistogramAnalyser(channelCount=8)
       hist.turnOn(
           {
               "Sync": 0,
               "Signals": [1, 2, 3],
               "ViewStart": -100000,
               "ViewStop": 100000,
               "BinCount": 200,
               "Divide": 1,
           }
       )

       for p in files:
           block = DataBlock.deserialize(p.read_bytes())

           counter_result = counter.dataIncome(block)
           hist_result = hist.dataIncome(block)

           # 这里可替换成写入数据库/文件的逻辑
           print(p.name, counter_result["Configuration"], len(hist_result["Histograms"]))


   if __name__ == "__main__":
       run_offline("./my_data")

注意事项
--------

- ``DataBlock.deserialize`` 默认读取单块；若你自行拼接了多个块，可使用 ``allowMultiDataBlock=True``。
- 离线处理与 CLI 的在线处理互补：在线处理偏实时监控，离线处理偏回放、重算和批量统计。
- 若离线结果也想落库，可直接复用 ``pytimetag.storage.Storage`` 写入 DuckDB。
