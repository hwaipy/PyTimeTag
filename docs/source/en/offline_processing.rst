Offline Processing
==================

Overview
--------

``.datablock`` files produced during acquisition can be loaded later for repeated analysis.
This is useful for replay, parameter sweeps, and batch statistics without live hardware.

Typical workflow
----------------

#. Discover ``*.datablock`` files from a directory.
#. Read bytes and call ``DataBlock.deserialize``.
#. Create analysers and call ``turnOn`` if needed.
#. Run ``dataIncome`` on each block and collect outputs.

Example: batch load and run analysers
-------------------------------------

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
           print(p.name, counter_result["Configuration"], len(hist_result["Histograms"]))


   if __name__ == "__main__":
       run_offline("./my_data")

Notes
-----

- ``DataBlock.deserialize`` reads one block by default; use ``allowMultiDataBlock=True`` if your bytes contain multiple concatenated blocks.
- Offline processing complements online processing in CLI: online for real-time monitoring, offline for replay and recomputation.
- If you also want DB persistence in offline workflows, reuse ``pytimetag.storage.Storage`` with DuckDB.
