"""Local PNG visualization of Financial Decision Engine output. No calculations.

POC scope: Financial Fit only. Other cards await inline-display verification.
"""
import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

PALETTES = {
    'light': dict(bg='#EDF2F1', card='#FFFFFF', text='#12382F', muted='#526D66',
                  panel='#F2F6F4', line='#DCE6E1', accent='#21664E', track='#DDE8E2'),
    'dark': dict(bg='#101B18', card='#182923', text='#EDF6F0', muted='#A4BEB1',
                 panel='#223A30', line='#365044', accent='#8AD8AC', track='#375145')}
STATUSES = {
    'AFFORDABLE': ('#21825B', 'ซื้อได้ตามแผน', 'ข้อมูลที่ยืนยันครอบคลุมราคาสินค้า'),
    'SAVE_FIRST': ('#AA690B', 'แนะนำให้รอเก็บเงิน', 'เก็บเงินเพิ่ม โดยรักษาเป้าหมายเดิม'),
    'NOT_AFFORDABLE': ('#C04E54', 'ยังไม่แนะนำให้ซื้อ', 'ควรจัดการภาระที่ยังไม่ครอบคลุมก่อน'),
    'INSUFFICIENT_DATA': ('#6A7C86', 'ข้อมูลยังไม่เพียงพอ', 'ยืนยันข้อมูลที่ขาดก่อนตัดสินใจซื้อ')}


def font(size, bold=False, font_dir=None):
    folder = Path(font_dir or 'C:/Windows/Fonts')
    path = folder / ('tahomabd.ttf' if bold else 'tahoma.ttf')
    if not path.is_file():
        raise ValueError('Thai font required: set font_dir containing tahoma.ttf and tahomabd.ttf')
    layout = ImageFont.Layout.RAQM if features.check_feature('raqm') else ImageFont.Layout.BASIC
    if layout == ImageFont.Layout.BASIC and os.name != 'nt':
        raise ValueError('Thai shaping requires RAQM, or Windows native text rendering')
    return ImageFont.truetype(str(path), size, layout_engine=layout)


def windows_text_mask(message, size, bold=False):
    """Windows Unicode text layout for Thai when Pillow wheel lacks RAQM.

    DrawTextW shapes complex scripts locally; Pillow composites its glyph mask.
    Native handles are released even if rendering fails.
    """
    import ctypes as c
    from ctypes import wintypes as w
    gdi, user = c.WinDLL('gdi32'), c.WinDLL('user32')
    class Header(c.Structure):
        _fields_ = [('size', w.DWORD), ('width', w.LONG), ('height', w.LONG), ('planes', w.WORD),
                    ('bits', w.WORD), ('compression', w.DWORD), ('image_size', w.DWORD),
                    ('xppm', w.LONG), ('yppm', w.LONG), ('used', w.DWORD), ('important', w.DWORD)]
    class Info(c.Structure):
        _fields_ = [('header', Header), ('colors', w.DWORD * 3)]
    gdi.CreateCompatibleDC.argtypes = [w.HDC]; gdi.CreateCompatibleDC.restype = w.HDC
    gdi.CreateDIBSection.argtypes = [w.HDC, c.POINTER(Info), w.UINT, c.POINTER(c.c_void_p), w.HANDLE, w.DWORD]
    gdi.CreateDIBSection.restype = w.HBITMAP
    gdi.CreateFontW.argtypes = [c.c_int] * 5 + [w.DWORD] * 8 + [w.LPCWSTR]
    gdi.CreateFontW.restype = w.HFONT
    gdi.SelectObject.argtypes = [w.HDC, w.HANDLE]; gdi.SelectObject.restype = w.HANDLE
    gdi.DeleteObject.argtypes = [w.HANDLE]; gdi.DeleteDC.argtypes = [w.HDC]
    gdi.SetTextColor.argtypes = [w.HDC, w.DWORD]; gdi.SetBkColor.argtypes = [w.HDC, w.DWORD]
    user.DrawTextW.argtypes = [w.HDC, w.LPCWSTR, c.c_int, c.POINTER(w.RECT), w.UINT]
    width, height = 1200, max(160, size * 3)
    info = Info(Header(c.sizeof(Header), width, -height, 1, 32, 0, width * height * 4, 0, 0, 0, 0))
    bits = c.c_void_p()
    dc = gdi.CreateCompatibleDC(None)
    bitmap = gdi.CreateDIBSection(dc, c.byref(info), 0, c.byref(bits), None, 0)
    face = gdi.CreateFontW(-size, 0, 0, 0, 700 if bold else 400, 0, 0, 0, 1, 0, 0, 4, 0, 'Tahoma')
    if not dc or not bitmap or not face:
        if face: gdi.DeleteObject(face)
        if bitmap: gdi.DeleteObject(bitmap)
        if dc: gdi.DeleteDC(dc)
        raise RuntimeError('Windows Thai text renderer unavailable')
    old_bitmap, old_font = gdi.SelectObject(dc, bitmap), gdi.SelectObject(dc, face)
    try:
        c.memset(bits, 0, width * height * 4)
        gdi.SetTextColor(dc, 0xFFFFFF)
        gdi.SetBkColor(dc, 0)
        rect = w.RECT(0, 0, width, height)
        if not user.DrawTextW(dc, message, -1, c.byref(rect), 0x20 | 0x800):
            raise RuntimeError('Unicode text rendering failed')
        gdi.GdiFlush()
        return Image.frombytes('RGB', (width, height), c.string_at(bits, width * height * 4), 'raw', 'BGRX').convert('L')
    finally:
        gdi.SelectObject(dc, old_font); gdi.SelectObject(dc, old_bitmap)
        gdi.DeleteObject(face); gdi.DeleteObject(bitmap); gdi.DeleteDC(dc)


def value_text(value):
    if value is None:
        return 'ยังประเมินไม่ได้'
    value = Decimal(str(value))
    if not value.is_finite():
        raise ValueError('finite display value required')
    return '฿' + format(value, ',.0f' if value == value.to_integral_value() else ',.2f')


def render_financial_fit(result, output, theme='light', demo=False, font_dir=None):
    """Render values from the existing engine. No budgets, ETA or ratios inferred."""
    p = PALETTES[theme]
    status = result.get('status')
    if status not in STATUSES:
        raise ValueError('unsupported financial status')
    color, label, recommendation = STATUSES[status]
    image = Image.new('RGB', (1200, 1400), p['bg'])
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((30, 30, 1170, 1370), radius=38, fill=p['card'])

    def text(x, y, message, size=30, bold=False, fill=None, max_width=1000):
        current = size
        while True:
            f = font(current, bold, font_dir)
            if d.textlength(message, font=f) <= max_width or current <= 20:
                break
            current -= 1
        if d.textlength(message, font=f) > max_width:
            raise ValueError('text exceeds card width')
        if features.check_feature('raqm'):
            d.text((x, y), message, font=f, fill=fill or p['text'], stroke_width=0)
        else:
            mask = windows_text_mask(message, current, bold)
            image.paste(fill or p['text'], (x, y, x + mask.width, y + mask.height), mask)

    text(86, 77, 'SHOPPING AGENT  /  FINANCIAL FIT', 26, fill=p['muted'])
    text(86, 126, 'ซื้อไหวไหม?', 54, True)
    badge = 'DEMO · ข้อมูลจำลอง' if demo else 'ผลคำนวณจากข้อมูลที่ยืนยัน'
    text(86, 202, badge, 26, fill=p['muted'])
    d.rounded_rectangle((86, 265, 1114, 376), radius=22, fill=p['panel'])
    d.ellipse((112, 301, 132, 321), fill=color)
    text(154, 285, status + '  ·  ' + label, 34, True, fill=p['text'], max_width=930)
    d.line((86, 418, 1114, 418), fill=p['line'], width=2)
    text(86, 449, 'ราคาสินค้า', 28, fill=p['muted'])
    progress = result.get('savings_progress')
    price = progress.get('goal') if progress else None
    text(86, 492, value_text(price), 92, True, max_width=1000)

    for box, title, number in [((86, 630, 585, 801), 'เงินเหลือตามแผน / เดือน', result.get('monthly_surplus')),
                                ((615, 630, 1114, 801), 'เงินที่จัดสรรซื้อแล้ว', progress.get('allocated') if progress else None)]:
        d.rounded_rectangle(box, radius=24, fill=p['panel'])
        text(box[0] + 25, 653, title, 27, fill=p['muted'], max_width=445)
        text(box[0] + 25, 704, value_text(number), 54, True, max_width=445)

    text(86, 844, 'ระยะเวลาเก็บเงินเพิ่ม', 28, fill=p['muted'])
    months = result.get('months')
    eta = 'ซื้อได้ตอนนี้' if months == 0 else ('ประมาณ ' + str(months) + ' เดือน' if months is not None else 'ยังประเมินไม่ได้')
    text(86, 886, eta, 51, True, fill=p['accent'])
    if progress:
        percent = Decimal(str(progress['percent']))
        if not percent.is_finite() or not 0 <= percent <= 100:
            raise ValueError('invalid engine progress')
        text(86, 975, 'ความคืบหน้าเงินซื้อสินค้า', 27, fill=p['muted'])
        text(963, 975, str(progress['percent']) + '%', 27, True, max_width=151)
        d.rounded_rectangle((86, 1027, 1114, 1047), radius=10, fill=p['track'])
        # Pixel scaling only; percentage is supplied by the engine.
        pixels = int(Decimal(1028) * percent / 100)
        if pixels:
            d.rounded_rectangle((86, 1027, 86 + pixels, 1047), radius=min(10, pixels // 2), fill=p['accent'])
    else:
        text(86, 975, 'ความคืบหน้า: ยังประเมินไม่ได้', 27, fill=p['muted'])
    d.line((86, 1090, 1114, 1090), fill=p['line'], width=2)
    text(86, 1120, 'คำแนะนำ', 28, True)
    text(86, 1167, recommendation, 30)
    text(86, 1231, 'สมมติให้เงินเหลือต่อเดือนและราคาคงเดิม ไม่แตะเงินสำรอง', 24, fill=p['muted'])
    text(86, 1277, 'ข้อมูลจำลอง ไม่ใช่ผลประเมินการเงินจริงของคุณ' if demo else 'ผลตามข้อมูล ณ วันที่ประเมิน ไม่ใช่การรับประกันอนาคต', 24, fill=p['muted'])
    output = Path(output)
    if output.suffix.lower() != '.png':
        raise ValueError('output must be PNG')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids overwriting a previous financial artifact.
    with output.open('xb') as stream:
        image.save(stream, format='PNG')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, help='Local engine JSON result')
    parser.add_argument('--output', required=True)
    parser.add_argument('--theme', choices=PALETTES, default='light')
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    result = json.loads(Path(args.input).read_text(encoding='utf-8-sig'))
    render_financial_fit(result, args.output, args.theme, args.demo)


if __name__ == '__main__':
    main()
