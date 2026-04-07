Installation
============

Requirements
------------

- Python 3.9+
- Core dependencies: NumPy, msgpack, numba, rich

Install from PyPI
-----------------

.. code-block:: bash

   python -m pip install -U pytimetag

Install with Swabian support
----------------------------

.. code-block:: bash

   python -m pip install -U "pytimetag[swabian]"

Install from source
-------------------

.. code-block:: bash

   git clone https://github.com/hwaipy/PyTimeTag.git
   cd PyTimeTag
   python -m pip install -e .

For hardware usage, install:

.. code-block:: bash

   python -m pip install -e ".[swabian]"
