#!/usr/bin/env python3
"""Offline tests for rastertovevor (no printer required).

Builds synthetic CUPS rasters with build/mkras, runs the filter and checks
the TSPL stream byte-for-byte against the sequence documented from the vendor
filter.  Run with `make test`.
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILTER = os.path.join(ROOT, "build", "rastertovevor")
MKRAS = os.path.join(ROOT, "build", "mkras")
PPD203 = os.path.join(ROOT, "ppd", "vevor-label-203dpi.ppd")
PPD300 = os.path.join(ROOT, "ppd", "vevor-label-300dpi.ppd")

failures = 0


def run_filter(raster, options="", ppd=None):
    env = dict(os.environ)
    if ppd:
        env["PPD"] = ppd
    else:
        env.pop("PPD", None)
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(raster)
        path = tf.name
    try:
        p = subprocess.run([FILTER, "1", "user", "title", "1", options, path],
                           capture_output=True, env=env)
    finally:
        os.unlink(path)
    return p.returncode, p.stdout, p.stderr.decode(errors="replace")


def mkras(w, h, dpi, pattern, pages=1):
    p = subprocess.run([MKRAS, str(w), str(h), str(dpi), pattern, str(pages)],
                       capture_output=True, check=True)
    return p.stdout


def header(w_mm, h_mm, ref=(0, 0), tracking="GAP 3 mm,0 mm", density=8, speed=4,
           autodotted=False, wbytes=None, hdots=None):
    parts = [b"\x00" * 200,
             f"SIZE {w_mm} mm,{h_mm} mm\r\n".encode(),
             f"REFERENCE {ref[0]},{ref[1]}\r\n".encode(),
             f"{tracking}\r\n".encode()]
    if density is not None:
        parts.append(f"DENSITY {density}\r\n".encode())
    if speed is not None:
        parts.append(f"SPEED {speed}\r\n".encode())
    parts += [b"SETC AUTODOTTED ON\r\n" if autodotted else b"SETC AUTODOTTED OFF\r\n",
              b"SETC PAUSEKEY ON\r\n", b"SETC WATERMARK OFF\r\n", b"CLS\r\n",
              f"BITMAP 0,0,{wbytes},{hdots},1,".encode()]
    return b"".join(parts)


TRAILER = b"\nPRINT 1,1\r\n"


def check(name, cond, detail=""):
    global failures
    if cond:
        print(f"  ok   {name}")
    else:
        failures += 1
        print(f"  FAIL {name} {detail}")


def expect_equal(name, got, want):
    if got == want:
        check(name, True)
        return
    # find first difference for a readable message
    i = next((k for k in range(min(len(got), len(want))) if got[k] != want[k]),
             min(len(got), len(want)))
    check(name, False, f"\n       first diff at byte {i}:\n"
                       f"       got  {got[max(0, i - 24):i + 24]!r}\n"
                       f"       want {want[max(0, i - 24):i + 24]!r}")


def test_basic_203():
    print("basic 12x8 @203 dpi, top row black, PPD defaults")
    rc, out, err = run_filter(mkras(12, 8, 203, "toprow"), ppd=PPD203)
    check("exit status 0", rc == 0, err)
    # 12 px -> 2 bytes/row; row 0 = 12 black bits + 4 white pad bits = 00 0F
    bitmap = b"\x00\x0f" + b"\xff\xff" * 7
    want = header(2, 1, wbytes=2, hdots=8) + bitmap + TRAILER
    expect_equal("TSPL stream", out, want)
    check("PAGE: line on stderr", "PAGE: 1 1" in err, err)


def test_size_rounding_and_300dpi():
    print("SIZE rounding: 4x6in at 203 (798x1198) and at 300 (1181x1772)")
    rc, out, _ = run_filter(mkras(798, 1198, 203, "toprow"), ppd=PPD203)
    check("203 dpi -> SIZE 100 mm,150 mm", b"SIZE 100 mm,150 mm\r\n" in out)
    rc, out, _ = run_filter(mkras(1181, 1772, 300, "toprow"), ppd=PPD300)
    check("300 dpi -> SIZE 99 mm,148 mm (ceil(dots/12))",
          b"SIZE 99 mm,148 mm\r\n" in out)
    rc, out, _ = run_filter(mkras(1200, 1800, 300, "toprow"), ppd=PPD300)
    check("300 dpi 1200x1800 -> SIZE 100 mm,150 mm", b"SIZE 100 mm,150 mm\r\n" in out)


def test_options():
    print("options through the PPD")
    ras = mkras(8, 4, 203, "toprow")
    rc, out, _ = run_filter(ras, "Darkness=Default zePrintRate=Default", ppd=PPD203)
    check("Darkness=Default omits DENSITY", b"DENSITY" not in out)
    check("zePrintRate=Default omits SPEED", b"SPEED" not in out)
    rc, out, _ = run_filter(ras, "Darkness=15 zePrintRate=1", ppd=PPD203)
    check("Darkness=15 -> DENSITY 15", b"DENSITY 15\r\n" in out)
    check("zePrintRate=1 -> SPEED 2 (vendor clamp)", b"SPEED 2\r\n" in out)
    rc, out, _ = run_filter(ras, "zeMediaTracking=BLine GapOrMarkHeight=5 GapOrMarkOffset=2",
                            ppd=PPD203)
    check("BLine -> BLINE 5 mm,2 mm", b"BLINE 5 mm,2 mm\r\n" in out)
    rc, out, _ = run_filter(ras, "zeMediaTracking=Continuous", ppd=PPD203)
    check("Continuous -> GAP 0 mm,0 mm", b"GAP 0 mm,0 mm\r\n" in out)
    rc, out, _ = run_filter(ras, "AdjustHoriaontal=-3 AdjustVertical=2", ppd=PPD203)
    check("offsets in mm -> REFERENCE -24,16 at 203 dpi", b"REFERENCE -24,16\r\n" in out)
    rc, out, _ = run_filter(mkras(8, 4, 300, "toprow"), "AdjustHoriaontal=1 AdjustVertical=1",
                            ppd=PPD300)
    check("offsets -> REFERENCE 12,12 at 300 dpi", b"REFERENCE 12,12\r\n" in out)
    rc, out, _ = run_filter(ras, "AutoDotted=1", ppd=PPD203)
    check("AutoDotted=1 -> SETC AUTODOTTED ON", b"SETC AUTODOTTED ON\r\n" in out)


def test_threshold():
    print("black threshold: grey 200 prints, grey 201 does not")
    rc, out, _ = run_filter(mkras(8, 1, 203, "grey"), ppd=PPD203)
    check("200 -> all dots (0x00)", out.endswith(b"1,\x00" + TRAILER), out[-40:])
    rc, out, _ = run_filter(mkras(3, 3, 203, "diag"), ppd=PPD203)
    # diag: (0,0),(1,1),(2,2) black, rest 201 (white). 3 px -> 1 byte/row.
    check("diag rows 7F BF DF", out.endswith(b"1," + b"\x7f\xbf\xdf" + TRAILER), out[-40:])


def test_rotation():
    print("rotation of a 4x2 page with a black top-left pixel")
    ras = mkras(4, 2, 203, "corner")
    rc, out, _ = run_filter(ras, "Rotate=0", ppd=PPD203)
    check("0: BITMAP 0,0,1,2 rows 7F FF", out.endswith(b"BITMAP 0,0,1,2,1,\x7f\xff" + TRAILER))
    rc, out, _ = run_filter(ras, "Rotate=1", ppd=PPD203)
    check("180: rows FF EF (pixel at x=3,y=1)", out.endswith(b"BITMAP 0,0,1,2,1,\xff\xef" + TRAILER))
    rc, out, _ = run_filter(ras, "Rotate=2", ppd=PPD203)
    # 90: dst[x*H + y] = src[(H-1-y)*W + x]; src black at (0,0) -> dst x=0,y=H-1=1
    check("90: SIZE swapped, BITMAP 0,0,1,4, rows BF FF FF FF",
          b"SIZE 1 mm,1 mm" in out and out.endswith(b"BITMAP 0,0,1,4,1,\xbf\xff\xff\xff" + TRAILER))
    rc, out, _ = run_filter(ras, "Rotate=3", ppd=PPD203)
    # 270: dst[x*H + y] = src[y*W + (W-1-x)]; src (0,0) -> x=W-1=3,y=0 -> row 3, col 0
    check("270: rows FF FF FF 7F", out.endswith(b"BITMAP 0,0,1,4,1,\xff\xff\xff\x7f" + TRAILER))


def test_multipage_and_noppd():
    print("multiple pages and running without a PPD")
    rc, out, _ = run_filter(mkras(8, 1, 203, "toprow", 3), ppd=PPD203)
    check("3 pages -> 3 PRINT commands", out.count(b"PRINT 1,1\r\n") == 3)
    check("3 pages -> 3 SIZE commands", out.count(b"SIZE ") == 3)
    rc, out, err = run_filter(mkras(8, 1, 203, "toprow"), "Darkness=10 Rotate=1")
    check("no PPD: exit 0", rc == 0, err)
    check("no PPD: options from the command line", b"DENSITY 10\r\n" in out)
    check("no PPD: SPEED omitted when unset", b"SPEED" not in out)


def main():
    for f in (FILTER, MKRAS, PPD203, PPD300):
        if not os.path.exists(f):
            print("missing", f, "- run `make` first")
            return 2
    test_basic_203()
    test_size_rounding_and_300dpi()
    test_options()
    test_threshold()
    test_rotation()
    test_multipage_and_noppd()
    print("\n%s" % ("ALL TESTS PASSED" if failures == 0 else f"{failures} FAILURE(S)"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
