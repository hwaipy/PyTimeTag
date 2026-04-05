__license__ = "GNU General Public License v3"
__author__ = 'Hwaipy'
__email__ = 'hwaipy@gmail.com'

import time
import numpy as np
from pytimetag.datablock import DataBlock


class Simulator:
  CHANNEL_COUNT = 16

  def __init__(self, channel_count=CHANNEL_COUNT, resolution=1e-12, random_seed=None):
    if channel_count != self.CHANNEL_COUNT:
      raise ValueError('Simulator supports exactly 16 channels.')
    self.channel_count = channel_count
    self.resolution = resolution
    self._rng = np.random.default_rng(random_seed)
    self._channels = [self._default_channel_config() for _ in range(self.channel_count)]

  def _default_channel_config(self):
    return {
        'mode': None,
        'mode_args': tuple(),
        'dead_time': 0,
        'threshold_voltage': float('-inf'),
        'signal_mean': 1.0,
        'signal_std': 0.0,
    }

  def _validate_channel(self, channel):
    if not isinstance(channel, int) or channel < 0 or channel >= self.channel_count:
      raise ValueError('Channel index out of range.')

  def set_channel_mode(self, channel, mode, *args):
    self._validate_channel(channel)
    normalized = str(mode).strip().lower()
    if normalized == 'period':
      if len(args) != 1:
        raise ValueError('Period mode requires: count.')
      count = int(args[0])
      if count < 0:
        raise ValueError('Count should be non-negative.')
      self._channels[channel]['mode'] = 'Period'
      self._channels[channel]['mode_args'] = (count,)
    elif normalized == 'random':
      if len(args) != 1:
        raise ValueError('Random mode requires: count.')
      count = int(args[0])
      if count < 0:
        raise ValueError('Count should be non-negative.')
      self._channels[channel]['mode'] = 'Random'
      self._channels[channel]['mode_args'] = (count,)
    elif normalized == 'pulse':
      if len(args) != 3:
        raise ValueError('Pulse mode requires: pulse_count, event_count, sigma.')
      pulse_count = int(args[0])
      event_count = int(args[1])
      sigma = float(args[2])
      if pulse_count < 0 or event_count < 0 or sigma < 0:
        raise ValueError('Pulse mode arguments should be non-negative.')
      self._channels[channel]['mode'] = 'Pulse'
      self._channels[channel]['mode_args'] = (pulse_count, event_count, sigma)
    else:
      raise ValueError('Unsupported mode.')
    return self

  def set_period_mode(self, channel, count):
    return self.set_channel_mode(channel, 'Period', count)

  def set_random_mode(self, channel, count):
    return self.set_channel_mode(channel, 'Random', count)

  def set_pulse_mode(self, channel, pulse_count, event_count, sigma):
    return self.set_channel_mode(channel, 'Pulse', pulse_count, event_count, sigma)

  def set_channel_dead_time(self, channel, dead_time):
    self._validate_channel(channel)
    dead_time = int(dead_time)
    if dead_time < 0:
      raise ValueError('Dead time should be non-negative.')
    self._channels[channel]['dead_time'] = dead_time
    return self

  def set_channel_threshold(self, channel, threshold_voltage, signal_mean=1.0, signal_std=0.0):
    self._validate_channel(channel)
    signal_std = float(signal_std)
    if signal_std < 0:
      raise ValueError('Signal std should be non-negative.')
    self._channels[channel]['threshold_voltage'] = float(threshold_voltage)
    self._channels[channel]['signal_mean'] = float(signal_mean)
    self._channels[channel]['signal_std'] = signal_std
    return self

  def get_channel_config(self, channel):
    self._validate_channel(channel)
    return dict(self._channels[channel])

  def generate_datablock(self, data_time_begin, data_time_end, creation_time=None, se_der=False):
    data_time_begin = int(data_time_begin)
    data_time_end = int(data_time_end)
    if data_time_end <= data_time_begin:
      raise ValueError('data_time_end should be greater than data_time_begin.')

    channel_config = {}
    for channel, config in enumerate(self._channels):
      if config['mode'] is not None:
        channel_config[channel] = [config['mode'], *config['mode_args']]

    general_config = {
        'DataTimeBegin': data_time_begin,
        'DataTimeEnd': data_time_end,
    }
    raw_data_block = DataBlock.generate(general_config, channel_config, seDer=se_der)

    filtered_content = []
    for channel in range(self.channel_count):
      channel_data = self._apply_threshold(raw_data_block.content[channel], self._channels[channel])
      channel_data = self._apply_dead_time(channel_data, self._channels[channel]['dead_time'])
      filtered_content.append(channel_data)

    if creation_time is None:
      creation_time = int(time.time() * 1000)
    return DataBlock.create(filtered_content, creation_time, data_time_begin, data_time_end, self.resolution)

  def readout(self, data_time_begin, data_time_end, creation_time=None, se_der=False):
    return self.generate_datablock(data_time_begin, data_time_end, creation_time, se_der)

  def _apply_threshold(self, events, config):
    if len(events) == 0:
      return np.array([], dtype='<i8')
    threshold = config['threshold_voltage']
    signal_mean = config['signal_mean']
    signal_std = config['signal_std']
    events = np.array(events, dtype='<i8')
    if signal_std == 0:
      if signal_mean < threshold:
        return np.array([], dtype='<i8')
      return events
    amplitudes = self._rng.normal(signal_mean, signal_std, len(events))
    return events[amplitudes >= threshold]

  def _apply_dead_time(self, events, dead_time):
    if len(events) == 0:
      return np.array([], dtype='<i8')
    if dead_time <= 0:
      return np.array(events, dtype='<i8')
    filtered = [events[0]]
    previous = events[0]
    for event in events[1:]:
      if event - previous >= dead_time:
        filtered.append(event)
        previous = event
    return np.array(filtered, dtype='<i8')
