/*
 * rastertovevor - CUPS raster to TSPL filter for VEVOR Y486 / Y486BT
 * thermal label printers (and other TSPL printers of the same OEM family).
 *
 * Copyright 2026 Mattia Colombo
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * ---------------------------------------------------------------------------
 *
 * Why this exists
 *
 *   The driver VEVOR ships for macOS ("Vevor Label Printer" 1.5.8) is an
 *   x86_64-only build of the CUPS `rastertolabel` filter with a TSPL model
 *   bolted on.  macOS 27 no longer carries Rosetta 2 over an upgrade, so on
 *   Apple Silicon the vendor filter fails with "Bad CPU type in executable"
 *   and the printer stops working.  This is a native, universal (arm64 +
 *   x86_64) re-implementation of just the TSPL part.
 *
 * What it emits (byte-for-byte the sequence of the vendor filter, model 0x14)
 *
 *   <200 NUL bytes>                 wake-up padding
 *   SIZE <w> mm,<h> mm\r\n          label size, ceil(dots / dots-per-mm)
 *   REFERENCE <x>,<y>\r\n           origin offset in dots (option value in mm)
 *   GAP <g> mm,<o> mm\r\n           or BLINE <g> mm,<o> mm  or GAP 0 mm,0 mm
 *   DENSITY <d>\r\n                 only when Darkness != Default
 *   SPEED <s>\r\n                   only when zePrintRate != Default (1 -> 2)
 *   SETC AUTODOTTED ON|OFF\r\n
 *   SETC PAUSEKEY ON\r\n
 *   SETC WATERMARK OFF\r\n
 *   CLS\r\n
 *   BITMAP 0,0,<wbytes>,<hdots>,1,<1-bpp rows, 0 = black>
 *   \n
 *   PRINT 1,1\r\n
 *
 *   Pixels with a grey value <= 200 (0 = black, 255 = white) become dots.
 *   The Rotate option rotates the bitmap in software (0, 180, 90, 270).
 *
 * PPD option keywords (identical to the vendor PPD so existing queues keep
 * their settings): Rotate, AdjustHoriaontal (sic), AdjustVertical,
 * zeMediaTracking, GapOrMarkHeight, GapOrMarkOffset, Darkness, zePrintRate,
 * AutoDotted.  Without a PPD the same keywords are read from the job options.
 *
 * CUPS filter argv: job-id user title copies options [file]
 */

#include <cups/cups.h>
#include <cups/ppd.h>
#include <cups/raster.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

/* The PPD API is deprecated in CUPS 2.x but is still what macOS uses for
 * driver queues; silence the warnings. */
#pragma GCC diagnostic ignored "-Wdeprecated-declarations"

#define WAKEUP_NUL_BYTES 200
#define BLACK_THRESHOLD  200   /* grey <= 200 prints a dot */

typedef enum { TRACK_GAP, TRACK_BLINE, TRACK_CONTINUOUS } tracking_t;

typedef struct
{
  int        rotate;        /* 0 = none, 1 = 180, 2 = 90, 3 = 270 */
  int        ref_x_mm;      /* REFERENCE, in mm */
  int        ref_y_mm;
  tracking_t tracking;
  int        gap_height_mm;
  int        gap_offset_mm;
  int        darkness;      /* -1 = printer default (omit DENSITY) */
  int        speed;         /* -1 = printer default (omit SPEED) */
  int        autodotted;
} job_options_t;

static volatile sig_atomic_t Canceled = 0;

static void
cancel_job(int sig)
{
  (void)sig;
  Canceled = 1;
}

/*
 * Option lookup: marked PPD choice first (which already reflects the job's
 * "-o" options once cupsMarkOptions ran), plain job option otherwise.
 */
static const char *
option_value(ppd_file_t *ppd, int num_options, cups_option_t *options,
             const char *keyword)
{
  if (ppd)
  {
    ppd_choice_t *choice = ppdFindMarkedChoice(ppd, keyword);
    if (choice)
      return choice->choice;
  }
  return cupsGetOption(keyword, num_options, options);
}

static void
read_options(ppd_file_t *ppd, int num_options, cups_option_t *options,
             job_options_t *o)
{
  const char *v;

  memset(o, 0, sizeof(*o));
  o->tracking      = TRACK_GAP;
  o->gap_height_mm = 3;
  o->gap_offset_mm = 0;
  o->darkness      = -1;
  o->speed         = -1;

  if ((v = option_value(ppd, num_options, options, "Rotate")) != NULL)
    o->rotate = atoi(v);
  if (o->rotate < 0 || o->rotate > 3)
    o->rotate = 0;

  if ((v = option_value(ppd, num_options, options, "AdjustHoriaontal")) != NULL)
    o->ref_x_mm = atoi(v);
  if ((v = option_value(ppd, num_options, options, "AdjustVertical")) != NULL)
    o->ref_y_mm = atoi(v);

  if ((v = option_value(ppd, num_options, options, "zeMediaTracking")) != NULL)
  {
    if (!strcmp(v, "Continuous"))
      o->tracking = TRACK_CONTINUOUS;
    else if (!strcmp(v, "Gap"))
      o->tracking = TRACK_GAP;
    else
      o->tracking = TRACK_BLINE;
  }

  if ((v = option_value(ppd, num_options, options, "GapOrMarkHeight")) != NULL)
    o->gap_height_mm = atoi(v);
  if ((v = option_value(ppd, num_options, options, "GapOrMarkOffset")) != NULL)
    o->gap_offset_mm = atoi(v);

  if ((v = option_value(ppd, num_options, options, "Darkness")) != NULL &&
      strcmp(v, "Default"))
    o->darkness = atoi(v);

  if ((v = option_value(ppd, num_options, options, "zePrintRate")) != NULL &&
      strcmp(v, "Default"))
  {
    o->speed = atoi(v);
    if (o->speed == 1)          /* the vendor filter clamps 1 ips to 2 */
      o->speed = 2;
  }

  if ((v = option_value(ppd, num_options, options, "AutoDotted")) != NULL)
    o->autodotted = atoi(v) != 0;
}

/*
 * Dots per millimetre for the job resolution: 8 at 203 dpi, 12 at 300 dpi
 * (the two constants hard-wired in the vendor's 203/300 dpi builds).
 */
static unsigned
dots_per_mm(unsigned dpi)
{
  unsigned dpm = (dpi * 10 + 253) / 254;
  return dpm ? dpm : 8;
}

static void
start_page(const cups_page_header2_t *h, const job_options_t *o,
           unsigned bitmap_width, unsigned bitmap_height)
{
  unsigned dpm = dots_per_mm(h->HWResolution[0]);
  int      i;

  for (i = 0; i < WAKEUP_NUL_BYTES; i++)
    putchar(0);

  printf("SIZE %u mm,%u mm\r\n", (bitmap_width + dpm - 1) / dpm,
         (bitmap_height + dpm - 1) / dpm);
  printf("REFERENCE %d,%d\r\n", (int)dpm * o->ref_x_mm, (int)dpm * o->ref_y_mm);

  switch (o->tracking)
  {
    case TRACK_GAP :
        printf("GAP %d mm,%d mm\r\n", o->gap_height_mm, o->gap_offset_mm);
        break;
    case TRACK_BLINE :
        printf("BLINE %d mm,%d mm\r\n", o->gap_height_mm, o->gap_offset_mm);
        break;
    case TRACK_CONTINUOUS :
        fputs("GAP 0 mm,0 mm\r\n", stdout);
        break;
  }

  if (o->darkness >= 0)
    printf("DENSITY %d\r\n", o->darkness);
  if (o->speed >= 0)
    printf("SPEED %d\r\n", o->speed);

  fputs(o->autodotted ? "SETC AUTODOTTED ON\r\n" : "SETC AUTODOTTED OFF\r\n",
        stdout);
  fputs("SETC PAUSEKEY ON\r\n", stdout);
  fputs("SETC WATERMARK OFF\r\n", stdout);
  fputs("CLS\r\n", stdout);

  printf("BITMAP 0,0,%u,%u,1,", (bitmap_width + 7) / 8, bitmap_height);
}

static void
end_page(void)
{
  putchar('\n');
  fputs("PRINT 1,1\r\n", stdout);
  fflush(stdout);
}

/*
 * Convert one raster line to 8-bit grey (0 = black, 255 = white).
 * Returns 0 on success, -1 for an unsupported pixel format.
 */
static int
line_to_grey(const cups_page_header2_t *h, const unsigned char *in,
             unsigned char *out)
{
  unsigned x, w = h->cupsWidth;

  if (h->cupsColorSpace == CUPS_CSPACE_W && h->cupsBitsPerPixel == 8)
  {
    memcpy(out, in, w);
  }
  else if (h->cupsColorSpace == CUPS_CSPACE_K && h->cupsBitsPerPixel == 8)
  {
    for (x = 0; x < w; x++)
      out[x] = (unsigned char)(255 - in[x]);
  }
  else if (h->cupsColorSpace == CUPS_CSPACE_W && h->cupsBitsPerPixel == 1)
  {
    for (x = 0; x < w; x++)
      out[x] = (in[x >> 3] & (0x80 >> (x & 7))) ? 255 : 0;
  }
  else if (h->cupsColorSpace == CUPS_CSPACE_K && h->cupsBitsPerPixel == 1)
  {
    for (x = 0; x < w; x++)
      out[x] = (in[x >> 3] & (0x80 >> (x & 7))) ? 0 : 255;
  }
  else if ((h->cupsColorSpace == CUPS_CSPACE_RGB ||
            h->cupsColorSpace == CUPS_CSPACE_SRGB) && h->cupsBitsPerPixel == 24)
  {
    for (x = 0; x < w; x++)
      out[x] = (unsigned char)((299 * in[3 * x] + 587 * in[3 * x + 1] +
                                114 * in[3 * x + 2]) / 1000);
  }
  else
    return -1;

  return 0;
}

/*
 * Rotate the W x H grey page into a new buffer, exactly as the vendor filter
 * does.  Returns the rotated buffer (may be `src` itself for rotate == 0) and
 * the rotated dimensions.
 */
static unsigned char *
rotate_page(unsigned char *src, unsigned W, unsigned H, int rotate,
            unsigned *outW, unsigned *outH)
{
  unsigned char *dst;
  unsigned      x, y;
  size_t        n = (size_t)W * H;

  if (rotate == 0)
  {
    *outW = W;
    *outH = H;
    return src;
  }

  if ((dst = malloc(n ? n : 1)) == NULL)
    return NULL;

  switch (rotate)
  {
    case 1 : /* 180 degrees */
        for (x = 0; x < n; x++)
          dst[x] = src[n - 1 - x];
        *outW = W;
        *outH = H;
        break;

    case 2 : /* 90 degrees: dst[x*H + y] = src[(H-1-y)*W + x] */
        for (x = 0; x < W; x++)
          for (y = 0; y < H; y++)
            dst[(size_t)x * H + y] = src[(size_t)(H - 1 - y) * W + x];
        *outW = H;
        *outH = W;
        break;

    default : /* 3: 270 degrees: dst[x*H + y] = src[y*W + (W-1-x)] */
        for (x = 0; x < W; x++)
          for (y = 0; y < H; y++)
            dst[(size_t)x * H + y] = src[(size_t)y * W + (W - 1 - x)];
        *outW = H;
        *outH = W;
        break;
  }

  return dst;
}

/*
 * Emit the 1-bpp BITMAP payload: a set bit is white, a clear bit is a dot;
 * padding bits at the end of a row are white.
 */
static void
write_bitmap(const unsigned char *grey, unsigned W, unsigned H)
{
  unsigned      x, y, wbytes = (W + 7) / 8;
  unsigned char *row;

  if ((row = malloc(wbytes ? wbytes : 1)) == NULL)
    return;

  for (y = 0; y < H; y++)
  {
    const unsigned char *line = grey + (size_t)y * W;

    memset(row, 0xff, wbytes);
    for (x = 0; x < W; x++)
      if (line[x] <= BLACK_THRESHOLD)
        row[x >> 3] &= (unsigned char)~(0x80 >> (x & 7));

    fwrite(row, 1, wbytes, stdout);
  }

  free(row);
}

int
main(int argc, char *argv[])
{
  int                 fd = 0;
  cups_raster_t       *ras;
  cups_page_header2_t header;
  ppd_file_t          *ppd = NULL;
  const char          *ppdname;
  int                 num_options;
  cups_option_t       *options = NULL;
  job_options_t       opts;
  int                 page = 0;
  int                 status = 0;

  setbuf(stderr, NULL);

  if (argc < 6 || argc > 7)
  {
    fprintf(stderr, "Usage: %s job-id user title copies options [file]\n",
            argv[0]);
    return 1;
  }

  if (argc == 7)
  {
    if ((fd = open(argv[6], O_RDONLY)) < 0)
    {
      fprintf(stderr, "ERROR: Unable to open raster file \"%s\": %s\n",
              argv[6], strerror(errno));
      return 1;
    }
  }

  if ((ras = cupsRasterOpen(fd, CUPS_RASTER_READ)) == NULL)
  {
    fprintf(stderr, "ERROR: Unable to read raster data\n");
    return 1;
  }

  signal(SIGTERM, cancel_job);

  num_options = cupsParseOptions(argv[5], 0, &options);

  if ((ppdname = getenv("PPD")) != NULL && *ppdname)
  {
    if ((ppd = ppdOpenFile(ppdname)) == NULL)
    {
      ppd_status_t st;
      int          line;

      st = ppdLastError(&line);
      fprintf(stderr, "ERROR: The PPD file could not be opened: %s on line %d\n",
              ppdErrorString(st), line);
      return 1;
    }
    ppdMarkDefaults(ppd);
    cupsMarkOptions(ppd, num_options, options);
  }

  read_options(ppd, num_options, options, &opts);

  while (cupsRasterReadHeader2(ras, &header) && !Canceled)
  {
    unsigned      W = header.cupsWidth, H = header.cupsHeight;
    unsigned      RW, RH;
    unsigned      y;
    unsigned char *line, *grey, *rotated;

    page++;
    fprintf(stderr, "PAGE: %d 1\n", page);
    fprintf(stderr, "INFO: Starting page %d.\n", page);

    if (W == 0 || H == 0 || header.cupsBytesPerLine == 0)
    {
      fprintf(stderr, "ERROR: Empty page.\n");
      status = 1;
      break;
    }

    line = malloc(header.cupsBytesPerLine);
    grey = malloc((size_t)W * H);
    if (!line || !grey)
    {
      fprintf(stderr, "ERROR: Out of memory.\n");
      free(line);
      free(grey);
      status = 1;
      break;
    }

    for (y = 0; y < H && !Canceled; y++)
    {
      if (cupsRasterReadPixels(ras, line, header.cupsBytesPerLine) < 1)
      {
        fprintf(stderr, "ERROR: Short read on page %d line %u.\n", page, y);
        Canceled = 1;
        status = 1;
        break;
      }
      if (line_to_grey(&header, line, grey + (size_t)y * W) < 0)
      {
        fprintf(stderr,
                "ERROR: Unsupported raster format (colorspace %d, %u bpp).\n",
                header.cupsColorSpace, header.cupsBitsPerPixel);
        Canceled = 1;
        status = 1;
        break;
      }
    }
    free(line);

    if (Canceled)
    {
      free(grey);
      break;
    }

    rotated = rotate_page(grey, W, H, opts.rotate, &RW, &RH);
    if (!rotated)
    {
      fprintf(stderr, "ERROR: Out of memory.\n");
      free(grey);
      status = 1;
      break;
    }

    start_page(&header, &opts, RW, RH);
    write_bitmap(rotated, RW, RH);
    end_page();

    if (rotated != grey)
      free(rotated);
    free(grey);

    fprintf(stderr, "INFO: Finished page %d.\n", page);
  }

  cupsRasterClose(ras);
  if (fd != 0)
    close(fd);
  if (ppd)
    ppdClose(ppd);
  cupsFreeOptions(num_options, options);

  if (page == 0 && status == 0)
  {
    fprintf(stderr, "ERROR: No pages were found.\n");
    return 1;
  }

  return status;
}
