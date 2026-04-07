安装
====

环境要求
--------

- Python 3.9+
- 核心依赖：NumPy、msgpack、numba、rich

从 PyPI 安装
------------

.. code-block:: bash

   python -m pip install -U pytimetag

安装 Swabian 可选支持
---------------------

.. code-block:: bash

   python -m pip install -U "pytimetag[swabian]"

从源码安装
----------

.. code-block:: bash

   git clone https://github.com/hwaipy/PyTimeTag.git
   cd PyTimeTag
   python -m pip install -e .

如需硬件支持，再安装：

.. code-block:: bash

   python -m pip install -e ".[swabian]"
