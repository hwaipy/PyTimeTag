"""Virtual TimeTag hardware simulation."""

from pytimetag.device.Simulator import (
    DEFAULT_CHANNEL_COUNT,
    MAX_PACKED_CHANNELS,
    ChannelSettings,
    TimeTagSimulator,
    pack_timetag,
    unpack_timetag,
)

__all__ = [
    'DEFAULT_CHANNEL_COUNT',
    'MAX_PACKED_CHANNELS',
    'ChannelSettings',
    'TimeTagSimulator',
]
