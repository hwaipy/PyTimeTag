import unittest
import numpy as np

from device.Simulator import Simulator


class SimulatorTest(unittest.TestCase):
  def test_channel_count_is_16(self):
    simulator = Simulator()
    self.assertEqual(simulator.channel_count, 16)

  def test_generate_with_mixed_modes(self):
    simulator = Simulator(random_seed=1234)
    simulator.set_period_mode(0, 10)
    simulator.set_random_mode(1, 20)
    simulator.set_pulse_mode(2, 10, 15, 5.0)
    data_block = simulator.generate_datablock(0, 1000, creation_time=7)

    self.assertEqual(data_block.creationTime, 7)
    self.assertEqual(data_block.dataTimeBegin, 0)
    self.assertEqual(data_block.dataTimeEnd, 1000)
    self.assertEqual(len(data_block.content), 16)
    self.assertEqual(len(data_block.content[0]), 10)
    self.assertEqual(len(data_block.content[1]), 20)
    self.assertEqual(len(data_block.content[2]), 15)
    for channel in range(3, 16):
      self.assertEqual(len(data_block.content[channel]), 0)

  def test_dead_time_filters_nearby_events(self):
    simulator = Simulator()
    simulator.set_period_mode(0, 10)  # events at 0,10,...,90 in this window
    simulator.set_channel_dead_time(0, 30)
    data_block = simulator.generate_datablock(0, 100, creation_time=1)

    self.assertListEqual(data_block.content[0].tolist(), [0, 30, 60, 90])

  def test_threshold_can_remove_all_events(self):
    simulator = Simulator()
    simulator.set_period_mode(0, 10)
    simulator.set_channel_threshold(0, threshold_voltage=2.0, signal_mean=1.0, signal_std=0.0)
    data_block = simulator.generate_datablock(0, 100, creation_time=1)

    self.assertEqual(len(data_block.content[0]), 0)

  def test_threshold_keeps_all_with_higher_signal(self):
    simulator = Simulator()
    simulator.set_period_mode(0, 10)
    simulator.set_channel_threshold(0, threshold_voltage=0.5, signal_mean=1.0, signal_std=0.0)
    data_block = simulator.generate_datablock(0, 100, creation_time=1)

    self.assertEqual(len(data_block.content[0]), 10)

  def test_invalid_config_raises(self):
    simulator = Simulator()
    with self.assertRaises(ValueError):
      simulator.set_period_mode(16, 10)
    with self.assertRaises(ValueError):
      simulator.set_channel_dead_time(0, -1)
    with self.assertRaises(ValueError):
      simulator.set_channel_threshold(0, 0.1, signal_mean=1.0, signal_std=-1.0)
    with self.assertRaises(ValueError):
      simulator.generate_datablock(100, 100)
    with self.assertRaises(ValueError):
      simulator.set_channel_mode(0, 'UnsupportedMode', 1)

  def test_readout_alias(self):
    simulator = Simulator()
    simulator.set_random_mode(3, 5)
    data_block = simulator.readout(0, 1000, creation_time=99)
    self.assertEqual(data_block.creationTime, 99)
    self.assertEqual(len(data_block.content[3]), 5)

  def test_se_der_round_trip(self):
    simulator = Simulator()
    simulator.set_random_mode(0, 8)
    simulator.set_channel_dead_time(0, 20)
    simulator.set_channel_threshold(0, 0.0, signal_mean=1.0, signal_std=0.5)
    data_block = simulator.generate_datablock(0, 1000, creation_time=2, se_der=True)

    self.assertEqual(data_block.creationTime, 2)
    self.assertEqual(data_block.dataTimeBegin, 0)
    self.assertEqual(data_block.dataTimeEnd, 1000)
    self.assertIsInstance(data_block.content[0], np.ndarray)
    self.assertTrue(np.all(np.diff(data_block.content[0]) >= 0))


if __name__ == '__main__':
  unittest.main()
