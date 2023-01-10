import numba
import numpy as np

@numba.njit
def serializeJIT(data, buffer, unit):
    head = data[0]
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
    return pBuffer

@numba.njit
def deserializeJIT(data):
    buffer = []
    if len(data) > 0:
        offset = 0
        offset += data[0]
        for i in range(7):
            offset <<= 8
            offset += data[i + 1]
        buffer.append(offset)
        previous = offset

        positionC = 8
        pre = 1

        def hasNext():
            return positionC < len(data)

        def getNext(pre):
            nonlocal positionC
            b = data[positionC]
            if pre:
                return (b >> 4) & 0x0f
            else:
                positionC += 1
                return b & 0x0f

        while (hasNext()):
            length = getNext(pre) - 1
            pre = 1 - pre
            if length >= 0:
                value = (getNext(pre) & 0xf)                
                pre = 1 - pre
                if (value & 0x8) == 0x8:
                    value |= -16
                while length > 0:
                    value <<= 4
                    value |= (getNext(pre) & 0xf)
                    pre = 1 - pre
                    length -= 1
                previous += value
                buffer.append(previous)
    return buffer
