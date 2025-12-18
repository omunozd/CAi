from xml.etree import ElementTree as ET
from typing import Optional
import shutil, os, re
from mysite.utils import printt

def add_bar_animations(
        svg_path: str,
        dur: float = 2.5,
        delay_step: float = 0.06) -> Optional[str]:
    """Add height + y SMIL animations to bars in the SVG.

    Args:
        svg_path: Path to the SVG file to modify.
        dur: Animation duration in seconds.
        delay_step: Stagger delay step between bars in seconds.

    Returns:
        Backup file path on success.
    """

    if not os.path.exists(svg_path):
        raise FileNotFoundError(f"No se pudo encontrar el SVG: {svg_path}")

    printt('Target path:', svg_path)
    ET.register_namespace('', "http://www.w3.org/2000/svg")

    # Parse
    tree = ET.parse(svg_path)

    ET.register_namespace('', "http://www.w3.org/2000/svg")
    tree = ET.parse(svg_path)
    root = tree.getroot()
    ns = '{' + 'http://www.w3.org/2000/svg' + '}'

    # find rects with class containing 'bar' (handles 'bar bar-0' etc.)
    rects = [r for r in root.findall(
        './/' + ns + 'rect') if r.get('class') and 'bar' in r.get('class').split()]

    # fallback: auto-detect likely bar rects (e.g. narrow bars in the visualizer)
    if not rects:
        candidates = [r for r in root.findall('.//' + ns + 'rect') if r.get('width') and r.get('height')]
        rects = []
        for r in candidates:
            try:
                w = float(r.get('width'))
                h = float(r.get('height'))
            except Exception:
                continue
            # skip large background rects or decorative full-width rects
            if w > 50 or h > 200:
                continue
            rects.append(r)
        printt(f"Auto-detected {len(rects)} bar rects (no 'bar' class present)")

    # ensure a <style> element exists to hold per-bar keyframes
    style_el = root.find(ns + 'style')
    if style_el is None:
        style_el = ET.Element(ns + 'style')
        root.insert(0, style_el)

    # collect generated CSS rules
    css_rules = []

    for i, r in enumerate(rects):
        try:
            h = float(r.get('height'))
            y = float(r.get('y'))
        except Exception:
            continue

        style = r.get('style') or ''
        # parse animation-delay if present
        if 'animation-delay' in style:
            try:
                delay = float(style.split('animation-delay:')[1].split('s')[0])
            except Exception:
                delay = round(i * delay_step, 2)
        else:
            delay = round(i * delay_step, 2)

        # compute values (centered y adjustments so scaling appears vertically centered)
        # use the same amplitudes as the general wiggle but per-rect in px for translate
        scale25 = 1.04
        scale50 = 0.98
        scale75 = 1.02
        h25 = round(h * scale25, 3)
        h50 = round(h * scale50, 3)
        h75 = round(h * scale75, 3)
        # compute absolute translate offsets and signs so we don't emit double minus signs
        t25 = round(abs(h25 - h) / 2, 3)
        t50 = round(abs(h50 - h) / 2, 3)
        t75 = round(abs(h75 - h) / 2, 3)
        s25 = '-' if h25 > h else ''
        s50 = '-' if h50 > h else ''
        s75 = '-' if h75 > h else ''

        # remove existing SMIL height/y animate children if present (we'll use CSS animations)
        for child in list(r):
            if child.tag == ns + 'animate' and child.get('attributeName') in ('height', 'y'):
                r.remove(child)

        # add classes for scoping: generic `bar` plus per-rect `bar-{i}`
        existing_class = r.get('class') or ''
        classes = existing_class.split() if existing_class else []
        if 'bar' not in classes:
            classes.append('bar')
        bar_class = f'bar-{i}'
        if bar_class not in classes:
            classes.append(bar_class)
        r.set('class', ' '.join(classes))

        # set inline animation properties (use CSS keyframes we'll create)
        r_style = (r.get('style') or '').strip().rstrip(';')
        # remove any existing animation-* declarations
        # (quick approach: append our settings; inline styles override class)
        inline = (
            f"animation-name:wiggle-{i};animation-duration:{dur}s;"
            f"animation-timing-function:ease-in-out;animation-iteration-count:infinite;"
            f"animation-delay:{delay}s;animation-direction:alternate;animation-fill-mode:both;"
        )
        r.set('style', (r_style + ';' if r_style else '') + inline)

        # create CSS keyframes for this bar (translate Y in opposite direction)
        keyframes = (
            f"@keyframes wiggle-{i} {{\n"
            f"  0% {{ transform: translateY(0px) scaleY(1); }}\n"
            f" 25% {{ transform: translateY({s25}{t25}px) scaleY({scale25}); }}\n"
            f" 50% {{ transform: translateY({s50}{t50}px) scaleY({scale50}); }}\n"
            f" 75% {{ transform: translateY({s75}{t75}px) scaleY({scale75}); }}\n"
            f" 100% {{ transform: translateY(0px) scaleY(1); }}\n"
            f"}}"
        )
        css_rules.append(keyframes)

    # append generated rules to style element text
    existing_css = style_el.text or ''
    # remove previously generated per-bar keyframes to avoid duplication and stale values
    # keep base CSS (anything up through the generic @keyframes wiggle block)
    m = re.search(r'@keyframes\s+wiggle\s*\{', existing_css, flags=re.S)
    if m:
        # find matching closing brace by counting braces
        start = m.start()
        i = m.end() - 1
        depth = 1
        while i < len(existing_css) - 1 and depth > 0:
            i += 1
            if existing_css[i] == '{':
                depth += 1
            elif existing_css[i] == '}':
                depth -= 1
        end = i + 1 if depth == 0 else m.end()
        base_css = existing_css[:end]
    else:
        base_css = existing_css

    # write clean base CSS and append per-bar keyframes
    base_css = (
        ".bar { transform-box: fill-box; transform-origin: center center; will-change: transform; }\n"
        "@keyframes wiggle { 0% { transform: scaleY(1); } 25% { transform: scaleY(1.04); } 50% { transform: scaleY(0.98); } 75% { transform: scaleY(1.02); } 100% { transform: scaleY(1); } }\n"
    )
    style_el.text = base_css + ('\n'.join(css_rules) + '\n' if css_rules else '')

    # write backup and write file
    bak_path = svg_path + '.bak'
    shutil.copy(svg_path, bak_path)
    printt(f"Backup file creado en {bak_path}")

    tree.write(svg_path, encoding='utf-8', xml_declaration=True)
    printt(f"SVG animado creado en {svg_path}")

    return bak_path


if __name__ == '__main__':
    # default behavior for backwards compatibility
    default_svg = os.path.join(
        'Cancion_del_dia','spotify_codes', 'QFMC_cancionDelDia_15_12_25.svg')
    
    import sys

    path = os.path.join(sys.argv[1]) if len(sys.argv) > 1 else default_svg
    bak = add_bar_animations(path)
