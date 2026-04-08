Extending PyTimeTag
===================

Overview
--------

Three common extension points:

#. **CLI hardware sources**: map a name to a plugin module in ``pytimetag.device.source_registry``, loaded by ``device_type_manager.create_device_for_cli_source``.
#. **Device types**: register a :class:`~pytimetag.device.base.TimeTagDeviceFactory` subclass on ``device_type_manager`` for discovery and connection.
#. **Analysers**: subclass :class:`~pytimetag.Analyser.Analyser`, implement ``analysis``, call ``dataIncome`` from your own pipeline or from the CLI.

CLI source plugins
------------------

The table ``CLI_SOURCE_PLUGINS`` in ``pytimetag/device/source_registry.py`` maps ``--source`` names to **importable module paths** (imported only when that source is selected).

The plugin module must define::

   def create_device(manager, args, console, live, on_words) -> Optional[TimeTagDevice]

- ``manager`` is the global ``device_type_manager`` used to ``connect(device_type, serial_number, dataUpdate=..., **kwargs)``.
- ``on_words`` forwards packed timestamp streams to the upper layer (same contract as the simulator).
- Return ``None`` to abort after printing help (e.g. NumPy ABI mismatch).

See ``pytimetag/device/sources/swabian.py`` for a full example.

Device factories
----------------

:class:`~pytimetag.device.manager.DeviceTypeManager` stores ``device_type -> Factory``. Factories should set ``device_type`` and implement ``discover()`` / ``connect()`` (see ``pytimetag.device.base``).

Typical steps for a new vendor:

#. Implement ``TimeTagDevice`` / ``TimeTagDeviceFactory``.
#. ``device_type_manager.register(MyFactory)`` on import (same pattern as Swabian).
#. For CLI support: add an entry to ``CLI_SOURCE_PLUGINS`` and call ``connect`` for your ``device_type`` inside ``create_device``.

Analysers
---------

``Analyser`` uses ``turnOn`` / ``turnOff``; ``dataIncome`` calls ``analysis(dataBlock)`` and attaches ``Configuration`` to the returned dict.

The CLI (with ``--post-process``, i.e. online processing) persists each successful ``dataIncome`` return value to DuckDB under a collection named like the analyser class. Custom apps can instantiate subclasses directly or extend the list in ``pytimetag/__main__.py`` (upstream coordination required).

Tests
-----

Add tests under ``tests/`` and run::

   python -m unittest discover -s tests -p 'test*.py'
