Quickstart
==========

Show CLI help
-------------

.. code-block:: bash

   pytimetag --help

Run simulator source
--------------------

.. code-block:: bash

   pytimetag --source simulator

Save DataBlock files
--------------------

.. code-block:: bash

   pytimetag --save --output-dir ./my_data

Split by time window
--------------------

.. code-block:: bash

   pytimetag --split-s 2.0 --resolution 1e-12

Split by channel event
----------------------

.. code-block:: bash

   pytimetag --split-mode channel --split-channel 3
