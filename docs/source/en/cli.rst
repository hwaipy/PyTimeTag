Command-Line Interface
======================

Entry point
-----------

The package provides a console entry point named ``pytimetag``.

.. code-block:: bash

   pytimetag --help

Main arguments
--------------

- ``--source``: source backend (for example ``simulator`` or ``swabian``)
- ``--save`` and ``--output-dir``: store serialized DataBlocks
- ``--split-mode``, ``--split-s``, ``--split-channel``: split strategy
- ``--channel-count`` and ``--resolution``: source settings
- ``--serial``: hardware device selection for multi-device setups

Simulator options
-----------------

- ``--seed``
- ``--update-lo-s``
- ``--update-hi-s``
- ``--channel INDEX:key=value,...`` (repeatable)

Hardware-related options
------------------------

- ``--hardware-buffer-size``
- ``--hardware-poll-s``
- ``--trigger-level INDEX:V`` (repeatable)
- ``--deadtime-s INDEX:SECONDS`` (repeatable)
