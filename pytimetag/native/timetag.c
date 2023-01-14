#include "timetag.h"

int serializeDataBlock(long long *data, int begin, int end, unsigned char *buffer)
{
  long long head = data[begin];
  unsigned char unit[16];
  for (int i = 0; i < 8; i++)
  {
    buffer[7 - i] = (head & 0xFF);
    head >>= 8;
  }
  int unitSize = 15;
  int hasHalfByte = 0;
  int halfByte = 0;
  int pBuffer = 8;
  int i = begin;
  while (i < end - 1)
  {
    long long delta = data[i + 1] - data[i];
    i++;
    if (delta > 1e16 || delta < -1e16)
    {
      printf("-1-1-1\n");
      return -1;
    }
    long long value = delta;
    int length = 0;
    int valueBase = (delta >= 0) ? 0 : -1;
    for (int j = 0; j < unitSize; j++)
    {
      unit[unitSize - length] = value & 0xf;
      value >>= 4;
      length++;
      if (value == valueBase && !((unit[unitSize - length + 1] & 0x8) == ((delta >= 0) ? 0x8 : 0x0)))
      {
        break;
      }
    }
    unit[unitSize - length] = length;
    int p = 0;
    while (p <= length)
    {
      if (hasHalfByte)
      {
        buffer[pBuffer] = ((halfByte << 4) | unit[unitSize - length + p]);
        pBuffer++;
      }
      else
      {
        halfByte = unit[unitSize - length + p];
      }
      hasHalfByte = !hasHalfByte;
      p++;
    }
  }
  if (hasHalfByte)
  {
    buffer[pBuffer] = (halfByte << 4);
    pBuffer++;
  }
  return pBuffer;
  // return bytes(buffer[:pBuffer])
}

int deserializeDataBlock(unsigned char *data, int length, long long *result)
{
  int pResult = 0;
  if (length > 0)
  {
    long long offset = 0;
    offset += data[0];
    for (int i = 0; i < 7; i++)
    {
      offset <<= 8;
      offset += data[i + 1];
    }
    result[pResult] = offset;
    pResult++;
    long long previous = offset;

    int positionC = 8;
    int pre = 1;

    while (positionC < length)
    {
      int len = (pre ? ((data[positionC] >> 4) & 0x0f) : (data[positionC++] & 0x0f)) - 1;
      pre = 1 - pre;
      if (len >= 0)
      {
        long long value = ((pre ? ((data[positionC] >> 4) & 0x0f) : (data[positionC++] & 0x0f)) & 0xf);
        pre = 1 - pre;
        if ((value & 0x8) == 0x8)
        {
          value |= -16;
        }
        while (len > 0)
        {
          value <<= 4;
          value |= ((pre ? ((data[positionC] >> 4) & 0x0f) : (data[positionC++] & 0x0f)) & 0xf);
          pre = 1 - pre;
          len -= 1;
        }
        previous += value;
        result[pResult] = previous;
        pResult++;
      }
    }
  }
  return pResult;
}

void mergeDataSection(long long *des, int pDest, long long *src, int pSrc, int size)
{
  memcpy(des + pDest, src + pSrc, size);
}