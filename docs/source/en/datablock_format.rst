DataBlock storage format
========================

This page describes the **binary blob** produced by ``DataBlock.serialize()`` (the ``*.datablock`` files written with ``--save`` in the CLI). The protocol id is ``DataBlock_V1``.

Outer container: MessagePack
----------------------------

Serialization uses **msgpack** (``packb(..., use_bin_type=True)``). The top-level value is a **map** with the following keys:

.. list-table::
   :widths: 30 70
   :header-rows: 1

   * - Key
     - Meaning
   * - ``Format``
     - Literal ``DataBlock_V1`` (``pytimetag.datablock.DataBlock.PROTOCOL_V1``).
   * - ``CreationTime``
     - Block creation time in **milliseconds** (numeric; same convention as the code).
   * - ``Resolution``
     - **Seconds per tick** (float; default ``1e-12``, i.e. 1 ps per tick).
   * - ``DataTimeBegin`` / ``DataTimeEnd``
     - Inclusive tick range for the block (multiply by ``Resolution`` for seconds).
   * - ``Sizes``
     - Per-channel event counts (matches numpy channel lengths).
   * - ``Content``
     - Per-channel compressed payloads (see below).
   * - ``ContentSerializedSizeSugggestion``
     - Per-channel segment length hints (historic typo preserved); aligns with ``Content`` segments.

Per-channel encoding (protocol V1)
----------------------------------

Each channel is a sorted ``int64`` tick array. The encoder **splits** long channels into segments (``DataBlock.FINENESS = 100000`` events per segment at most), and each segment is encoded independently. The rules below are the concrete on-wire definition implemented by ``serializeSectionJIT`` / ``deserializeSectionJIT``.

Segment byte layout
~~~~~~~~~~~~~~~~~~~

For one non-empty segment ``t[0..m-1]`` (``m > 0``):

#. **Header (8 bytes)**: ``t[0]`` as big-endian signed int64.
#. **Body (nibble stream)**: for each ``i = 1..m-1``, encode ``delta_i = t[i] - t[i-1]`` and append.

If ``m = 0``, the segment payload is empty. For an empty channel, ``Content`` stores ``[]`` for that channel.

Nibble token for one delta
~~~~~~~~~~~~~~~~~~~~~~~~~~

Each ``delta`` is encoded as a nibble token:
``[L][N0][N1]...[N(L-1)]``.

- ``N0..N(L-1)`` are the two's-complement sign-extended truncated representation of ``delta`` (most-significant nibble first), with ``1 <= L <= 15``.
- ``L`` itself is the number of following value nibbles.
- Decoder reads ``L``, then reads exactly ``L`` nibbles to reconstruct the signed delta and accumulate to the previous timestamp.

Implementation notes and edge conditions
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Nibble packing order is high 4 bits then low 4 bits per byte.
- If Body has an odd number of nibbles, the final low nibble is zero padding; decoder naturally ignores it.
- Encoder range guard is ``|delta| <= 1e16`` (per source). If exceeded, that segment returns an empty byte buffer (error-path behavior).
- Deserialization reads Header first, then token-by-token restores the original ``int64`` sequence.

Relation to ``ContentSerializedSizeSugggestion``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This field stores per-channel per-segment **event counts** (not compressed byte lengths), aligned with the segment list in ``Content``.

File size is dominated by the **compressed byte length** of all segments; msgpack adds only a small fixed overhead for maps and ``bytes`` blobs.

Size estimation
---------------

Let **total events** be :math:`N = \sum_c N_c` across channels.

**Uncompressed lower bound (timestamps only)**  
Storing every event as int64 needs about :math:`8N` bytes for raw times. The actual blob also includes msgpack framing and ``Sizes``, usually **a few extra KB**.

**Compressed behaviour**

- **Small, smooth deltas** (e.g. periodic data with jitter) often use **far fewer than 8 bytes/event** on average.
- **Large or near-random deltas** inflate the nibble stream and can approach or exceed 8 bytes/event (extreme cases may hit the encoder failure path).

**Order-of-magnitude rule of thumb**  
Approximate serialized size as about :math:`N \times s` bytes, where :math:`s` is an average **encoded bytes per event** learned from your signal; try :math:`s \sim 1\text{--}4` for tidy data and raise it for noisy streams.

If the total event rate is :math:`R` events/s and the block spans :math:`T` seconds, then :math:`N \sim R \times T` and on-disk size scales roughly with :math:`R \times T`.

**CLI layout**  

With ``--save``, filenames follow block creation time under ``<output-dir>/YYYY-MM-DD/HH/`` with extension ``.datablock``; each file is **one** msgpack blob as above.

Relation to DuckDB
------------------

``--storage-db`` stores **analyser outputs** (JSON in DuckDB tables), **not** the ``.datablock`` layout; ``.datablock`` files are defined solely by ``DataBlock.serialize()``.
