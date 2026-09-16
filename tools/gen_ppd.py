#!/usr/bin/env python3
"""Generate the two PPDs (203 dpi and 300 dpi) for rastertovevor.

Run from the repository root:  python3 tools/gen_ppd.py
Writes ppd/vevor-label-203dpi.ppd and ppd/vevor-label-300dpi.ppd.

The option keywords are the ones the vendor PPD uses, so a queue that is
re-pointed to these PPDs keeps its saved settings.
"""
import os

FILTER = "/Library/Printers/VevorOpen/Filter/rastertovevor"
MAX_W_PT, MAX_H_PT = 294, 5670   # ~104 mm x 2 m, same limits as the vendor PPD

# (label, width, height, unit) - unit "mm" or "in"
SIZES = [
    ("100 x 150 mm (4 x 6 in)", 100, 150, "mm"),
    ("100 x 100 mm", 100, 100, "mm"),
    ("100 x 120 mm", 100, 120, "mm"),
    ("100 x 170 mm", 100, 170, "mm"),
    ("100 x 180 mm", 100, 180, "mm"),
    ("100 x 200 mm", 100, 200, "mm"),
    ("100 x 250 mm", 100, 250, "mm"),
    ("100 x 50 mm", 100, 50, "mm"),
    ("100 x 75 mm", 100, 75, "mm"),
    ("80 x 100 mm", 80, 100, "mm"),
    ("76 x 130 mm", 76, 130, "mm"),
    ("60 x 40 mm", 60, 40, "mm"),
    ("50 x 30 mm", 50, 30, "mm"),
    ("40 x 30 mm", 40, 30, "mm"),
    ("4 x 6 in (US)", 4, 6, "in"),
    ("4 x 4 in", 4, 4, "in"),
    ("4 x 3 in", 4, 3, "in"),
    ("4 x 2 in", 4, 2, "in"),
    ("4 x 1 in", 4, 1, "in"),
    ("4 x 8 in", 4, 8, "in"),
    ("3 x 5 in", 3, 5, "in"),
    ("3 x 2 in", 3, 2, "in"),
    ("3 x 1 in", 3, 1, "in"),
    ("2 x 4 in", 2, 4, "in"),
    ("2 x 2 in", 2, 2, "in"),
    ("2 x 1 in", 2, 1, "in"),
]


def pts(v, unit):
    return int(round(v * 72 / 25.4)) if unit == "mm" else int(round(v * 72))


def size_entries():
    out = []
    seen = set()
    for label, w, h, unit in SIZES:
        wp, hp = pts(w, unit), pts(h, unit)
        name = f"w{wp}h{hp}"
        if name in seen:
            continue
        seen.add(name)
        out.append((name, label, wp, hp))
    return out


def ppd(dpi):
    dpm = 8 if dpi == 203 else 12
    sizes = size_entries()
    default = sizes[0][0]      # 100 x 150 mm
    L = []
    a = L.append
    a('*PPD-Adobe: "4.3"')
    a('*% rastertovevor - open-source driver for VEVOR Y486 / Y486BT label printers')
    a('*% https://github.com/mattiacolombomc/vevor-cups-driver')
    a('*% Licensed under the Apache License, Version 2.0')
    a('*FormatVersion: "4.3"')
    a('*FileVersion: "1.0"')
    a('*LanguageVersion: English')
    a('*LanguageEncoding: ISOLatin1')
    a(f'*PCFileName: "vevor{dpi}.ppd"')
    a('*Manufacturer: "VEVOR"')
    a('*Product: "(VEVOR Label Printer)"')
    a('*cupsVersion: 2.2')
    a('*cupsManualCopies: True')
    a('*cupsModelNumber: 20')
    a(f'*cupsFilter: "application/vnd.cups-raster 0 {FILTER}"')
    a(f'*ModelName: "VEVOR Label Printer {dpi} dpi Open"')
    a(f'*ShortNickName: "VEVOR Label {dpi}dpi"')
    a(f'*NickName: "VEVOR Label Printer {dpi} dpi Open"')
    a('*PSVersion: "(3010.000) 0"')
    a('*LanguageLevel: "3"')
    a('*ColorDevice: False')
    a('*DefaultColorSpace: Gray')
    a('*FileSystem: False')
    a('*Throughput: "1"')
    a('*LandscapeOrientation: Plus90')
    a('*TTRasterizer: Type42')
    a('*HWMargins: 0 0 0 0')
    a('*VariablePaperSize: True')
    a(f'*MaxMediaWidth: "{MAX_W_PT}"')
    a(f'*MaxMediaHeight: "{MAX_H_PT}"')
    a('*CustomPageSize True: "pop pop pop <</PageSize[5 -2 roll]/ImagingBBox null>>setpagedevice"')
    a(f'*ParamCustomPageSize Width: 1 points 36 {MAX_W_PT}')
    a(f'*ParamCustomPageSize Height: 2 points 36 {MAX_H_PT}')
    a('*ParamCustomPageSize WidthOffset: 3 points 0 0')
    a('*ParamCustomPageSize HeightOffset: 4 points 0 0')
    a('*ParamCustomPageSize Orientation: 5 int 0 0')
    a('')
    a('*OpenGroup: General/General')
    a('')
    a('*OpenUI *PageSize/Media Size: PickOne')
    a('*OrderDependency: 10 AnySetup *PageSize')
    a(f'*DefaultPageSize: {default}')
    for name, label, wp, hp in sizes:
        a(f'*PageSize {name}/{label}: "<</PageSize[{wp} {hp}]/ImagingBBox null>>setpagedevice"')
    a('*CloseUI: *PageSize')
    a('')
    a('*OpenUI *PageRegion/Media Size: PickOne')
    a('*OrderDependency: 10 AnySetup *PageRegion')
    a(f'*DefaultPageRegion: {default}')
    for name, label, wp, hp in sizes:
        a(f'*PageRegion {name}/{label}: "<</PageSize[{wp} {hp}]/ImagingBBox null>>setpagedevice"')
    a('*CloseUI: *PageRegion')
    a('')
    a(f'*DefaultImageableArea: {default}')
    for name, label, wp, hp in sizes:
        a(f'*ImageableArea {name}/{label}: "0 0 {wp} {hp}"')
    a('')
    a(f'*DefaultPaperDimension: {default}')
    for name, label, wp, hp in sizes:
        a(f'*PaperDimension {name}/{label}: "{wp} {hp}"')
    a('')
    a('*OpenUI *Resolution/Resolution: PickOne')
    a('*OrderDependency: 20 AnySetup *Resolution')
    a(f'*DefaultResolution: {dpi}dpi')
    a(f'*Resolution {dpi}dpi/{dpi} dpi: "<</HWResolution[{dpi} {dpi}]/cupsBitsPerColor 8/cupsRowCount 8/cupsRowFeed 0/cupsRowStep 0/cupsColorSpace 0>>setpagedevice"')
    a('*CloseUI: *Resolution')
    a('')
    a('*CloseGroup: General')
    a('')
    a('*OpenGroup: PrinterSettings/Printer Settings')
    a('')
    a('*OpenUI *zeMediaTracking/Media Tracking: PickOne')
    a('*OrderDependency: 20 AnySetup *zeMediaTracking')
    a('*DefaultzeMediaTracking: Gap')
    a('*zeMediaTracking Gap/Gap: ""')
    a('*zeMediaTracking BLine/Black Line: ""')
    a('*zeMediaTracking Continuous/Continuous: ""')
    a('*CloseUI: *zeMediaTracking')
    a('')
    a('*OpenUI *GapOrMarkHeight/Gap or Mark Height: PickOne')
    a('*OrderDependency: 20 AnySetup *GapOrMarkHeight')
    a('*DefaultGapOrMarkHeight: 3')
    for i in range(0, 11):
        a(f'*GapOrMarkHeight {i}/{i} mm: ""')
    a('*CloseUI: *GapOrMarkHeight')
    a('')
    a('*OpenUI *GapOrMarkOffset/Gap or Mark Offset: PickOne')
    a('*OrderDependency: 20 AnySetup *GapOrMarkOffset')
    a('*DefaultGapOrMarkOffset: 0')
    for i in range(0, 11):
        a(f'*GapOrMarkOffset {i}/{i} mm: ""')
    a('*CloseUI: *GapOrMarkOffset')
    a('')
    a('*OpenUI *Darkness/Darkness: PickOne')
    a('*OrderDependency: 20 AnySetup *Darkness')
    a('*DefaultDarkness: 8')
    a('*Darkness Default/Printer Default: ""')
    for i in range(0, 16):
        a(f'*Darkness {i}/{i}: ""')
    a('*CloseUI: *Darkness')
    a('')
    a('*OpenUI *zePrintRate/Print Speed: PickOne')
    a('*OrderDependency: 20 AnySetup *zePrintRate')
    a('*DefaultzePrintRate: 4')
    a('*zePrintRate Default/Printer Default: ""')
    for i in range(1, 9):
        a(f'*zePrintRate {i}/{i} inch/sec: ""')
    a('*CloseUI: *zePrintRate')
    a('')
    a('*OpenUI *AutoDotted/Dotted Line: PickOne')
    a('*OrderDependency: 20 AnySetup *AutoDotted')
    a('*DefaultAutoDotted: 0')
    a('*AutoDotted 0/Off: ""')
    a('*AutoDotted 1/On: ""')
    a('*CloseUI: *AutoDotted')
    a('')
    a('*CloseGroup: PrinterSettings')
    a('')
    a('*OpenGroup: PageSet/Page Options')
    a('')
    a('*OpenUI *Rotate/Rotate: PickOne')
    a('*OrderDependency: 30 AnySetup *Rotate')
    a('*DefaultRotate: 0')
    a('*Rotate 0/0 degrees: ""')
    a('*Rotate 1/180 degrees: ""')
    a('*Rotate 2/90 degrees: ""')
    a('*Rotate 3/270 degrees: ""')
    a('*CloseUI: *Rotate')
    a('')
    a('*OpenUI *AdjustHoriaontal/Horizontal Offset: PickOne')
    a('*OrderDependency: 30 AnySetup *AdjustHoriaontal')
    a('*DefaultAdjustHoriaontal: 0')
    for i in range(-20, 21):
        a(f'*AdjustHoriaontal {i}/{i} mm: ""')
    a('*CloseUI: *AdjustHoriaontal')
    a('')
    a('*OpenUI *AdjustVertical/Vertical Offset: PickOne')
    a('*OrderDependency: 30 AnySetup *AdjustVertical')
    a('*DefaultAdjustVertical: 0')
    for i in range(-20, 21):
        a(f'*AdjustVertical {i}/{i} mm: ""')
    a('*CloseUI: *AdjustVertical')
    a('')
    a('*CloseGroup: PageSet')
    a('')
    a('*DefaultFont: Courier')
    a('*Font Courier: Standard "(1.05)" Standard ROM')
    a('*Font Helvetica: Standard "(1.05)" Standard ROM')
    a('*Font Times-Roman: Standard "(1.05)" Standard ROM')
    a(f'*% dots per mm at this resolution: {dpm}')
    a('*% End of PPD')
    return "\n".join(L) + "\n"


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = os.path.join(root, "ppd")
    os.makedirs(outdir, exist_ok=True)
    for dpi in (203, 300):
        path = os.path.join(outdir, f"vevor-label-{dpi}dpi.ppd")
        with open(path, "w", encoding="latin-1") as f:
            f.write(ppd(dpi))
        print("wrote", path)


if __name__ == "__main__":
    main()
