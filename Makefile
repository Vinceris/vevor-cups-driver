# rastertovevor - CUPS raster -> TSPL filter for VEVOR Y486 label printers
#
#   make            build build/rastertovevor (universal arm64 + x86_64 on macOS)
#   make test       run the offline test-suite (no printer needed)
#   make clean

CC      ?= cc
CFLAGS  ?= -O2 -Wall -Wextra
LDLIBS   = -lcups -lcupsimage

UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Darwin)
  ARCHS   ?= -arch arm64 -arch x86_64
  CFLAGS  += -mmacosx-version-min=11.0
  SIGN     = codesign --force --sign - $@
else
  # Linux: use cups-config when available (Debian: libcups2-dev / libcupsimage2-dev)
  CFLAGS  += $(shell cups-config --cflags 2>/dev/null)
  LDLIBS  := $(shell cups-config --libs 2>/dev/null) -lcupsimage
  ARCHS   =
  SIGN    = true
endif

BIN = build/rastertovevor

all: $(BIN)

$(BIN): src/rastertovevor.c
	mkdir -p build
	$(CC) $(ARCHS) $(CFLAGS) -o $@ $< $(LDLIBS)
	$(SIGN)

build/mkras: tests/mkras.c
	mkdir -p build
	$(CC) $(ARCHS) $(CFLAGS) -o $@ $< $(LDLIBS)

test: $(BIN) build/mkras
	python3 tests/test_filter.py

ppd:
	python3 tools/gen_ppd.py

clean:
	rm -rf build

.PHONY: all test ppd clean
