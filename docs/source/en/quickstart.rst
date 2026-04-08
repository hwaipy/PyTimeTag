Quickstart
==========

Requirements
------------

- **Python**: 3.9+ (see ``setup.py`` / ``python_requires``).
- **Core deps**: NumPy, msgpack, numba, rich, duckdb.

Install
-------

From PyPI (library + CLI; no Swabian extras):

.. code-block:: bash

   python -m pip install -U pytimetag

With Swabian Time Tagger support (also installs ``Swabian-TimeTagger`` from PyPI; vendor runtime still required):

.. code-block:: bash

   python -m pip install -U "pytimetag[swabian]"

Editable install from a clone:

.. code-block:: bash

   git clone https://github.com/hwaipy/PyTimeTag.git
   cd PyTimeTag
   python -m pip install -e .
   python -m pip install -e ".[swabian]"

The console entry point is ``pytimetag`` (or ``python -m pytimetag``).

First commands
--------------

Show all options:

.. code-block:: bash

   pytimetag --help

If **no arguments at all** follow the program name, the CLI prints help and a short Chinese hint, and **does not** start acquisition. With any argument (e.g. ``--save``), the app runs; ``--source`` defaults to ``simulator`` when omitted.

Run the simulator (live table, stop with Ctrl+C):

.. code-block:: bash

   pytimetag --source simulator

Save DataBlock files
--------------------

.. code-block:: bash

   pytimetag --save --output-dir ./my_data

``--datablock-dir`` is an alias for ``--output-dir``. Files go under ``my_data/YYYY-MM-DD/HH/*.datablock``.

Online processing and DuckDB (enabled by default)
-------------------------------------------------

When online processing is enabled, analyser results are written to DuckDB (default ``./store_test/pytimetag.duckdb``). Override:

.. code-block:: bash

   pytimetag --save --output-dir ./blocks --storage-db ./analytics/run.duckdb

Disable online processing:

.. code-block:: bash

   pytimetag --no-post-process

Common split examples
---------------------

Time window (e.g. 2 s blocks):

.. code-block:: bash

   pytimetag --split-s 2.0 --resolution 1e-12

Split on channel events (e.g. channel 3):

.. code-block:: bash

   pytimetag --split-mode channel --split-channel 3

Next steps
----------

See :doc:`cli` for the full CLI reference, :doc:`offline_processing` for replay analysis, and :doc:`datablock_format` for the binary layout and size notes.
