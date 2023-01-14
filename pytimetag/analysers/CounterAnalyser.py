__license__ = "GNU General Public License v3"
__author__ = 'Hwaipy'
__email__ = 'hwaipy@gmail.com'

from pytimetag.Analyser import Analyser


class CounterAnalyser(Analyser):
  def analysis(self, dataBlock):
    result = {}
    for ch in range(len(dataBlock.getContent())):
      result[str(ch)] = len(dataBlock.getContent(ch))
    return result
