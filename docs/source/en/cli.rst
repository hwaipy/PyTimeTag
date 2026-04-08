Command-Line Interface (detailed)
=================================

Entry point and help
--------------------

After installation, use ``pytimetag`` (equivalent to ``python -m pytimetag``).

.. code-block:: bash

   pytimetag --help

**No-argument behavior**: if there is nothing after the program name, the CLI prints help plus a short Chinese hint and **does not** start acquisition. ``pytimetag -h`` / ``--help`` count as “with arguments” and likewise do not acquire.

``--source``
------------

.. list-table::
   :widths: 20 80
   :header-rows: 1

   * - Value
     - Meaning
   * - ``simulator``
     - Built-in simulator; default when another argument is present and ``--source`` is omitted.
   * - ``swabian``
     - Swabian Instruments Time Tagger; requires ``pip install "pytimetag[swabian]"`` and vendor runtime; plugin loads only when selected.

Use ``--serial`` for multi-device setups when the plugin requires it.

DataBlock files and splitting
-------------------------------

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - Flag
     - Description
   * - ``--save``
     - Serialize each ``DataBlock`` to disk.
   * - ``--output-dir`` / ``--datablock-dir``
     - Root directory for files, default ``./store_test``. Files are ``root/YYYY-MM-DD/HH/timestamp.datablock``.
   * - ``--split-s``
     - For ``--split-mode time``, window length in seconds (default ``1.0``).
   * - ``--split-mode``
     - ``time`` (window) or ``channel`` (trigger on channel events).
   * - ``--split-channel``
     - Channel index for ``split-mode=channel`` (0–15, default ``0``).
   * - ``--channel-count``
     - Active channel count (default ``8``; packing still uses a 16-channel layout).
   * - ``--resolution``
     - Seconds per tick (default ``1e-12``).

Online processing and DuckDB
----------------------------

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - Flag
     - Description
   * - ``--post-process`` / ``--no-post-process``
     - Enable/disable online processing (built-in analysers + DB persistence; default: **on**).
   * - ``--storage-db``
     - DuckDB file path, default ``./store_test/pytimetag.duckdb``. Connected only when post-processing is enabled; parent directories are created as needed.

With ``--no-post-process``, online processing is disabled and DuckDB is not opened.

Hardware options (plugin-specific)
----------------------------------

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - Flag
     - Description
   * - ``--serial``
     - Device serial; often required when multiple units are present.
   * - ``--hardware-buffer-size``
     - Stream buffer event cap (plugin-defined; Swabian uses ``n_max_events``, default ``1000000``).
   * - ``--hardware-poll-s``
     - Poll interval in seconds (Swabian default ``0.002``).
   * - ``--trigger-level``
     - Repeatable. ``INDEX:V`` per-channel trigger level.
   * - ``--deadtime-s``
     - Repeatable. ``INDEX:SECONDS`` per-channel dead time.

Simulator-only options
----------------------

.. list-table::
   :widths: 28 72
   :header-rows: 1

   * - Flag
     - Description
   * - ``--seed``
     - RNG seed (default ``42``).
   * - ``--update-lo-s`` / ``--update-hi-s``
     - Random range for batch update interval (seconds).
   * - ``--channel``
     - Repeatable. ``INDEX:key=value,...`` for that channel (e.g. ``mode=Random,random_count=50000``).

Examples
--------

Help only:

.. code-block:: bash

   pytimetag

Simulator, no files:

.. code-block:: bash

   pytimetag --source simulator

Save blocks and custom DuckDB path:

.. code-block:: bash

   pytimetag --save --datablock-dir ./my_data --storage-db ./my_data/meta.duckdb

2 s time windows:

.. code-block:: bash

   pytimetag --split-s 2.0

Split on channel 3 events:

.. code-block:: bash

   pytimetag --split-mode channel --split-channel 3

Swabian, single device:

.. code-block:: bash

   pytimetag --source swabian --save --output-dir ./runs

Multiple devices:

.. code-block:: bash

   pytimetag --source swabian --serial YOUR_SERIAL

Simulator channel override:

.. code-block:: bash

   pytimetag --channel "1:mode=Random,random_count=100000" --seed 123

Hardware trigger and dead time:

.. code-block:: bash

   pytimetag --source swabian --trigger-level "0:-0.2" --deadtime-s "1:5e-08"

Troubleshooting
---------------

.. list-table::
   :widths: 35 65
   :header-rows: 1

   * - Symptom
     - Hint
   * - Nothing runs with bare ``pytimetag``
     - Expected; pass an argument such as ``--source simulator`` or ``--save``.
   * - Unknown / unregistered hardware source
     - Install ``pytimetag[swabian]`` and check ``--source`` spelling.
   * - ``--serial`` required
     - Use the serial shown by the vendor tool when multiple devices exist.

Binary layout and size notes: :doc:`datablock_format`. Offline replay: :doc:`offline_processing`. Extension points: :doc:`extending`.
