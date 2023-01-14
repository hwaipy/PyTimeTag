from ctypes import cdll, c_longlong
import platform
import os

lib = cdll.LoadLibrary(f"{os.path.realpath(__file__)[:-9]}timetag.{'so' if platform.system() == 'Linux' else 'dll'}")


def convertNativeList(data):
  nl = (c_longlong * len(data))()
  for i in range(len(data)):
    nl[i] = data[i]
  return nl  

def convertNativeContent(content):
  if content is None: return None
  nativeContent = []
  for c in content:
    nativeContent.append(convertNativeList(c))
  return nativeContent

def convertContent(contentNative):
  if contentNative is None: return None
  return [list(ch) for ch in contentNative]


def serializeNative(data, begin, end):
  buffer = bytes((end - begin) * 8)
  size = lib.serializeDataBlock(data, begin, end, buffer);
  return buffer[:size]


def deserializeNative(data):
  if isinstance(data, bytes):
    data = [data]
  resultSet = []
  for section in data:
    buffer = (c_longlong * int(len(section) / 2))()
    resultSize = lib.deserializeDataBlock(section, len(section), buffer)
    resultSet.append([buffer, resultSize])
  result = (c_longlong * sum(r[1] for r in resultSet))()
  totalDataSize = 0
  for r in resultSet:
    lib.mergeDataSection(result, totalDataSize, r[0], 0, r[1] * 8)
    totalDataSize += r[1]
  return result

# class TimeTagChannelNative():
#   def __init__(self, buffer, length):
#     self.buffer = buffer
#     self.length = length

#   def __setitem__(self, k, v):
#     raise NotImplementedError()

#   def __getitem__(self, k):
#     if k >= self.length: raise IndexError(f"{k} out of range of {self.length}.")
#     return self.buffer[k]

#   def __len__(self):
#     return self.length

#   def __eq__(self, __o: object):
#     if len(__o) != len(self): return False
#     for i in range(len(self)):
#       if __o[i] != self[i]: return False
#     return True
