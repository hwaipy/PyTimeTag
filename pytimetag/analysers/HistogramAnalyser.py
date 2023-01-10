__license__ = "GNU General Public License v3"
__author__ = 'Hwaipy'
__email__ = 'hwaipy@gmail.com'

from pytimetag.Analyser import Analyser, Validator
import numba
import numpy as np

class HistogramAnalyser(Analyser):
    def __init__(self, channelCount):
        super().__init__()
        self.channelCount = channelCount
        self.setConfiguration("Sync", 0, Validator.int(0, channelCount - 1))
        self.setConfiguration("Signals", [1], Validator.intList(0, channelCount - 1))
        self.setConfiguration("ViewStart", -100000, Validator.float())
        self.setConfiguration("ViewStop", 100000, Validator.float())
        self.setConfiguration("BinCount", 1000, Validator.int(1, 10000))
        self.setConfiguration("Divide", 1, Validator.int(min=1))

    def analysis(self, dataBlock):
        if True:
            return self.analysisJIT(dataBlock)
        syncChannel = self.getConfiguration("Sync")
        signalChannels = self.getConfiguration("Signals")
        viewStart = self.getConfiguration("ViewStart")
        viewStop = self.getConfiguration("ViewStop")
        binCount = self.getConfiguration("BinCount")
        divide = self.getConfiguration("Divide")
        tList = dataBlock.content[syncChannel]
        viewFrom = viewStart
        viewTo = viewStop
        histograms = []
        for signalChannel in signalChannels:
            deltas = []
            sList = dataBlock.content[signalChannel]
            if len(tList) > 0 and len(sList) > 0:
                preStartT = 0
                lengthT = len(tList)
                sp = 0
                while sp < len(sList):
                    s = sList[sp]
                    cont = True
                    while (preStartT < lengthT and cont):
                        t = tList[preStartT]
                        delta = s - t
                        if (delta > viewTo):
                            preStartT += 1
                        else:
                            cont = False
                    tIndex = preStartT
                    cont = True
                    while (tIndex < lengthT and cont):
                        t = tList[tIndex]
                        delta = s - t
                        if (delta > viewFrom):
                            deltas.append(delta)
                            tIndex += 1
                        else:
                            cont = False
                    sp += 1
            histograms.append(Histogram(deltas, binCount, viewFrom, viewTo, divide).yData)
        return {'Histograms': histograms}

    def dataIncomeJIT(self, dataBlock):
        if self.on:
            result = self.analysisJIT(dataBlock)
            result['Configuration'] = self.getConfigurations()
            return result
        else:
            return None

    def analysisJIT(self, dataBlock):
        syncChannel = self.getConfiguration("Sync")
        signalChannels = self.getConfiguration("Signals")
        viewStart = self.getConfiguration("ViewStart")
        viewStop = self.getConfiguration("ViewStop")
        binCount = self.getConfiguration("BinCount")
        divide = self.getConfiguration("Divide")
        tList = dataBlock.content[syncChannel]
        viewFrom = viewStart
        viewTo = viewStop
        histograms = []
        for signalChannel in signalChannels:
            sList = dataBlock.content[signalChannel]
            histograms.append(analysisJIT(np.array(tList), np.array(sList), viewFrom, viewTo, binCount, divide))
        return {'Histograms': histograms}

@numba.njit
def analysisJIT(tList, sList, viewFrom, viewTo, binCount, divide):
    deltas = [0]
    if len(tList) > 0 and len(sList) > 0:
        preStartT = 0
        lengthT = len(tList)
        sp = 0
        while sp < len(sList):
            s = sList[sp]
            cont = True
            while (preStartT < lengthT and cont):
                t = tList[preStartT]
                delta = s - t
                if (delta > viewTo):
                    preStartT += 1
                else:
                    cont = False
            tIndex = preStartT
            cont = True
            while (tIndex < lengthT and cont):
                t = tList[tIndex]
                delta = s - t
                if (delta > viewFrom):
                    deltas.append(delta)
                    tIndex += 1
                else:
                    cont = False
            sp += 1
    min = float(viewFrom)
    max = float(viewTo)
    binSize = (max - min) / binCount / divide
    xData = [(i * binSize + min) + binSize / 2 for i in range(binCount)]
    yData = [0] * binCount
    dp = 0
    while dp < len(deltas):
        delta = deltas[dp]
        deltaDouble = float(delta)
        if deltaDouble < min:
            pass
            # /* this data is smaller than min */
        elif deltaDouble == max:
            #  // the value falls exactly on the max value
            self.yData[binCount - 1] += 1
        elif deltaDouble > max:
            pass
            # /* this data point is bigger than max */
        else:
            bin = int((deltaDouble - min) / binSize) % binCount
            yData[bin] += 1
        dp += 1
    return yData

class Histogram:
    def __init__(self, deltas, binCount, viewFrom, viewTo, divide):
        self.deltas = deltas
        self.binCount = binCount
        self.min = float(viewFrom)
        self.max = float(viewTo)
        self.divide = divide
        self.binSize = (self.max - self.min) / self.binCount / self.divide
        self.xData = [(i * self.binSize + self.min) + self.binSize / 2 for i in range(self.binCount)]
        self.yData = [0] * self.binCount
        self.__initData()

    def __initData(self):
        dp = 0
        while dp < len(self.deltas):
            delta = self.deltas[dp]
            deltaDouble = float(delta)
            if deltaDouble < self.min:
                pass
                # /* this data is smaller than min */
            elif deltaDouble == self.max:
                #  // the value falls exactly on the max value
                self.yData[self.binCount - 1] += 1
            elif deltaDouble > self.max:
                pass
                # /* this data point is bigger than max */
            else:
                bin = int((deltaDouble - self.min) / self.binSize) % self.binCount
                self.yData[bin] += 1
            dp += 1


if __name__ == '__main__':
    from pytimetag.datablock import DataBlock
    from pytimetag.analysers.HistogramAnalyser import HistogramAnalyser
    import time
    dataBlock = DataBlock.generate(
        {'CreationTime': 100, 'DataTimeBegin': 10, 'DataTimeEnd': 1000000000010},
        {0: ['Period', 10000], 1: ["Pulse", 100000000, 4000000, 1000]},
        seDer=True
    )
    mha = HistogramAnalyser(16)
    mha.turnOn({'Sync': 0, 'Signals': [1]})
    t1 = time.time()
    r1 = mha.dataIncome(dataBlock)
    t2 = time.time()
    r2 = mha.dataIncomeJIT(dataBlock)
    t3 = time.time()
    r2 = mha.dataIncomeJIT(dataBlock)
    t4 = time.time()
    print(t2 - t1, t4 - t3)
    # print(r1 == r2)
    # print(r1['Configuration'] == r2['Configuration'])

    # l1 = r1['Histograms'][0]
    # l2 = r1['Histograms'][0]
    # assert(len(l1) == len(l2))
    # for i in range(len(l1)):
    #     if l1[i] != l2[i]:
    #         print(i, l1[i], l2[i])
    #         break