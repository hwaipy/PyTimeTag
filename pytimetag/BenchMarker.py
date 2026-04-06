from pytimetag import DataBlock, HistogramAnalyser, EncodingAnalyser
from pytimetag.device.Simulator import TimeTagSimulator, pack_timetag
from pytimetag.device.datablock_packer import (
    DataBlockPackerPath,
    DataBlockStreamPacker,
    SplitByChannelEvent,
    SplitByTimeWindow,
)
import argparse
import os
import sys
import time
import numpy as np
import numba
from rich.console import Console
from rich.progress import (
  BarColumn,
  Progress,
  TaskProgressColumn,
  TextColumn,
  TimeElapsedColumn,
  TimeRemainingColumn,
)

if __name__ == '__main__':
  UNIT_SIZE = 20
  numba.set_num_threads(1)

  # Packer grid: must stay in sync with benchMarkingDataBlockStreamPacker()
  PACKER_DURATION_LIST = (5,)
  PACKER_LOAD_ROUNDS = 4
  PACKER_OPS_PER_ROW = 6

  _SERDES_EVENT_SIZES = (10000, 100000, 1000000, 4000000, 10000000)
  _SUM_SERDES_R = float(sum(_SERDES_EVENT_SIZES))

  def _noop_advance(_delta):
    pass

  # Top of ladder = 2.5M events/lab-second per ch1–4 (before optional cap); half of former 5M load.
  PACKER_BASE_HZ_PER_CH = 2_500_000

  def _packer_max_rate_per_ch():
    """
    Cap each signal channel's events per lab-second (ladder uses PACKER_BASE_HZ_PER_CH×frac, then min).
    - Env PYTIMETAG_BENCH_PACKER_MAX_RATE_PER_CH: default '2500000' (target load for this bench).
    - '0' / negative → uncapped (full ladder up to BASE×frac).
    """
    raw = os.environ.get('PYTIMETAG_BENCH_PACKER_MAX_RATE_PER_CH', '2500000')
    raw = raw.strip() if isinstance(raw, str) else str(raw)
    if raw == '' or raw.lower() in ('none', 'max', 'full', 'uncapped'):
      return None
    try:
      v = int(raw, 0)
    except ValueError:
      return PACKER_BASE_HZ_PER_CH
    if v <= 0:
      return None
    return v

  def _packer_chunk_subdiv():
    """Sub-intervals per lab second (1=whole second per chunk). Default 2 ≈ half-second chunks for ~2GB RAM."""
    raw = os.environ.get('PYTIMETAG_BENCH_PACKER_CHUNK_SUBDIV', '2')
    try:
      v = int(str(raw).strip(), 0)
    except ValueError:
      return 2
    return max(1, v)

  def _packer_counts_per_sub(total, n_sub):
    """Split ``total`` into ``n_sub`` nonnegative integers summing to ``total``."""
    if n_sub <= 0:
      return [total]
    if total <= 0:
      return [0] * n_sub
    base = total // n_sub
    rem = total % n_sub
    return [base + (1 if i < rem else 0) for i in range(n_sub)]

  def _packer_n_per_ch(load_round):
    frac = (0.125, 0.25, 0.5, 1.0)[int(load_round) & 3]
    raw = max(1, int(PACKER_BASE_HZ_PER_CH * frac))
    cap = _packer_max_rate_per_ch()
    if cap is None:
      return raw
    return min(raw, cap)

  def _packer_n_events(duration_s, load_round):
    n_per_ch = _packer_n_per_ch(load_round)
    return int(duration_s) * (4 * n_per_ch + 1)

  def _benchmark_weight(key):
    """
    Abstract cost on one scale: mostly ~event volume; simulator uses ~5e6 units ≈ 5 s wall
    so it stays visible next to multi-million-event workloads.
    """
    if key == 'packer':
      return float(
        sum(
          _packer_n_events(d, lr)
          for d in PACKER_DURATION_LIST
          for lr in range(PACKER_LOAD_ROUNDS)
        )
      )
    if key == 'simulator':
      return 5_000_000.0
    if key == 'serdes':
      return 6.0 * _SUM_SERDES_R
    if key == 'histogram':
      return 3.0 * _SUM_SERDES_R
    if key == 'encoding':
      return 6.0 * _SUM_SERDES_R
    raise KeyError(key)

  def benchMarkingSerDeser(advance=None):
    configs = [
        ("Period List", (10000, 100000, 1000000, 4000000, 10000000), lambda r: {0: ("Period", r)}, 1e-12),
        ("Period List, 16 ps", (10000, 100000, 1000000, 4000000, 10000000), lambda r: {0: ("Period", r)}, 16e-12),
        ("Random List", (10000, 100000, 1000000, 4000000, 10000000), lambda r: {0: ("Random", r)}, 1e-12),
        ("Random List, 16 ps", (10000, 100000, 1000000, 4000000, 10000000), lambda r: {0: ("Random", r)}, 16e-12),
        ("Mixed List", (10000, 100000, 1000000, 4000000, 10000000), lambda r: {0: ("Period", int(r / 10)), 1: ("Random", int(r / 10 * 4)), 5: ("Random", int(r / 10 * 5)), 10: ("Period", 10), 12: ("Random", 1)}, 1e-12),
        ("Mixed List, 16 ps", (10000, 100000, 1000000, 4000000, 10000000), lambda r: {0: ("Period", int(r / 10)), 1: ("Random", int(r / 10 * 4)), 5: ("Random", int(r / 10 * 5)), 10: ("Period", 10), 12: ("Random", 1)}, 16e-12),
    ]
    adv = advance if advance is not None else _noop_advance
    for config in configs:
      rt = ReportTable(f'DataBlock serial/deserial: {config[0]}', ("Event Size", "Data Rate", "Serial Time", "Deserial Time")).setFormatter(0, formatterKMG).setFormatter(1, lambda dr: "{:.2f}".format(dr)).setFormatter(2, lambda second: "{:.2f} ms".format(second * 1000)).setFormatter(3, lambda second: "{:.2f} ms".format(second * 1000))
      for r in config[1]:
        bm = doBenchMarkingSerDeser(config[2](r), config[3])
        rt.addRow(r, bm[0], bm[1], bm[2])
        adv(float(r))
      rt.output()

  def doBenchMarkingSerDeser(dataConfig, resolution=1e-12):
    generatedDB = DataBlock.generate({"CreationTime": 100, "DataTimeBegin": 10, "DataTimeEnd": 1000000000010}, dataConfig)
    testDataBlock = generatedDB if resolution == 1e-12 else generatedDB.convertResolution(resolution)
    data = testDataBlock.serialize()
    recovered = DataBlock.deserialize(data)
    consumingSerialization = doBenchMarkingOpertion(lambda: testDataBlock.serialize())
    infoRate = len(data) / sum([len(ch) for ch in testDataBlock.content])
    consumingDeserialization = doBenchMarkingOpertion(lambda: DataBlock.deserialize(data))
    return (infoRate, consumingSerialization, consumingDeserialization)

  def benchMarkingMultiHistogramAnalyser(advance=None):
    adv = advance if advance is not None else _noop_advance
    rt = ReportTable('MultiHistogramAnalyser', ("Total Event Size", "1 Ch", "2 Ch (1, 1)", "4 Ch (5, 3, 1, 1)")).setFormatter(0, formatterKMG).setFormatter(1, lambda second: f"{(second * 1000):.2f} ms").setFormatter(2, lambda second: f"{(second * 1000):.2f} ms").setFormatter(3, lambda second: f"{(second * 1000):.2f} ms")
    for r in [10000, 100000, 1000000, 4000000, 10000000]:
      bm = doBenchMarkingMultiHistogramAnalyser(r, [[1], [1, 1], [5, 3, 1, 1]])
      rt.addRow(r, bm[0], bm[1], bm[2])
      adv(3.0 * float(r))
    rt.output()

  def doBenchMarkingMultiHistogramAnalyser(totalSize, sizes):
    mha = HistogramAnalyser(16)
    mha.turnOn({"Sync": 0, "Signals": [1], "ViewStart": 0, "ViewStop": 40000000, "BinCount": 1000, "Divide": 1})
    bm = []
    for size in sizes:
      m = {}
      for s in range(len(size) + 1):
        if s == 0:
          m[s] = ["Period", 25000]
        else:
          m[s] = ["Pulse", 100000000, int(size[s - 1] / sum(size) * totalSize), 1000]
      dataBlock = DataBlock.generate({"CreationTime": 100, "DataTimeBegin": 0, "DataTimeEnd": 1000000000000}, m)
      mha.turnOn({"Signals": [i + 1 for i in range(len(size))]})
      bm.append(doBenchMarkingOpertion(lambda: mha.dataIncome(dataBlock)))
    return bm

  def benchMarkingEncodingAnalyser(advance=None):
    adv = advance if advance is not None else _noop_advance
    rt = ReportTable('Encoding Analyser', ("Total Event Size", "RN (8)", "RN (32)", "RN (128)")).setFormatter(0, formatterKMG).setFormatter(1, lambda second: f"{(second * 1000):.2f} ms").setFormatter(2, lambda second: f"{(second * 1000):.2f} ms").setFormatter(3, lambda second: f"{(second * 1000):.2f} ms")
    for r in [10000, 100000, 1000000, 4000000, 10000000]:
      bm = doBenchMarkingEncodingAnalyser(r, [8, 32, 128], [8, 32, 128])
      rt.addRow(r, bm[0], bm[1], bm[2])
      adv(3.0 * float(r))
    rt.output()

    rt = ReportTable('Encoding Analyser (Long RandomNumber)', ("Total Event Size", "RN (8)", "RN (32)", "RN (128)")).setFormatter(0, formatterKMG).setFormatter(1, lambda second: f"{(second * 1000):.2f} ms").setFormatter(2, lambda second: f"{(second * 1000):.2f} ms").setFormatter(3, lambda second: f"{(second * 1000):.2f} ms")
    for r in [10000, 100000, 1000000, 4000000, 10000000]:
      bm = doBenchMarkingEncodingAnalyser(r, [8, 32, 128], [20000000] * 3)
      rt.addRow(r, bm[0], bm[1], bm[2])
      adv(3.0 * float(r))
    rt.output()

  def doBenchMarkingEncodingAnalyser(totalSize, rnLimits, rnLengths):
    bm = []
    for i in range(len(rnLimits)):
      rnLimit = rnLimits[i]
      rnLength = rnLengths[i]
      mha = EncodingAnalyser(16, rnLimit)
      mha.turnOn({"Period": 10000, "TriggerChannel": 0, "SignalChannel": 1, "RandomNumbers": np.linspace(0, rnLength - 1, rnLength, dtype='<i4') % rnLimit})
      dataBlock = DataBlock.generate({"CreationTime": 100, "DataTimeBegin": 0, "DataTimeEnd": 1000000000000}, {0: ["Period", 10000], 1: ["Pulse", 100000000, totalSize, 100]})
      bm.append(doBenchMarkingOpertion(lambda: mha.dataIncome(dataBlock)))
    return bm

  def doBenchMarkingOpertion(operation, duration_s=1.0):
    operation()
    stop = time.time() + duration_s
    count = 0
    while time.time() < stop:
      operation()
      count += 1
    # Mean operation wall-time over the configured timing window.
    return (duration_s + time.time() - stop) / count

  def benchMarkingDataBlockStreamPacker(advance=None):
    """
    Realistic-ish load for :class:`DataBlockStreamPacker`: ch0 = GPS 1PPS (one tick per
    lab second), time windows 1 s / 0.1 s at 1 ps resolution; ch1–4 scale up to 2.5M/s
    each (4 load steps). Streams are built in **time chunks** (see
    PYTIMETAG_BENCH_PACKER_CHUNK_SUBDIV, default 2) to limit peak alloc during build.
    For each table row, chunks and packed words are **materialized once** before timing;
    measured ms/s is **DataBlockStreamPacker feed / feed_from_packed only** (no numpy
    generation or pack_timetag in the timed section).
    Total timing budget ~5 s wall (6 ops × N rows).
    """
    adv = advance if advance is not None else _noop_advance
    # Per-row: streaming removes giant peak; merge gen+pack_words share; warmup + 6× timed.
    _p_gen_pk, _p_wu, _p_tm = 0.70, 0.10, 0.20
    resolution = 1e-12
    ticks_per_s = int(round(1.0 / resolution))
    ticks_100ms = max(1, ticks_per_s // 10)
    # 5 lab seconds → TW 1s sees splits; peak round ≈ 5×(4×2.5M) signal + 5 PPS (chunked feed).
    duration_list = PACKER_DURATION_LIST
    n_load_rounds = PACKER_LOAD_ROUNDS
    ops_per_row = PACKER_OPS_PER_ROW
    packer_op_s = 5.0 / max(1, len(duration_list) * n_load_rounds * ops_per_row)

    def _packer_ms_per_lab_s(time_per_feed_sec, lab_seconds):
      """One feed pass covers ``lab_seconds`` of timeline → ms per lab-second."""
      return (time_per_feed_sec * 1000.0) / max(float(lab_seconds), 1e-9)

    rt = ReportTable(
      'DataBlockStreamPacker (GPS 1PPS ch0; see units line below)',
      (
        'Lab s',
        'rnd',
        'events/s',
        'TW1s ms/s',
        'TW.1s ms/s',
        'PPS ms/s',
        'filt ms/s',
        'TW+PPS ms/s',
        'pk ms/s',
      ),
    ).setFormatter(0, lambda s: '{:.0f}'.format(s)).setFormatter(
      1, lambda s: str(int(s))
    ).setFormatter(2, formatterKMG).setFormatter(
      3, lambda x: '{:.3f}'.format(x)
    ).setFormatter(
      4, lambda x: '{:.3f}'.format(x)
    ).setFormatter(
      5, lambda x: '{:.3f}'.format(x)
    ).setFormatter(
      6, lambda x: '{:.3f}'.format(x)
    ).setFormatter(
      7, lambda x: '{:.3f}'.format(x)
    ).setFormatter(
      8, lambda x: '{:.3f}'.format(x)
    )
    for duration_s in duration_list:
      for load_round in range(n_load_rounds):
        w_row = float(_packer_n_events(duration_s, load_round))
        n_events = int(w_row)
        n_sub = _packer_chunk_subdiv()
        chunk_list = list(
          _iter_packer_bench_chunks(duration_s, load_round, ticks_per_s, n_sub)
        )
        words_list = [pack_timetag(ts_i, ch_i) for ts_i, ch_i in chunk_list]
        adv(w_row * _p_gen_pk)

        tw1s = DataBlockStreamPacker(
          [DataBlockPackerPath('w', SplitByTimeWindow(ticks_per_s))]
        )
        tw01 = DataBlockStreamPacker(
          [DataBlockPackerPath('w', SplitByTimeWindow(ticks_100ms))]
        )
        pps = DataBlockStreamPacker(
          [DataBlockPackerPath('c', SplitByChannelEvent(0))]
        )
        filt = DataBlockStreamPacker(
          [
            DataBlockPackerPath(
              'f',
              SplitByTimeWindow(ticks_per_s),
              channels=(1, 2, 3, 4),
            )
          ]
        )
        dual = DataBlockStreamPacker(
          [
            DataBlockPackerPath('a', SplitByTimeWindow(ticks_per_s)),
            DataBlockPackerPath('b', SplitByChannelEvent(0)),
          ]
        )
        stream_pk = DataBlockStreamPacker(
          [DataBlockPackerPath('w', SplitByTimeWindow(ticks_per_s))]
        )

        def op_tw1():
          tw1s.reset()
          for ts_i, ch_i in chunk_list:
            tw1s.feed(ts_i, ch_i)
          tw1s.flush()

        def op_tw01():
          tw01.reset()
          for ts_i, ch_i in chunk_list:
            tw01.feed(ts_i, ch_i)
          tw01.flush()

        def op_pps():
          pps.reset()
          for ts_i, ch_i in chunk_list:
            pps.feed(ts_i, ch_i)
          pps.flush()

        def op_filt():
          filt.reset()
          for ts_i, ch_i in chunk_list:
            filt.feed(ts_i, ch_i)
          filt.flush()

        def op_dual():
          dual.reset()
          for ts_i, ch_i in chunk_list:
            dual.feed(ts_i, ch_i)
          dual.flush()

        def op_pk():
          stream_pk.reset()
          for w_i in words_list:
            stream_pk.feed_from_packed(w_i)
          stream_pk.flush()

        for op in (op_tw1, op_tw01, op_pps, op_filt, op_dual, op_pk):
          op()
        adv(w_row * _p_wu)

        tw = doBenchMarkingOpertion(op_tw1, packer_op_s)
        adv(w_row * (_p_tm / ops_per_row))
        tw01 = doBenchMarkingOpertion(op_tw01, packer_op_s)
        adv(w_row * (_p_tm / ops_per_row))
        pp = doBenchMarkingOpertion(op_pps, packer_op_s)
        adv(w_row * (_p_tm / ops_per_row))
        fi = doBenchMarkingOpertion(op_filt, packer_op_s)
        adv(w_row * (_p_tm / ops_per_row))
        du = doBenchMarkingOpertion(op_dual, packer_op_s)
        adv(w_row * (_p_tm / ops_per_row))
        sec_pk = doBenchMarkingOpertion(op_pk, packer_op_s)
        adv(w_row * (_p_tm / ops_per_row))

        ev_s = n_events / float(duration_s)
        rt.addRow(
          duration_s,
          load_round,
          ev_s,
          _packer_ms_per_lab_s(tw, duration_s),
          _packer_ms_per_lab_s(tw01, duration_s),
          _packer_ms_per_lab_s(pp, duration_s),
          _packer_ms_per_lab_s(fi, duration_s),
          _packer_ms_per_lab_s(du, duration_s),
          _packer_ms_per_lab_s(sec_pk, duration_s),
        )
    print(
      '  Units: events/s = total events per lab-second of simulated timeline; '
      'ms/s = wall ms per lab-second for packer feed only (chunk build & pack_timetag '
      'done before timing). TW.1s = 0.1 s time window.'
    )
    rt.output()

  def _datablock_packer_bench_one_chunk(sec, sub, n_sub, load_round, ticks_per_s):
    """
    One sorted (ts, ch) chunk: lab second ``sec``, sub-interval ``sub`` of ``n_sub``.
    ch0 PPS tick only on the last sub-interval of each lab second (timestamp ``t1``).
    """
    n_per_ch = _packer_n_per_ch(load_round)
    t0 = sec * ticks_per_s
    t1 = (sec + 1) * ticks_per_s
    span = t1 - t0
    u0 = t0 + (span * sub) // n_sub
    u1 = t0 + (span * (sub + 1)) // n_sub
    if u1 <= u0:
      u1 = u0 + 1
    counts = _packer_counts_per_sub(n_per_ch, n_sub)
    n_ev_ch = counts[sub]
    ts_parts = []
    ch_parts = []
    margin = max(1, (u1 - u0) // 10000)
    if margin * 2 >= (u1 - u0):
      margin = max(1, (u1 - u0) // 4)
    for ch in range(1, 5):
      if n_ev_ch <= 0:
        continue
      if n_ev_ch == 1:
        ticks = np.array([(u0 + u1) // 2], dtype=np.int64)
      else:
        lo = u0 + margin
        hi = u1 - margin
        if hi <= lo:
          lo, hi = u0, u1 - 1
        ticks = np.linspace(lo, hi, num=n_ev_ch, dtype=np.int64)
      ts_parts.append(ticks)
      ch_parts.append(np.full(ticks.shape[0], ch, dtype=np.int64))
    if sub == n_sub - 1:
      ts_parts.append(np.array([t1], dtype=np.int64))
      ch_parts.append(np.array([0], dtype=np.int64))
    if not ts_parts:
      return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)
    ts = np.concatenate(ts_parts)
    ch = np.concatenate(ch_parts)
    order = np.lexsort((ch, ts))
    return ts[order], ch[order]

  def _iter_packer_bench_chunks(duration_s, load_round, ticks_per_s, n_sub):
    for sec in range(int(duration_s)):
      for sub in range(n_sub):
        yield _datablock_packer_bench_one_chunk(sec, sub, n_sub, load_round, ticks_per_s)

  def benchMarkingSimulator(advance=None):
    """
    Measure TimeTagSimulator throughput: tight loop of step() for ~5 s wall time.
    Reports process CPU time vs wall time (generation dominates; no thread sleep).
    """
    adv = advance if advance is not None else _noop_advance
    duration_s = 5.0
    label, wall_s, events, ev_per_s, cpu_s, cpu_ratio = doBenchMarkingSimulator(duration_s)
    rt = ReportTable(
      'TimeTagSimulator data rate (step() loop, ~{:.0f} s wall, no background thread)'.format(duration_s),
      ("Load", "Wall s", "uint64 events", "events/s", "CPU s", "CPU/Wall"),
    ).setFormatter(1, lambda s: "{:.3f}".format(s)).setFormatter(2, formatterKMG).setFormatter(
      3, lambda r: "{:.3e}".format(r) if r >= 1e6 else "{:.1f}".format(r)
    ).setFormatter(4, lambda s: "{:.3f}".format(s)).setFormatter(5, lambda x: "{:.1f}%".format(x * 100.0))
    rt.addRow(label, wall_s, events, ev_per_s, cpu_s, cpu_ratio)
    rt.output()
    adv(_benchmark_weight('simulator'))

  def doBenchMarkingSimulator(duration_s):
    """
    Repeated step() for approximately duration_s seconds (perf_counter).
    Returns (description, wall_seconds, total_events, events_per_wall_s, process_cpu_seconds, cpu_seconds/wall_seconds).
    """
    total = [0]

    def cb(arr):
      total[0] += int(arr.size)

    channel_count = 8
    sim = TimeTagSimulator(
      cb,
      channel_count=channel_count,
      seed=42,
      resolution=1e-12,
      update_interval_range_s=(0.05, 0.08),
      realtime_pacing=True,
    )
    for i in range(channel_count):
      if i < 4:
        sim.set_channel(
          i,
          mode='Period',
          period_count=500000,
          threshold_voltage=-1.0,
          reference_pulse_v=1.0,
        )
      else:
        sim.set_channel(
          i,
          mode='Random',
          random_count=300000,
          threshold_voltage=-1.0,
          reference_pulse_v=1.0,
        )

    t0 = time.perf_counter()
    c0 = time.process_time()
    while time.perf_counter() - t0 < duration_s:
      sim.step()
    wall_s = time.perf_counter() - t0
    cpu_s = time.process_time() - c0
    if wall_s <= 0:
      wall_s = 1e-9
    ev = total[0]
    label = "{} ch: 4x Period 500 kHz + 4x Random 300 kHz (fixed 15 ms window/step)".format(channel_count)
    return (label, wall_s, ev, ev / wall_s, cpu_s, cpu_s / wall_s)

  def formatterKMG(value):
    if value < 0:
      return "-"
    if value < 1e2:
      return str(value)
    if value < 1e3:
      return f"{value / 1e3:.3f} K"
    if value < 1e4:
      return f"{value / 1e3:.2f} K"
    if value < 1e5:
      return f"{value / 1e3:.1f} K"
    if value < 1e6:
      return f"{value / 1e6:.3f} M"
    if value < 1e7:
      return f"{value / 1e6:.2f} M"
    if value < 1e8:
      return f"{value / 1e6:.1f} M"
    if value < 1e9:
      return f"{value / 1e9:.3f} G"
    if value < 1e10:
      return f"{value / 1e9:.2f} G"
    if value < 1e11:
      return f"{value / 1e9:.1f} G"
    if value < 1e12:
      return f"{value / 1e12:.3f} T"
    if value < 1e13:
      return f"{value / 1e12:.2f} T"
    if value < 1e14:
      return f"{value / 1e12:.1f} T"
    return str(value)

  class ReportTable:
    def __init__(self, title, headers, cellWidth=UNIT_SIZE):
      self.title = title
      self.headers = headers
      self.cellWidth = cellWidth
      self.rows = []
      self.formatters = {}

    def setFormatter(self, column, formatter):
      self.formatters[column] = formatter
      return self

    def addRow(self, *item):
      if len(item) != len(self.headers):
        raise RuntimeError("Dimension of table of matched.")
      self.rows.append(item)
      return self

#     def addRows(rows: List[Any]*) = rows.map(addRow).head

    def output(self):
      output = ''
      totalWidth = len(self.headers) * (1 + self.cellWidth) + 1
      output += ("+" + "-" * (totalWidth - 2) + "+\n")
      output += ("|" + self.complete(self.title, totalWidth - 2, alignment="center") + "|\n")
      output += ("+" + '-' * (totalWidth - 2) + "+\n")
      output += ("|" + '|'.join([self.complete(header, self.cellWidth) for header in self.headers]) + "|\n")
      for row in self.rows:
        output += '|' + '|'.join([(self.complete(self.__getFormatter(i)(row[i]), self.cellWidth)) for i in range(len(row))]) + "|\n"
      output += ("+" + "-" * (totalWidth - 2) + "+")
      print(output)

    def complete(self, content, width, filler=" ", alignment="Center"):
      if len(content) > width:
        return content[0: width - 3] + "..."
      else:
        diff = width - len(content)
        alignment = alignment.lower()
        if alignment == 'left':
          return content + filler * diff
        elif alignment == 'right':
          return filler * diff + content
        elif alignment == 'center':
          return filler * int(diff / 2) + content + filler * (diff - int(diff / 2))
        else:
          raise RuntimeError('bad alignment: {}'.format(alignment))

    def __getFormatter(self, name):
      if self.formatters.__contains__(name):
        return self.formatters[name]
      else:
        return lambda item: str(item)

  def _benchmark_registry():
    """(key, description, callable). Order is used for --all."""
    return (
      ('packer', 'DataBlockStreamPacker: reset + feed / feed_from_packed', benchMarkingDataBlockStreamPacker),
      ('simulator', 'TimeTagSimulator: step() throughput (~5 s wall)', benchMarkingSimulator),
      ('serdes', 'DataBlock serialize / deserialize', benchMarkingSerDeser),
      ('histogram', 'MultiHistogramAnalyser.dataIncome', benchMarkingMultiHistogramAnalyser),
      ('encoding', 'EncodingAnalyser.dataIncome (two tables)', benchMarkingEncodingAnalyser),
    )

  def _registry_map():
    return {k: (desc, fn) for k, desc, fn in _benchmark_registry()}

  def _print_benchmark_list():
    print('Available benchmarks:')
    for i, (key, desc, _) in enumerate(_benchmark_registry(), start=1):
      print('  {:2}  {:12}  {}'.format(i, key, desc))

  def _parse_choice_tokens(tokens, reg_keys):
    """Map user tokens (indices or keys) to registry keys; raises ValueError on bad input."""
    order = [k for k, _, _ in _benchmark_registry()]
    key_set = set(reg_keys)
    norm = [x.strip().lower() for x in tokens if x.strip()]
    if any(t in ('a', 'all') for t in norm):
      return list(order)
    keys = []
    for raw in tokens:
      t = raw.strip().lower()
      if not t or t in ('a', 'all'):
        continue
      if t.isdigit():
        idx = int(t)
        if idx < 1 or idx > len(order):
          raise ValueError('out-of-range index: {!r} (use 1-{})'.format(raw, len(order)))
        keys.append(order[idx - 1])
      elif t in key_set:
        keys.append(t)
      else:
        raise ValueError('unknown benchmark: {!r}'.format(raw))
    return keys

  def _prompt_benchmark_choices(retries_left=8):
    _print_benchmark_list()
    print("Enter number(s) or id(s), comma-separated; 'a' or empty = all.")
    try:
      line = input('Choice: ').strip()
    except EOFError:
      print('(EOF)', file=sys.stderr)
      return list(k for k, _, _ in _benchmark_registry())
    if not line or line.lower() in ('a', 'all'):
      return list(k for k, _, _ in _benchmark_registry())
    parts = [p.strip() for p in line.replace(';', ',').split(',')]
    try:
      return _parse_choice_tokens(parts, _registry_map().keys())
    except ValueError as e:
      print('Invalid input: {}'.format(e), file=sys.stderr)
      if retries_left <= 1:
        print('Too many invalid attempts; running all benchmarks.', file=sys.stderr)
        return list(k for k, _, _ in _benchmark_registry())
      return _prompt_benchmark_choices(retries_left - 1)

  def _dedupe_preserve_order(keys):
    seen = set()
    out = []
    for k in keys:
      if k not in seen:
        seen.add(k)
        out.append(k)
    return out

  def run_benchmark_suite(keys, use_progress=True):
    print("\n ******** Start BenchMarking ******** \n")
    reg = _registry_map()
    total_w = sum(_benchmark_weight(k) for k in keys)

    def run_one(key, adv_fn):
      desc, fn = reg[key]
      print('>>> {} — {}'.format(key, desc))
      fn(advance=adv_fn)
      print()

    if not use_progress or not sys.stderr.isatty() or total_w <= 0:
      for key in keys:
        run_one(key, _noop_advance)
      return

    console = Console(stderr=True)
    with Progress(
      TextColumn('[bold]{task.description}'),
      BarColumn(),
      TaskProgressColumn(),
      TimeElapsedColumn(),
      TimeRemainingColumn(),
      console=console,
      transient=False,
    ) as progress:
      task_id = progress.add_task('suite', total=total_w)

      for key in keys:

        def make_adv(k):
          def adv(delta):
            progress.update(task_id, advance=delta, description=k)

          return adv

        run_one(key, make_adv(key))

  def main():
    reg = _benchmark_registry()
    valid_keys = [k for k, _, _ in reg]
    parser = argparse.ArgumentParser(
      description='Run PyTimeTag micro-benchmarks. With no arguments on an interactive TTY, you are prompted.',
      formatter_class=argparse.RawDescriptionHelpFormatter,
      epilog=(
        'examples:\n'
        '  python pytimetag/BenchMarker.py --list\n'
        '  python pytimetag/BenchMarker.py packer simulator\n'
        '  python pytimetag/BenchMarker.py 1,3\n'
        '  python pytimetag/BenchMarker.py -a\n'
        '  python pytimetag/BenchMarker.py serdes --no-progress'
      ),
    )
    parser.add_argument(
      'benchmarks',
      nargs='*',
      metavar='NAME',
      help='Benchmark id(s): {}'.format(', '.join(valid_keys)),
    )
    parser.add_argument('-a', '--all', action='store_true', help='Run every benchmark')
    parser.add_argument('-l', '--list', action='store_true', help='List benchmarks and exit')
    parser.add_argument(
      '--no-progress',
      action='store_true',
      help='Disable Rich progress bar (stderr)',
    )
    parser.add_argument(
      '--packer-max-rate-per-ch',
      type=int,
      default=None,
      metavar='N',
      help=(
        'packer only: cap events/lab-second per ch1–4 (2.5M×frac ladder; default 2.5M from env). '
        'Use 0 for uncapped. Overrides PYTIMETAG_BENCH_PACKER_MAX_RATE_PER_CH.'
      ),
    )
    parser.add_argument(
      '--packer-chunk-subdiv',
      type=int,
      default=None,
      metavar='N',
      help=(
        'packer only: sub-intervals per lab second (>=1). Default 2 ≈ half-second chunks; '
        'higher reduces peak RAM. Overrides PYTIMETAG_BENCH_PACKER_CHUNK_SUBDIV.'
      ),
    )
    args = parser.parse_args()

    if args.list:
      _print_benchmark_list()
      return

    if args.all:
      chosen = list(valid_keys)
    elif args.benchmarks:
      expanded = []
      for p in args.benchmarks:
        expanded.extend([x.strip() for x in p.split(',') if x.strip()])
      try:
        chosen = _dedupe_preserve_order(_parse_choice_tokens(expanded, valid_keys))
      except ValueError as e:
        parser.error(str(e))
    elif sys.stdin.isatty():
      chosen = _dedupe_preserve_order(_prompt_benchmark_choices())
    else:
      print(
        'Non-interactive stdin: pass benchmark name(s), e.g.\n'
        '  PYTHONPATH=. python pytimetag/BenchMarker.py packer\n'
        'Use --all to run everything, or --list to see names.',
        file=sys.stderr,
      )
      sys.exit(2)

    bad = [k for k in chosen if k not in valid_keys]
    if bad:
      parser.error('unknown benchmark(s): {}'.format(', '.join(bad)))
    if not chosen:
      parser.error('no benchmarks selected')

    if args.packer_max_rate_per_ch is not None:
      os.environ['PYTIMETAG_BENCH_PACKER_MAX_RATE_PER_CH'] = str(args.packer_max_rate_per_ch)
    if args.packer_chunk_subdiv is not None:
      os.environ['PYTIMETAG_BENCH_PACKER_CHUNK_SUBDIV'] = str(args.packer_chunk_subdiv)

    run_benchmark_suite(chosen, use_progress=not args.no_progress)

  main()


#   private def doBenchMarkingSerDeser(): Unit =
#     List(
#       ("Period List", List(10000, 100000, 1000000, 4000000, 10000000, 100000000), (r: Int) => Map(0 -> List("Period", r)), 1e-12),
#       ("Period List, 16 ps", List(10000, 100000, 1000000, 4000000, 10000000, 100000000), (r: Int) => Map(0 -> List("Period", r)), 16e-12),
#       ("Random List", List(10000, 100000, 1000000, 4000000, 10000000, 100000000), (r: Int) => Map(0 -> List("Random", r)), 1e-12),
#       ("Random List, 16 ps", List(10000, 100000, 1000000, 4000000, 10000000, 100000000), (r: Int) => Map(0 -> List("Random", r)), 16e-12),
#       ("Mixed List", List(10000, 100000, 1000000, 4000000, 10000000, 100000000), (r: Int) => Map(0 -> List("Period", r / 10), 1 -> List("Random", r / 10 * 4), 5 -> List("Random", r / 10 * 5), 10 -> List("Period", 10), 12 -> List("Random", 1)), 1e-12),
#       ("Mixed List, 16 ps", List(10000, 100000, 1000000, 4000000, 10000000, 100000000), (r: Int) => Map(0 -> List("Period", r / 10), 1 -> List("Random", r / 10 * 4), 5 -> List("Random", r / 10 * 5), 10 -> List("Period", 10), 12 -> List("Random", 1)), 16e-12)
#     ).foreach(config => {
#       val rt = ReportTable(s"DataBlock serial/deserial: ${config._1}", List("Event Size", "Data Rate", "Serial Time", "Deserial Time")).setFormatter(0, formatterKMG).setFormatter(1, (dr) => f"${dr.asInstanceOf[Double]}%.2f").setFormatter(2, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms").setFormatter(3, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#       config._2.foreach(r => {
#         val bm = doBenchMarkingSerDeser(config._3(r), config._4)
#         rt.addRow(r, bm._1, bm._2, bm._3)
#       })
#       rt.output()
#     })

#   private def doBenchMarkingSerDeser(dataConfig: Map[Int, List[Any]], resolution: Double = 1e-12): Tuple3[Double, Double, Double] = {
#     val testDataBlock = {
#       val generatedDB = DataBlock.generate(Map("CreationTime" -> 100, "DataTimeBegin" -> 10, "DataTimeEnd" -> 1000000000010L), dataConfig)
#       if (resolution == 1e-12) generatedDB else generatedDB.convertResolution(resolution)
#     }
#     val consumingSerialization = doBenchMarkingOpertion(() => testDataBlock.serialize())
#     val data = testDataBlock.serialize()
#     val infoRate = data.length.toDouble / testDataBlock.getContent.map(_.length).sum
#     val consumingDeserialization = doBenchMarkingOpertion(() => DataBlock.deserialize(data))
#     (infoRate, consumingSerialization, consumingDeserialization)
#   }

#   // private def doBenchMarkingSyncedDataBlock(): Unit = {
#   //   List(false, true).foreach(hasSync => {
#   //     val rt = ReportTable(if (hasSync) s"Delay & Sync" else "Delay", List("Total Event Size", "1 Ch", "2 Ch (1, 1)", "4 Ch (5, 3, 1, 1)"))
#   //       .setFormatter(0, formatterKMG)
#   //       .setFormatter(1, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#   //       .setFormatter(2, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#   //       .setFormatter(3, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#   //     List(10000, 100000, 1000000, 4000000).foreach(r => {
#   //       val bm = doBenchMarkingSyncedDataBlock(
#   //         r,
#   //         List(
#   //           List(1),
#   //           List(1, 1),
#   //           List(5, 3, 1, 1)
#   //         ),
#   //         hasSync
#   //       )
#   //       rt.addRow(r, bm(0), bm(1), bm(2))
#   //     })
#   //     rt.output()
#   //   })
#   // }

#   // private def doBenchMarkingSyncedDataBlock(totalSize: Int, sizes: List[List[Double]], hasSync: Boolean): List[Double] = {
#   //   sizes.map(size => {
#   //     val m = Range(0, size.size + 1).map(s => s -> (if (s == 0) List("Period", 10000) else List("Pulse", 100000000, (size(s - 1) / size.sum * totalSize).toInt, 1000))).toMap
#   //     val dataBlock = DataBlock.generate(Map("CreationTime" -> 100, "DataTimeBegin" -> 0L, "DataTimeEnd" -> 1000000000000L), m)
#   //     doBenchMarkingOpertion(() => { dataBlock.synced(Range(0, 16).toList.map(_ => 100000), if (hasSync) Map("Method" -> "PeriodSignal", "SyncChannel" -> "0", "Period" -> "2e8") else Map()) })
#   //   })
#   // }

#   private def doBenchMarkingMultiHistogramAnalyser(): Unit = {
#     val rt = ReportTable(s"MultiHistogramAnalyser", List("Total Event Size", "1 Ch", "2 Ch (1, 1)", "4 Ch (5, 3, 1, 1)"))
#       .setFormatter(0, formatterKMG)
#       .setFormatter(1, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#       .setFormatter(2, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#       .setFormatter(3, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#     List(10000, 100000, 1000000, 4000000, 10000000).foreach(r => {
#       val bm = doBenchMarkingMultiHistogramAnalyser(
#         r,
#         List(
#           List(1),
#           List(1, 1),
#           List(5, 3, 1, 1)
#         )
#       )
#       rt.addRow(r, bm(0), bm(1), bm(2))
#     })
#     rt.output()
#   }

#   private def doBenchMarkingMultiHistogramAnalyser(totalSize: Int, sizes: List[List[Double]]): List[Double] = {
#     val mha = new MultiHistogramAnalyser(16)
#     mha.turnOn(Map("Sync" -> 0, "Signals" -> List(1), "ViewStart" -> -1000000, "ViewStop" -> 1000000, "BinCount" -> 100, "Divide" -> 100))
#     sizes.map(size => {
#       val m = Range(0, size.size + 1).map(s => s -> (if (s == 0) List("Period", 10000) else List("Pulse", 100000000, (size(s - 1) / size.sum * totalSize).toInt, 1000))).toMap
#       val dataBlock = DataBlock.generate(Map("CreationTime" -> 100, "DataTimeBegin" -> 0L, "DataTimeEnd" -> 1000000000000L), m)
#       doBenchMarkingOpertion(() => mha.dataIncome(dataBlock))
#     })
#   }

#   private def doBenchMarkingExceptionMonitorAnalyser(): Unit = {
#     val rt = ReportTable(s"ExceptionMonitorAnalyser", List("Total Event Size", "1 Ch", "2 Ch (1, 1)", "4 Ch (5, 3, 1, 1)"))
#       .setFormatter(0, formatterKMG)
#       .setFormatter(1, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#       .setFormatter(2, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#       .setFormatter(3, (second) => f"${second.asInstanceOf[Double] * 1000}%.2f ms")
#     List(10000, 100000, 1000000, 4000000).foreach(r => {
#       val bm = doBenchMarkingExceptionMonitorAnalyser(
#         r,
#         List(
#           List(1),
#           List(1, 1),
#           List(5, 3, 1, 1)
#         )
#       )
#       rt.addRow(r, bm(0), bm(1), bm(2))
#     })
#     rt.output()
#   }

#   private def doBenchMarkingExceptionMonitorAnalyser(totalSize: Int, sizes: List[List[Double]]): List[Double] = {
#     val mha = new ExceptionMonitorAnalyser(16)
#     mha.turnOn(Map("SyncChannels" -> List(0, 1, 2, 3, 4, 5, 6)))
#     sizes.map(size => {
#       val m = Range(0, size.size + 1).map(s => s -> (if (s == 0) List("Period", 10000) else List("Pulse", 100000000, (size(s - 1) / size.sum * totalSize).toInt, 1000))).toMap
#       val dataBlock = DataBlock.generate(Map("CreationTime" -> 100, "DataTimeBegin" -> 0L, "DataTimeEnd" -> 1000000000000L), m)
#       doBenchMarkingOpertion(() => mha.dataIncome(dataBlock))
#     })
#   }

#   private def doBenchMarkingOpertion(operation: () => Unit) = {
#     val stop = System.nanoTime() + 1000000000
#     val count = new AtomicInteger(0)
#     while (System.nanoTime() < stop) {
#       operation()
#       count.incrementAndGet()
#     }
#     (1e9 + System.nanoTime() - stop) / 1e9 / count.get
#   }

#   object ReportTable {
#     def apply(title: String, headers: List[String], cellWidth: Int = UNIT_SIZE) = new ReportTable(title, headers, cellWidth = cellWidth)
#   }

#   private def formatterKMG(value: Any): String =
#     value match {
#       case data if data.isInstanceOf[Int] || data.isInstanceOf[Long] || data.isInstanceOf[String] =>
#         data.toString.toLong match {
#           case d if d < 0    => "-"
#           case d if d < 1e2  => d.toString
#           case d if d < 1e3  => f"${d / 1e3}%.3f K"
#           case d if d < 1e4  => f"${d / 1e3}%.2f K"
#           case d if d < 1e5  => f"${d / 1e3}%.1f K"
#           case d if d < 1e6  => f"${d / 1e6}%.3f M"
#           case d if d < 1e7  => f"${d / 1e6}%.2f M"
#           case d if d < 1e8  => f"${d / 1e6}%.1f M"
#           case d if d < 1e9  => f"${d / 1e9}%.3f G"
#           case d if d < 1e10 => f"${d / 1e9}%.2f G"
#           case d if d < 1e11 => f"${d / 1e9}%.1f G"
#           case d if d < 1e12 => f"${d / 1e12}%.3f T"
#           case d if d < 1e13 => f"${d / 1e12}%.2f T"
#           case d if d < 1e14 => f"${d / 1e12}%.1f T"
#           case d             => "--"
#         }
#     }

#   class ReportTable private (val title: String, val headers: List[String], val cellWidth: Int = UNIT_SIZE) {
#     private val rows = ListBuffer[List[Any]]()
#     private val formatters = new mutable.HashMap[Int, Any => String]()

#     def setFormatter(column: Int, formatter: Any => String) = {
#       formatters(column) = formatter
#       this
#     }

#     def addRow(item: Any*) = {
#       if (item.size != headers.size) throw new RuntimeException("Dimension of table of matched.")
#       rows += item.toList
#       this
#     }

#     def addRows(rows: List[Any]*) = rows.map(addRow).head

#     def output(target: PrintStream = System.out): Unit = {
#       val totalWidth = headers.size * (1 + cellWidth) + 1
#       target.println("+" + Range(0, totalWidth - 2).map(_ => "-").mkString("") + "+")
#       target.println("|" + complete(title, totalWidth - 2, alignment = "center") + "|")
#       target.println("+" + Range(0, totalWidth - 2).map(_ => "-").mkString("") + "+")
#       target.println("|" + headers.map(header => complete(header, cellWidth)).mkString("|") + "|")
#       rows.foreach(row =>
#         target.println(
#           "|" + row.zipWithIndex
#             .map(z =>
#               complete(
#                 formatters.get(z._2) match {
#                   case Some(f) => f(z._1)
#                   case None    => z._1.toString
#                 },
#                 cellWidth
#               )
#             )
#             .mkString("|") + "|"
#         )
#       )
#       target.println("+" + Range(0, totalWidth - 2).map(_ => "-").mkString("") + "+")
#     }

#     private def complete(content: String, width: Int, filler: String = " ", alignment: String = "Center"): String = {
#       if (content.length > width) content.slice(0, width - 3) + "..."
#       else {
#         val diff = width - content.length
#         alignment.toLowerCase match {
#           case "left"   => content + Range(0, diff).map(_ => filler).mkString("")
#           case "right"  => Range(0, diff).map(_ => filler).mkString("") + content
#           case "center" => Range(0, diff / 2).map(_ => filler).mkString("") + content + Range(0, diff - diff / 2).map(_ => filler).mkString("")
#         }
#       }
#     }
#   }






### 2023-01-17
# 
# +-----------------------------------------------------------------------------------+
# |                      DataBlock serial/deserial: Period List                       |
# +-----------------------------------------------------------------------------------+
# |     Event Size     |     Data Rate      |    Serial Time     |   Deserial Time    |
# |       10.0 K       |        4.02        |      0.23 ms       |      0.22 ms       |
# |      0.100 M       |        4.00        |      2.34 ms       |      1.84 ms       |
# |       1.00 M       |        3.50        |      20.60 ms      |      20.52 ms      |
# |       4.00 M       |        3.00        |      66.53 ms      |      72.75 ms      |
# |       10.0 M       |        3.00        |     192.85 ms      |     197.78 ms      |
# +-----------------------------------------------------------------------------------+
# +-----------------------------------------------------------------------------------+
# |                   DataBlock serial/deserial: Period List, 16 ps                   |
# +-----------------------------------------------------------------------------------+
# |     Event Size     |     Data Rate      |    Serial Time     |   Deserial Time    |
# |       10.0 K       |        3.52        |      0.19 ms       |      0.20 ms       |
# |      0.100 M       |        3.50        |      1.89 ms       |      1.62 ms       |
# |       1.00 M       |        3.00        |      16.56 ms      |      14.76 ms      |
# |       4.00 M       |        2.50        |      57.45 ms      |      63.33 ms      |
# |       10.0 M       |        2.50        |     161.39 ms      |     173.78 ms      |
# +-----------------------------------------------------------------------------------+
# +-----------------------------------------------------------------------------------+
# |                      DataBlock serial/deserial: Random List                       |
# +-----------------------------------------------------------------------------------+
# |     Event Size     |     Data Rate      |    Serial Time     |   Deserial Time    |
# |       10.0 K       |        4.09        |      0.27 ms       |      0.23 ms       |
# |      0.100 M       |        3.84        |      2.73 ms       |      2.02 ms       |
# |       1.00 M       |        3.46        |      27.84 ms      |      17.93 ms      |
# |       4.00 M       |        3.00        |      67.95 ms      |      72.18 ms      |
# |       10.0 M       |        2.99        |     223.87 ms      |     203.55 ms      |
# +-----------------------------------------------------------------------------------+
# +-----------------------------------------------------------------------------------+
# |                   DataBlock serial/deserial: Random List, 16 ps                   |
# +-----------------------------------------------------------------------------------+
# |     Event Size     |     Data Rate      |    Serial Time     |   Deserial Time    |
# |       10.0 K       |        3.59        |      0.23 ms       |      0.22 ms       |
# |      0.100 M       |        3.34        |      2.47 ms       |      1.87 ms       |
# |       1.00 M       |        2.96        |      25.44 ms      |      15.26 ms      |
# |       4.00 M       |        2.50        |      60.71 ms      |      64.85 ms      |
# |       10.0 M       |        2.49        |     194.03 ms      |     175.51 ms      |
# +-----------------------------------------------------------------------------------+
# +-----------------------------------------------------------------------------------+
# |                       DataBlock serial/deserial: Mixed List                       |
# +-----------------------------------------------------------------------------------+
# |     Event Size     |     Data Rate      |    Serial Time     |   Deserial Time    |
# |       10.0 K       |        4.46        |      0.33 ms       |      0.25 ms       |
# |      0.100 M       |        3.99        |      2.63 ms       |      1.86 ms       |
# |       1.00 M       |        3.55        |      21.01 ms      |      17.55 ms      |
# |       4.00 M       |        3.30        |     100.42 ms      |      80.10 ms      |
# |       10.0 M       |        3.05        |     194.05 ms      |     198.66 ms      |
# +-----------------------------------------------------------------------------------+
# +-----------------------------------------------------------------------------------+
# |                   DataBlock serial/deserial: Mixed List, 16 ps                    |
# +-----------------------------------------------------------------------------------+
# |     Event Size     |     Data Rate      |    Serial Time     |   Deserial Time    |
# |       10.0 K       |        3.96        |      0.30 ms       |      0.23 ms       |
# |      0.100 M       |        3.49        |      2.29 ms       |      1.65 ms       |
# |       1.00 M       |        3.05        |      17.59 ms      |      14.93 ms      |
# |       4.00 M       |        2.80        |      89.44 ms      |      69.67 ms      |
# |       10.0 M       |        2.55        |     168.39 ms      |     173.34 ms      |
# +-----------------------------------------------------------------------------------+
# 
# 
# 
# 
# 
# 
# 
# ###