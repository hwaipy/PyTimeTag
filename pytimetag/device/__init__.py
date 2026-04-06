"""Virtual TimeTag hardware simulation."""

from pytimetag.device.Simulator import (
    DEFAULT_CHANNEL_COUNT,
    MAX_PACKED_CHANNELS,
    ChannelSettings,
    TimeTagSimulator,
    pack_timetag,
    unpack_timetag,
)
from pytimetag.device.datablock_packer import (
    DataBlockPackerPath,
    DataBlockStreamPacker,
    SplitByChannelEvent,
    SplitByTimeWindow,
    feed_callback_for_simulator,
    pack_timestamps_channels_to_content,
)

__all__ = [
    'DEFAULT_CHANNEL_COUNT',
    'MAX_PACKED_CHANNELS',
    'ChannelSettings',
    'TimeTagSimulator',
    'DataBlockPackerPath',
    'DataBlockStreamPacker',
    'SplitByChannelEvent',
    'SplitByTimeWindow',
    'feed_callback_for_simulator',
    'pack_timestamps_channels_to_content',
]
