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
    # nc = (c_longlong * len(c))()
    # for i in range(len(c)):
    #   nc[i] = c[i]
    nativeContent.append(convertNativeList(c))
  return nativeContent

def convertContent(contentNative):
  if contentNative is None: return None
  return [list(ch) for ch in contentNative]


def serializeNative(data, begin, end):
  buffer = bytes((end - begin) * 8)
  # if isinstance(data, list): data = convertNativeList(data)
  size = lib.serializeDataBlock(data, begin, end, buffer);
  return buffer[:size]
  # return b''


  import numpy as np
  data = data[begin: end]
  data = np.array(data)
  head = data[0]
  unit = bytearray(16)
  buffer = bytearray(len(data) * 8)
  for i in range(8):
    buffer[7 - i] = (head & 0xFF)
    head >>= 8
  unitSize = 15
  hasHalfByte = False
  halfByte = 0
  pBuffer = 8
  i = 0
  while (i < len(data) - 1):
    delta = (data[i + 1] - data[i])
    i += 1
    if (delta > 1e16 or delta < -1e16):
      return -1
    value = delta
    length = 0
    valueBase = 0 if delta >= 0 else -1
    for j in range(unitSize):
      unit[unitSize - length] = value & 0xf
      value >>= 4
      length += 1
      if value == valueBase and not ((unit[unitSize - length + 1] & 0x8) == (0x8 if delta >= 0 else 0x0)):
        break
    unit[unitSize - length] = length
    p = 0
    while p <= length:
      if hasHalfByte:
        buffer[pBuffer] = ((halfByte << 4) | unit[unitSize - length + p])
        pBuffer += 1
      else:
        halfByte = unit[unitSize - length + p]
      hasHalfByte = not hasHalfByte
      p += 1
  if hasHalfByte:
    buffer[pBuffer] = (halfByte << 4)
    pBuffer += 1
  return bytes(buffer[:pBuffer])


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
