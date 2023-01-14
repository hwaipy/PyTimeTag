#include <stdio.h>
#include <string.h>

int serializeDataBlock(long long* data, int begin, int end, unsigned char* buffer);

int deserializeDataBlock(unsigned char* data, int length, long long* result);

void mergeDataSection(long long* des, int pDest, long long* src, int pSrc, int size);