__author__ = 'Hwaipy'

import unittest
from pytimetag import DataBlock, DataBlockSerializer
import numpy as np
from random import Random
from pytimetag.native.native import convertNativeList

class DataBlockTest(unittest.TestCase):
    rnd = Random()

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        pass

    def testDataBlockGeneration(self):
        testDataBlock = DataBlock.generate(
            {'CreationTime': 100, 'DataTimeBegin': 10, 'DataTimeEnd': 1000000000010}, 
            {0: ['Period', 10000], 1: ['Random', 230000], 5: ['Random', 105888], 10: ['Period', 10]}
        )
        self.assertTrue(testDataBlock.getContent() is not None)
        self.assertFalse(testDataBlock.isReleased())
        self.assertEqual(len(testDataBlock.getContent(0)), 10000)
        self.assertEqual(len(testDataBlock.getContent(1)), 230000)
        self.assertEqual(len(testDataBlock.getContent(5)), 105888)
        self.assertEqual(len(testDataBlock.getContent(10)), 10)
        self.assertEqual(testDataBlock.getContent(10)[5] - testDataBlock.getContent(10)[4], 100000000000)
        testDataBlock.release()
        self.assertIsNone(testDataBlock.getContent())
        self.assertTrue(testDataBlock.isReleased())
        self.assertEqual(testDataBlock.sizes[0], 10000)
        self.assertEqual(testDataBlock.sizes[1], 230000)
        self.assertEqual(testDataBlock.sizes[5], 105888)
        self.assertEqual(testDataBlock.sizes[10], 10)
        self.assertEqual(testDataBlock.sizes[11], 0)

    def testDataBlockSerializerProtocolDataBlockV1(self):
        self.assertEqual(DataBlockSerializer.instance(DataBlock.PROTOCOL_V1).serialize([]), b'')
        self.assertEqual(DataBlockSerializer.instance(DataBlock.PROTOCOL_V1).serialize(convertNativeList([823784993])), bytes(bytearray([0, 0, 0, 0, 49, 25, 246, 33])))
        self.assertEqual(DataBlockSerializer.instance(DataBlock.PROTOCOL_V1).serialize(convertNativeList([823784993, 823784993 + 200, 823784993 + 2000, 823784993 + 2000, 823784993 + 2201])), bytes(bytearray([0, 0, 0, 0, 49, 25, 246, 33, 48, 200, 55, 8, 16, 48, 201])))
        self.assertEqual(DataBlockSerializer.instance(DataBlock.PROTOCOL_V1).serialize(convertNativeList([0, -1, -8, -17, -145, -274])), bytes(bytearray([0, 0, 0, 0, 0, 0, 0, 0, 31, 25, 47, 114, 128, 63, 127])))
        list1 = list(np.array([[1000 + i, 0] for i in range(2)]).flatten())
        binary1 = DataBlockSerializer.instance(DataBlock.PROTOCOL_V1).serialize(convertNativeList(list1))
        desList1 = DataBlockSerializer.instance(DataBlock.PROTOCOL_V1).deserialize(binary1)
        self.assertEqual(list1, [i for i in desList1])
        list2 = [int((DataBlockTest.rnd.random() - 0.5) * 1e14) for i in range(10)]
        binary2 = DataBlockSerializer.instance(DataBlock.PROTOCOL_V1).serialize(convertNativeList(list2))
        desList2 = DataBlockSerializer.instance(DataBlock.PROTOCOL_V1).deserialize(binary2)
        self.assertEqual(list2, [i for i in desList2])

    def testDataBlockSerializationAndDeserialization(self):
        testDataBlock = DataBlock.generate(
            {'CreationTime': 100, 'DataTimeBegin': 10, 'DataTimeEnd': 1000000000010}, 
            {0: ['Period', 10000], 1: ['Random', 230000], 5: ['Random', 105888], 10: ['Period', 10], 12: ['Random', 1]}
        )
        binary = testDataBlock.serialize()
        recoveredDataBlock = DataBlock.deserialize(binary)
        recoveredDataBlock.pythonalize()
        self.assertDataBlockEqual(testDataBlock, recoveredDataBlock)

    def testDataBlockSerializationAndDeserializationWithRandomizedData(self):
        testDataBlock = DataBlock.create([[DataBlockTest.rnd.randint(0, 1000000000000) for i in range(10000)]], 100001, 0, 1000000000000)
        binary = testDataBlock.serialize()
        recoveredDataBlock = DataBlock.deserialize(binary)
        recoveredDataBlock.pythonalize()
        self.assertDataBlockEqual(testDataBlock, recoveredDataBlock)

    def testDataBlockSerializationAndDeserializationWithTotallyReversedData(self):
        ch1 = [i * 100000000 for i in range(10000)]
        ch1.reverse()
        testDataBlock = DataBlock.create([ch1], 100001, 0, 1000000000000)
        binary = testDataBlock.serialize()
        recoveredDataBlock = DataBlock.deserialize(binary)
        recoveredDataBlock.pythonalize()
        self.assertDataBlockEqual(testDataBlock, recoveredDataBlock)

    def testDataBlockSerializationAndDeserializationWithReleasedDataBlock(self):
        testDataBlock = DataBlock.generate(
            {'CreationTime': 100, 'DataTimeBegin': 10, 'DataTimeEnd': 1000000000010}, 
            {0: ['Period', 10000], 1: ['Random', 230000], 5: ['Random', 105888], 10: ['Period', 10], 12: ['Random', 1]}
        )
        testDataBlock.release()
        binary = testDataBlock.serialize()
        recoveredDataBlock = DataBlock.deserialize(binary)
        self.assertDataBlockEqual(testDataBlock, recoveredDataBlock, compareContent=False)
        self.assertIsNone(testDataBlock.getContent())
        self.assertIsNone(recoveredDataBlock.getContent())

    def testDataBlockConvertResolution(self):
        fineDataBlock = DataBlock.generate(
            {'CreationTime': 100, 'DataTimeBegin': 10, 'DataTimeEnd': 1000000000010}, 
            {0: ['Period', 10000], 1: ['Random', 230000], 5: ['Random', 105888], 10: ['Period', 10], 12: ['Random', 1]}
        )
        coarseDataBlock1 = fineDataBlock.convertResolution(12e-12)
        self.assertEqual(fineDataBlock.creationTime, coarseDataBlock1.creationTime)
        self.assertEqual(int(fineDataBlock.dataTimeBegin / 12), coarseDataBlock1.dataTimeBegin)
        self.assertEqual(int(fineDataBlock.dataTimeEnd / 12), coarseDataBlock1.dataTimeEnd)
        self.assertEqual(fineDataBlock.sizes, coarseDataBlock1.sizes)
        self.assertEqual(fineDataBlock.resolution, 1e-12)
        self.assertEqual(coarseDataBlock1.resolution, 12e-12)
        self.assertEqual(len(fineDataBlock.getContent()), len(coarseDataBlock1.getContent()))
        for ch in range(len(fineDataBlock.sizes)):
            ch1 = fineDataBlock.getContent(ch)
            ch2 = coarseDataBlock1.getContent(ch)
            self.assertEqual(fineDataBlock.sizes[ch], len(ch1))
            for i in range(len(ch1)):
                self.assertEqual(int(ch1[i] / 12), ch2[i])
        fineDataBlock.release()
        coarseDataBlock2 = fineDataBlock.convertResolution(24e-12)
        self.assertEqual(fineDataBlock.creationTime, coarseDataBlock2.creationTime)
        self.assertEqual(int(fineDataBlock.dataTimeBegin / 24), coarseDataBlock2.dataTimeBegin)
        self.assertEqual(int(fineDataBlock.dataTimeEnd / 24), coarseDataBlock2.dataTimeEnd)
        self.assertEqual(fineDataBlock.sizes, coarseDataBlock2.sizes)
        self.assertEqual(coarseDataBlock2.resolution, 24e-12)
        self.assertIsNone(coarseDataBlock2.getContent())

    def testDataBlockLazyDeserializeAndUnpack(self):
        testDataBlock = DataBlock.generate(
            {'CreationTime': 100, 'DataTimeBegin': 10, 'DataTimeEnd': 1000000000010}, 
            {0: ['Period', 10000], 1: ['Random', 230000], 5: ['Random', 105888], 10: ['Period', 10], 12: ['Random', 1]}
        )
        binary = testDataBlock.serialize()
        recoveredDataBlock = DataBlock.deserialize(binary, True)
        try:
            recoveredDataBlock.getContent()
            self.fails()
        except RuntimeError as e:
            self.assertEqual(str(e), 'This DataBlock is not unpacked.')
        self.assertDataBlockEqual(testDataBlock, recoveredDataBlock, compareContent=False)
        self.assertIsNone(recoveredDataBlock.content)
        self.assertFalse(recoveredDataBlock.isReleased())
        recoveredDataBlock.unpack()
        recoveredDataBlock.unpack()
        try:
            recoveredDataBlock.getContent()
            self.fails()
        except RuntimeError as e:
            self.assertEqual(str(e), 'This DataBlock is not Pythonalized.')
        recoveredDataBlock.pythonalize()
        self.assertEqual([len(c) for c in recoveredDataBlock.getContent()], recoveredDataBlock.sizes)
        self.assertFalse(recoveredDataBlock.isReleased())
        recoveredDataBlock2 = DataBlock.deserialize(binary, True)
        recoveredDataBlock2.release()
        recoveredDataBlock2.unpack()
        self.assertIsNone(recoveredDataBlock2.getContent())

    # def testSyncedDataBlock(self):
    #     testDataBlock = DataBlock.generate(
    #         {'CreationTime': 100, 'DataTimeBegin': 20, 'DataTimeEnd': 1000000000020}, 
    #         {0: ['Period', 10000], 1: ['Random', 230000], 5: ['Random', 105888], 10: ['Period', 10], 12: ['Random', 1]}
    #     )
    #   //   testDataBlock.content.foreach(content => content.zipWithIndex.foreach(z => content(z._2) = z._1.sorted))
    #   //   val testDataBlockRef = DataBlock.deserialize(testDataBlock.serialize())
    #   //   assertThrows[IllegalArgumentException](testDataBlock.synced(List(0, 1, 2, 4)))
    #   //   val delays = List(10000000, 10L, 0, 0, 0, -10000, 0, 0, 0, 0, 10, 0, -10, 0, 0, 0)
    #   //   val testDelayedDataBlock = testDataBlock.synced(delays)
    #   //   (testDelayedDataBlock.content.get zip testDataBlock.content.get zip testDelayedDataBlock.delays).foreach(z => (z._1._1 zip z._1._2).foreach(zz => assert(zz._1 - zz._2 == z._2)))
    #   //   assertThrows[IllegalArgumentException](testDataBlock.synced(delays, Map("Method" -> "N")))
    #   //   val testSyncedDataBlock = testDataBlock.synced(delays, Map("Method" -> "PeriodSignal", "SyncChannel" -> "0", "Period" -> "2e8"))
    #   //   (testSyncedDataBlock.content.get zip testSyncedDataBlock.sizes).foreach(z => assert(z._1.size == z._2))
    #   //   (testSyncedDataBlock.content.get zip testDataBlock.content.get).zipWithIndex.foreach(z => {
    #   //     val size1 = z._1._1.size
    #   //     val list2 = z._1._2.filter(t => t + delays(z._2) >= testDataBlock.content.get(0)(0) + delays(0) && t + delays(z._2) <= testDataBlock.content.get(0).last + delays(0))
    #   //     val size2 = list2.size
    #   //     assert(size1 == size2)
    #   //     val mappedList2 = list2.map(v => (v + delays(z._2) - delays(0)) * 2)
    #   //     (mappedList2 zip z._1._1).foreach(zz => assert(math.abs(zz._1 - zz._2) < 2))
    #   //   })
    #   //   (testDataBlockRef.content.get zip testDataBlock.content.get).foreach(z => {
    #   //     assert(z._1.size == z._2.size)
    #   //     (z._1 zip z._2).foreach(zz => assert(zz._1 == zz._2))
    #   //   })
    #   // }

    # def testDataBlockRanged(self):
        # testDataBlock = DataBlock.generate(
        #     {'CreationTime': 100, 'DataTimeBegin': 1000000000010, 'DataTimeEnd': 2000000000010}, 
        #     {0: ['Period', 10000], 10: ['Period', 10], 12: ['Random', 2000000]}
        # )
        # rangedDataBlock1 = testDataBlock.ranged()
        #     assert(testDataBlock.sizes.toList == rangedDataBlock1.sizes.toList)
        #     assert(testDataBlock.creationTime == rangedDataBlock1.creationTime)
        #     assert(testDataBlock.dataTimeBegin == rangedDataBlock1.dataTimeBegin)
        #     assert(testDataBlock.dataTimeEnd == rangedDataBlock1.dataTimeEnd)
        #     assert(testDataBlock.sizes.toList == rangedDataBlock1.sizes.toList)
        #     Range(0, testDataBlock.sizes.length).map(ch => {
        #       val rangedDataBlockChannel = rangedDataBlock1.getContent(ch).toList
        #       assert(testDataBlock.sizes(ch) == rangedDataBlockChannel.size)
        #       (testDataBlock.getContent(ch) zip rangedDataBlockChannel).foreach(z => assert(z._1 == z._2))
        #     })

        #     val rangedDataBlock2 = testDataBlock.ranged(1200000000010L, 1700000000009L)
        #     assert(testDataBlock.sizes.toList.map(_ / 2) == rangedDataBlock2.sizes.toList)
        #     assert(testDataBlock.creationTime == rangedDataBlock2.creationTime)
        #     assert(1200000000010L == rangedDataBlock2.dataTimeBegin)
        #     assert(1700000000009L == rangedDataBlock2.dataTimeEnd)
        #     Range(0, testDataBlock.sizes.length).map(ch => rangedDataBlock2.getContent(ch).foreach(t => assert(t >= rangedDataBlock2.dataTimeBegin && t <= rangedDataBlock2.dataTimeEnd)))
        #   }

#   test("Test DataBlock merge.") {
#     val testDataBlock1 = DataBlock
#       .generate(
#         Map("CreationTime" -> 100, "DataTimeBegin" -> 1000000000010L, "DataTimeEnd" -> 2000000000010L),
#         Map(
#           0 -> List("Period", 10000),
#           10 -> List("Period", 10),
#           12 -> List("Period", 2000000)
#         )
#       )
#       .ranged(after = 1500000000010L)
#     val testDataBlock2 = DataBlock.generate(
#       Map("CreationTime" -> 100, "DataTimeBegin" -> 2000000000010L, "DataTimeEnd" -> 3000000000010L),
#       Map(
#         0 -> List("Period", 10000),
#         10 -> List("Period", 10),
#         12 -> List("Period", 2000000)
#       )
#     )
#     val testDataBlock3 = DataBlock.generate(
#       Map("CreationTime" -> 100, "DataTimeBegin" -> 3000000000010L, "DataTimeEnd" -> 4000000000010L),
#       Map(
#         0 -> List("Period", 10000),
#         10 -> List("Period", 10),
#         12 -> List("Period", 2000000)
#       )
#     )
#     try { DataBlock.merge(testDataBlock3 :: testDataBlock1 :: Nil) }
#     catch { case e: IllegalArgumentException => }
#     try { DataBlock.merge(testDataBlock1 :: testDataBlock3 :: Nil) }
#     catch { case e: IllegalArgumentException => }
#     DataBlock.merge(testDataBlock1 :: testDataBlock3 :: Nil, true)
#     val mergedDataBlock = DataBlock.merge(testDataBlock1 :: testDataBlock2 :: testDataBlock3 :: Nil)
#     Range(0, testDataBlock1.sizes.size).foreach(ch => assert(testDataBlock1.getContent(ch).size + testDataBlock2.getContent(ch).size + testDataBlock3.getContent(ch).size == mergedDataBlock.getContent(ch).size))
#     assert(mergedDataBlock.getContent(0).size == 25000)
#     Range(0, testDataBlock1.sizes.size).foreach(ch => assert((testDataBlock1.getContent(ch).headOption == mergedDataBlock.getContent(ch).headOption)))
#     Range(0, testDataBlock1.sizes.size).foreach(ch => assert((testDataBlock3.getContent(ch).lastOption == mergedDataBlock.getContent(ch).lastOption)))
#     assert(testDataBlock1.creationTime == mergedDataBlock.creationTime)
#     assert(testDataBlock1.dataTimeBegin == mergedDataBlock.dataTimeBegin)
#     assert(testDataBlock3.dataTimeEnd == mergedDataBlock.dataTimeEnd)
#   }
# }

    def assertDataBlockEqual(self, db1, db2, compareContent=True):
        self.assertEqual(db1.creationTime, db2.creationTime)
        self.assertEqual(db1.dataTimeBegin, db2.dataTimeBegin)
        self.assertEqual(db1.dataTimeEnd, db2.dataTimeEnd)
        self.assertEqual(db1.sizes, db2.sizes)
        if compareContent:
            for ch in range(len(db1.sizes)):
                ch1 = db1.getContent(ch)
                ch2 = db2.getContent(ch)
                self.assertEqual(db1.sizes[ch], len(ch1))
                for i in range(len(ch1)):
                    self.assertEqual(ch1[i], ch2[i])

    def tearDown(self):
        pass

    @classmethod
    def tearDownClass(cls):
        pass


if __name__ == '__main__':
    unittest.main()
