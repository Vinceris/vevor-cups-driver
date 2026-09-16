/*
 * mkras - write a small synthetic CUPS raster to stdout for testing
 * rastertovevor without a printer.
 *
 * Usage: mkras WIDTH HEIGHT DPI PATTERN [PAGES]
 *
 *   PATTERN  toprow      first row black (0), everything else white (255)
 *            diag        pixel (x,y) black where x == y, grey 201 elsewhere
 *            corner      top-left pixel black, rest white (rotation checks)
 *            grey        every pixel 200 (just below the black threshold)
 *
 * 8-bit W colourspace (255 = white), like the raster CUPS produces from the
 * driver PPD.
 *
 * Copyright 2026 Mattia Colombo - Apache-2.0
 */
#include <cups/raster.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int
main(int argc, char *argv[])
{
  if (argc < 5)
  {
    fprintf(stderr, "Usage: mkras WIDTH HEIGHT DPI PATTERN [PAGES]\n");
    return 2;
  }

  unsigned   W = (unsigned)atoi(argv[1]), H = (unsigned)atoi(argv[2]);
  unsigned   dpi = (unsigned)atoi(argv[3]);
  const char *pattern = argv[4];
  int        pages = argc > 5 ? atoi(argv[5]) : 1;

  cups_raster_t *r = cupsRasterOpen(1, CUPS_RASTER_WRITE);
  if (!r)
    return 1;

  cups_page_header2_t h;
  memset(&h, 0, sizeof(h));
  h.cupsWidth        = W;
  h.cupsHeight       = H;
  h.cupsBytesPerLine = W;
  h.cupsBitsPerColor = 8;
  h.cupsBitsPerPixel = 8;
  h.cupsNumColors    = 1;
  h.cupsColorSpace   = CUPS_CSPACE_W;
  h.HWResolution[0]  = dpi;
  h.HWResolution[1]  = dpi;
  h.NumCopies        = 1;
  h.PageSize[0]      = (unsigned)(W * 72 / dpi);
  h.PageSize[1]      = (unsigned)(H * 72 / dpi);

  unsigned char *row = malloc(W);
  if (!row)
    return 1;

  for (int p = 0; p < pages; p++)
  {
    if (!cupsRasterWriteHeader2(r, &h))
      return 1;
    for (unsigned y = 0; y < H; y++)
    {
      for (unsigned x = 0; x < W; x++)
      {
        unsigned char v = 255;
        if (!strcmp(pattern, "toprow"))
          v = y == 0 ? 0 : 255;
        else if (!strcmp(pattern, "diag"))
          v = x == y ? 0 : 201;
        else if (!strcmp(pattern, "corner"))
          v = (x == 0 && y == 0) ? 0 : 255;
        else if (!strcmp(pattern, "grey"))
          v = 200;
        row[x] = v;
      }
      if (cupsRasterWritePixels(r, row, W) < 1)
        return 1;
    }
  }

  cupsRasterClose(r);
  free(row);
  return 0;
}
