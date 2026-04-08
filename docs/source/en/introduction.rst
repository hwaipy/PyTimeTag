Introduction
============

PyTimeTag targets **time-tagging** experiments and tooling: record arrival times and channel indices for photons (or other events). The library and CLI cover the common path **ingest → split into :class:`~pytimetag.datablock.DataBlock` → serialize/persist → online processing and monitoring**, reducing one-off scripts and glue code.

**Capabilities**

- **Sources**: built-in **simulator** (no hardware); **Swabian Instruments Time Tagger** via optional extras (loaded on demand).
- **Splitting**: time windows or per-channel triggers to slice streams into ``DataBlock`` instances.
- **Storage**: serialize blocks to ``.datablock`` files; with online processing enabled, the CLI can persist analyser output to **DuckDB** (configurable path).
- **Extension**: register hardware via **device factories** and **CLI plugin modules**; analysers extend :class:`~pytimetag.Analyser.Analyser`.

**Repository and license**

- Source: <https://github.com/hwaipy/PyTimeTag>
- PyPI: <https://pypi.org/project/pytimetag/>
- License: GPL-3.0

Other sections: **Quickstart** → **CLI reference** → **Offline processing** → **Extending** → **DataBlock storage format**; see :doc:`api` for API autodocs.
