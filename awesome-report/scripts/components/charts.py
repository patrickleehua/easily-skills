"""图表类组件：纯内联 SVG / HTML，无脚本、无外链、可离线打印。

  bar       横向条形   类别对比；带 x + series 时为分组条形（计划 vs 实际）
  column    纵向柱状   周期对比；带 x + series 时为分组柱状
  line      折线       指标走势，1–4 条序列
  donut     环图       构成占比，2–6 项
  stacked   堆叠条     单一总量的状态构成
  progress  进度组     多项任务完成度（0–100）
  funnel    漏斗       阶段转化，右侧为相对上一层的转化率
  gauge     完成度环   1–6 个整体完成度 / 达成率
  waterfall 瀑布图     期初 → 各项增减 → 期末，解释变化由什么构成
  heatmap   热力表     两个维度交叉的强度（模块 × 周、渠道 × 月）

所有图都必须写 source；渲染器只画给定的数，不推算、不补点、不画拟合线。
"""
import math

from . import component
from .base import clip, esc, fmt, number, objects, optional, text, tone

W = 520  # 画布宽度贴近报告栏宽，避免缩放后字号过小
PALETTE = ['var(--chart-%d)' % i for i in range(1, 7)]
SEMANTIC = {
    'accent': 'var(--chart-1)', 'info': 'var(--chart-2)', 'good': 'var(--chart-good)',
    'warn': 'var(--chart-warn)', 'risk': 'var(--chart-risk)', 'muted': 'var(--chart-muted)',
}


def _color(entry, index):
    value = entry.get('color')
    if value is None:
        return PALETTE[index % len(PALETTE)]
    if value not in SEMANTIC:
        raise ValueError('color 必须是 %s 之一' % ' / '.join(SEMANTIC))
    return SEMANTIC[value]


def _nice(value):
    """坐标轴上限抬到便于读数的刻度；只影响刻度，不改动任何数据点。"""
    if value <= 0:
        return 1.0
    scale = 10 ** math.floor(math.log10(value))
    for step in (1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if value <= step * scale:
            return step * scale
    return 10 * scale


def _points(spec, low=1, high=12):
    points = []
    for index, entry in enumerate(objects(spec.get('data'), 'data', low, high)):
        points.append({
            'label': text(entry.get('label'), 'data[%d].label' % index),
            'value': number(entry.get('value'), 'data[%d].value' % index),
            'note': optional(entry, 'note', 'data[%d].note' % index),
            'fill': _color(entry, index),
        })
    return points


def _series(spec, low_x=2, high_x=14, high_series=4):
    axis, series = spec.get('x'), spec.get('series')
    if not isinstance(axis, list) or not low_x <= len(axis) <= high_x or not all(isinstance(i, str) and i.strip() for i in axis):
        raise ValueError('x 必须是 %d–%d 个非空字符串' % (low_x, high_x))
    lines = []
    for index, entry in enumerate(objects(series, 'series', 1, high_series)):
        values = entry.get('points')
        if not isinstance(values, list) or len(values) != len(axis):
            raise ValueError('series[%d].points 长度必须与 x 一致' % index)
        lines.append({'name': text(entry.get('name'), 'series[%d].name' % index),
                      'values': [number(v, 'series[%d].points' % index) for v in values],
                      'fill': _color(entry, index)})
    return axis, lines


def _top(spec, values):
    return number(spec['max'], 'max', 0) if 'max' in spec else max(values + [0])


def _svg(height, summary, body, css='chart-svg'):
    return ('<svg class="%s" viewBox="0 0 %d %d" role="img" aria-label="%s" preserveAspectRatio="xMidYMin meet">%s</svg>'
            % (css, W, height, esc(summary), body))


def _swatch(x, y, fill, label):
    return ('<rect x="%.1f" y="%.1f" width="10" height="10" rx="2" fill="%s"></rect>'
            '<text class="c-legend" x="%.1f" y="%.1f">%s</text>' % (x, y, fill, x + 15, y + 9, esc(label)))


def _legend(lines, y, left=0):
    return ''.join(_swatch(left + (i % 3) * 170, y + (i // 3) * 22, line['fill'], clip(line['name'], 12)) for i, line in enumerate(lines))


def _label(spec, summary):
    return '%s：%s' % (spec.get('title', '图表'), summary)


def _unit(spec):
    return optional(spec, 'unit')


def _chart(name, summary):
    return component(name, group='图表', summary=summary, source=True, tag='figure', extra=' chart')


@_chart('bar', '横向条形：类别对比；x + series 时为分组条形（计划 vs 实际）')
def _bar(spec, ctx):
    unit = _unit(spec)
    label_w, gap, tail = 104, 10, 60
    track = W - label_w - gap - tail
    body = []
    if 'series' in spec:
        axis, lines = _series(spec, 1, 12, 3)
        top = _top(spec, [v for line in lines for v in line['values']])
        bar_h, row = 12, len(lines) * 15 + 16
        for g, label in enumerate(axis):
            y0 = g * row + 4
            body.append('<text class="c-label" x="%d" y="%.1f" text-anchor="end">%s</text>' % (label_w, y0 + row / 2 - 2, esc(clip(label, 9))))
            for s, line in enumerate(lines):
                value = line['values'][g]
                width = max(2.0, track * value / top) if top > 0 else 2.0
                y = y0 + s * 15
                body.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="2" fill="%s"></rect>' % (label_w + gap, y, width, bar_h, line['fill']))
                body.append('<text class="c-axis" x="%.1f" y="%.1f">%s</text>' % (label_w + gap + width + 5, y + 10, esc(fmt(value) + unit)))
        height = len(axis) * row + 8
        body.append(_legend(lines, height, label_w + gap))
        summary = '；'.join('%s：%s' % (line['name'], '、'.join('%s %s' % (a, fmt(v) + unit) for a, v in zip(axis, line['values']))) for line in lines)
        return _svg(height + 22 * ((len(lines) + 2) // 3) + 4, _label(spec, summary), ''.join(body))
    points = _points(spec)
    top = _top(spec, [p['value'] for p in points])
    row = 32
    for index, point in enumerate(points):
        y = index * row + 2
        width = max(2.0, track * point['value'] / top) if top > 0 else 2.0
        body.append('<text class="c-label" x="%d" y="%.1f" text-anchor="end">%s</text>' % (label_w, y + 20, esc(clip(point['label'], 9))))
        body.append('<rect x="%d" y="%.1f" width="%.1f" height="17" rx="3" fill="%s"></rect>' % (label_w + gap, y + 8, width, point['fill']))
        body.append('<text class="c-value" x="%.1f" y="%.1f">%s</text>' % (label_w + gap + width + 7, y + 20.5, esc(fmt(point['value']) + unit)))
    summary = '；'.join('%s %s%s' % (p['label'], fmt(p['value']), unit) for p in points)
    return _svg(len(points) * row + 6, _label(spec, summary), ''.join(body))


@_chart('column', '纵向柱状：周期对比；x + series 时为分组柱状')
def _column(spec, ctx):
    unit = _unit(spec)
    base_y, plot = 176, 136
    body = ['<line class="c-axis-line" x1="0" y1="%d" x2="%d" y2="%d"></line>' % (base_y, W, base_y)]
    if 'series' in spec:
        axis, lines = _series(spec, 1, 12, 4)
        top = _top(spec, [v for line in lines for v in line['values']])
        slot = W / len(axis)
        group = min(slot * 0.74, len(lines) * 30.0)
        bar_w = group / len(lines) - 3
        show = len(axis) * len(lines) <= 16
        for g, label in enumerate(axis):
            center = slot * (g + 0.5)
            for s, line in enumerate(lines):
                value = line['values'][g]
                height = max(2.0, plot * value / top) if top > 0 else 2.0
                x = center - group / 2 + s * (group / len(lines))
                body.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s"></rect>' % (x, base_y - height, bar_w, height, line['fill']))
                if show:
                    body.append('<text class="c-axis" x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (x + bar_w / 2, base_y - height - 5, esc(fmt(value))))
            body.append('<text class="c-label" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (center, base_y + 19, esc(clip(label, 6))))
        body.append(_legend(lines, base_y + 32))
        summary = '；'.join('%s：%s' % (line['name'], '、'.join('%s %s' % (a, fmt(v) + unit) for a, v in zip(axis, line['values']))) for line in lines)
        return _svg(base_y + 32 + 22 * ((len(lines) + 2) // 3), _label(spec, summary), ''.join(body))
    points = _points(spec)
    top = _top(spec, [p['value'] for p in points])
    slot = W / len(points)
    width = min(46.0, slot * 0.55)
    for index, point in enumerate(points):
        cx = slot * (index + 0.5)
        bar = max(2.0, plot * point['value'] / top) if top > 0 else 2.0
        body.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s"></rect>' % (cx - width / 2, base_y - bar, width, bar, point['fill']))
        body.append('<text class="c-value" x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (cx, base_y - bar - 6, esc(fmt(point['value']) + unit)))
        body.append('<text class="c-label" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (cx, base_y + 19, esc(clip(point['label'], 6))))
        if point['note']:
            body.append('<text class="c-axis" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (cx, base_y + 35, esc(clip(point['note'], 8))))
    height = base_y + (48 if any(p['note'] for p in points) else 30)
    summary = '；'.join('%s %s%s' % (p['label'], fmt(p['value']), unit) for p in points)
    return _svg(height, _label(spec, summary), ''.join(body))


@_chart('line', '折线：指标走势，1–4 条序列，坐标轴自动取整')
def _line(spec, ctx):
    axis, lines = _series(spec)
    unit = _unit(spec)
    flat = [v for line in lines for v in line['values']]
    top = number(spec['max'], 'max', 0) if 'max' in spec else _nice(max(flat + [0]))
    left, right, sky, floor = 40, W - 8, 16, 162
    body = []
    for step in range(3):
        ratio = step / 2
        y = floor - (floor - sky) * ratio
        body.append('<line class="c-grid" x1="%d" y1="%.1f" x2="%d" y2="%.1f"></line>' % (left, y, right, y))
        body.append('<text class="c-axis" x="%d" y="%.1f" text-anchor="end">%s</text>' % (left - 6, y + 4, esc(fmt(top * ratio))))
    span = (right - left) / max(1, len(axis) - 1)
    for index, label in enumerate(axis):
        body.append('<text class="c-label" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (left + span * index, floor + 20, esc(clip(label, 6))))
    for line in lines:
        coords = [(left + span * i, floor - (floor - sky) * (v / top if top > 0 else 0)) for i, v in enumerate(line['values'])]
        body.append('<polyline class="c-line" points="%s" stroke="%s"></polyline>' % (' '.join('%.1f,%.1f' % p for p in coords), line['fill']))
        body += ['<circle cx="%.1f" cy="%.1f" r="3" fill="%s"></circle>' % (x, y, line['fill']) for x, y in coords]
    height = floor + 28
    if len(lines) > 1:
        body.append(_legend(lines, floor + 34, left))
        height = floor + 40 + ((len(lines) + 2) // 3) * 22
    summary = '；'.join('%s：%s' % (line['name'], '、'.join(fmt(v) + unit for v in line['values'])) for line in lines)
    return _svg(height, _label(spec, summary), ''.join(body))


@_chart('donut', '环图：构成占比，2–6 项，中心显示合计')
def _donut(spec, ctx):
    points = _points(spec, 2, 6)
    total = sum(p['value'] for p in points)
    if total <= 0:
        raise ValueError('donut 的数值合计必须大于 0')
    unit = _unit(spec)
    cx, cy, radius, stroke = 92, 104, 62, 26
    circumference = 2 * math.pi * radius
    body = ['<circle cx="%d" cy="%d" r="%d" fill="none" stroke="var(--chart-track)" stroke-width="%d"></circle>' % (cx, cy, radius, stroke)]
    offset = 0.0
    for point in points:
        length = circumference * point['value'] / total
        dash = max(0.0, length - 1.5)
        body.append('<circle cx="%d" cy="%d" r="%d" fill="none" stroke="%s" stroke-width="%d" stroke-dasharray="%.2f %.2f" stroke-dashoffset="%.2f" transform="rotate(-90 %d %d)"></circle>'
                    % (cx, cy, radius, point['fill'], stroke, dash, circumference - dash, -offset, cx, cy))
        offset += length
    body.append('<text class="c-total" x="%d" y="%d" text-anchor="middle">%s</text>' % (cx, cy + 2, esc(fmt(total) + unit)))
    body.append('<text class="c-legend" x="%d" y="%d" text-anchor="middle">%s</text>' % (cx, cy + 22, esc(clip(optional(spec, 'center') or '合计', 8))))
    step = 34 if any(p['note'] for p in points) else 28
    start = max(20, cy - (len(points) - 1) * step / 2 - 14)
    for index, point in enumerate(points):
        y = start + index * step
        body.append(_swatch(196, y, point['fill'], clip(point['label'], 10)))
        body.append('<text class="c-value" x="%d" y="%.1f" text-anchor="end">%s · %s%%</text>'
                    % (W, y + 9, esc(fmt(point['value']) + unit), esc(fmt(round(point['value'] / total * 100, 1)))))
        if point['note']:
            body.append('<text class="c-axis" x="211" y="%.1f">%s</text>' % (y + 24, esc(clip(point['note'], 20))))
    summary = '共 %s%s；' % (fmt(total), unit) + '；'.join(
        '%s %s%s（%s%%）' % (p['label'], fmt(p['value']), unit, fmt(round(p['value'] / total * 100, 1))) for p in points)
    return _svg(max(cy + radius + 18, start + len(points) * step + 6), _label(spec, summary), ''.join(body))


@_chart('stacked', '堆叠条：单一总量的状态构成（完成 / 进行中 / 风险）')
def _stacked(spec, ctx):
    points = _points(spec, 2, 6)
    total = sum(p['value'] for p in points)
    if total <= 0:
        raise ValueError('stacked 的数值合计必须大于 0')
    unit = _unit(spec)
    body, x = [], 0.0
    for point in points:
        width = W * point['value'] / total
        body.append('<rect x="%.1f" y="6" width="%.1f" height="40" fill="%s"></rect>' % (x, max(0.0, width - 2), point['fill']))
        if width > 46:
            body.append('<text class="c-inbar" x="%.1f" y="31" text-anchor="middle">%s%%</text>' % (x + width / 2, esc(fmt(round(point['value'] / total * 100)))))
        x += width
    column_w = W / 2
    for index, point in enumerate(points):
        column, line = index % 2, index // 2
        y = 66 + line * 24
        body.append(_swatch(column * column_w, y, point['fill'], clip(point['label'], 10)))
        body.append('<text class="c-value" x="%.1f" y="%.1f" text-anchor="end">%s</text>' % (column * column_w + column_w - 26, y + 9, esc(fmt(point['value']) + unit)))
    summary = '合计 %s%s；' % (fmt(total), unit) + '；'.join('%s %s%s' % (p['label'], fmt(p['value']), unit) for p in points)
    return _svg(66 + math.ceil(len(points) / 2) * 24, _label(spec, summary), ''.join(body))


@_chart('progress', '进度组：多项任务完成度，value 为 0–100')
def _progress(spec, ctx):
    points = _points(spec)
    for point in points:
        if not 0 <= point['value'] <= 100:
            raise ValueError('progress 的 value 必须是 0–100')
    row = 60 if any(p['note'] for p in points) else 40
    body = []
    for index, point in enumerate(points):
        y = index * row
        body.append('<text class="c-label" x="0" y="%d">%s</text>' % (y + 13, esc(clip(point['label'], 22))))
        body.append('<text class="c-value" x="%d" y="%d" text-anchor="end">%s%%</text>' % (W, y + 13, esc(fmt(point['value']))))
        body.append('<rect x="0" y="%d" width="%d" height="8" rx="4" fill="var(--chart-track)"></rect>' % (y + 20, W))
        body.append('<rect x="0" y="%d" width="%.1f" height="8" rx="4" fill="%s"></rect>' % (y + 20, max(2.0, W * point['value'] / 100), point['fill']))
        if point['note']:
            body.append('<text class="c-axis" x="0" y="%d">%s</text>' % (y + 45, esc(clip(point['note'], 32))))
    summary = '；'.join('%s %s%%' % (p['label'], fmt(p['value'])) for p in points)
    return _svg(len(points) * row, _label(spec, summary), ''.join(body))


@_chart('funnel', '漏斗：阶段转化，右侧为相对上一层的转化率')
def _funnel(spec, ctx):
    points = _points(spec, 2, 7)
    top = max(p['value'] for p in points)
    if top <= 0:
        raise ValueError('funnel 的首层数值必须大于 0')
    unit = _unit(spec)
    stage, gap, left, full = 40, 10, 96, W - 96 - 44
    body = []
    for index, point in enumerate(points):
        y = index * (stage + gap)
        width = max(20.0, full * point['value'] / top)
        following = points[index + 1]['value'] if index + 1 < len(points) else point['value']
        width_next = max(20.0, full * following / top)
        x1, x2 = left + (full - width) / 2, left + (full + width) / 2
        x3, x4 = left + (full + width_next) / 2, left + (full - width_next) / 2
        body.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s"></polygon>' % (x1, y, x2, y, x3, y + stage, x4, y + stage, point['fill']))
        body.append('<text class="c-label" x="%d" y="%.1f" text-anchor="end">%s</text>' % (left - 10, y + 25, esc(clip(point['label'], 8))))
        body.append('<text class="c-inbar" x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (left + full / 2, y + 25, esc(fmt(point['value']) + unit)))
        if index:
            previous = points[index - 1]['value']
            rate = fmt(round(point['value'] / previous * 100, 1)) if previous else '0'
            body.append('<text class="c-axis" x="%d" y="%.1f" text-anchor="end">%s%%</text>' % (W, y + 25, esc(rate)))
    summary = '；'.join('%s %s%s' % (p['label'], fmt(p['value']), unit) for p in points)
    return _svg(len(points) * (stage + gap), _label(spec, summary), ''.join(body))


@_chart('gauge', '完成度环：1–6 个整体完成度或达成率（0–100）')
def _gauge(spec, ctx):
    rings = []
    radius = 50
    circumference = 2 * math.pi * radius
    for index, entry in enumerate(objects(spec.get('items'), 'items', 1, 6)):
        field = 'items[%d]' % index
        label = text(entry.get('label'), field + '.label')
        value = number(entry.get('value'), field + '.value', 0, 100)
        note = optional(entry, 'note', field + '.note')
        fill = _color(entry, 0)  # 未指定颜色时统一用主色，多环并列更易比较
        dash = circumference * value / 100
        svg = ('<svg class="gauge-svg" viewBox="0 0 128 128" role="img" aria-label="%s %s%%">'
               '<circle cx="64" cy="64" r="%d" fill="none" stroke="var(--chart-track)" stroke-width="12"></circle>'
               '<circle cx="64" cy="64" r="%d" fill="none" stroke="%s" stroke-width="12" stroke-linecap="round" '
               'stroke-dasharray="%.2f %.2f" transform="rotate(-90 64 64)"></circle>'
               '<text class="c-total" x="64" y="71" text-anchor="middle">%s%%</text></svg>'
               % (esc(label), fmt(value), radius, radius, fill, dash, circumference - dash, esc(fmt(value))))
        rings.append('<div class="gauge">%s<div class="gauge-label">%s</div>%s</div>'
                     % (svg, esc(label), '<div class="gauge-note">%s</div>' % esc(note) if note else ''))
    return '<div class="gauges">%s</div>' % ''.join(rings)


@_chart('waterfall', '瀑布图：期初 → 各项增减 → 期末，说明变化由什么构成')
def _waterfall(spec, ctx):
    unit = _unit(spec)
    start = spec.get('start')
    steps = _points(spec, 1, 10)
    bars = []  # (标签, 下沿, 上沿, 颜色, 显示值, 该柱之后的累计值)
    running = 0.0
    if start is not None:
        if not isinstance(start, dict):
            raise ValueError('start 必须是 {"label": "期初", "value": 数字}')
        running = number(start.get('value'), 'start.value')
        bars.append((text(start.get('label', '期初'), 'start.label'), 0.0, running, 'var(--chart-1)', fmt(running), running))
    for point in steps:
        low, high = sorted((running, running + point['value']))
        fill = point['fill'] if point['fill'] not in PALETTE else ('var(--chart-good)' if point['value'] >= 0 else 'var(--chart-risk)')
        running += point['value']
        bars.append((point['label'], low, high, fill, ('+' if point['value'] > 0 else '') + fmt(point['value']), running))
    bars.append((optional(spec, 'end_label') or '期末', 0.0, running, 'var(--chart-1)', fmt(running), running))
    lowest = min([0.0] + [b[1] for b in bars] + [b[2] for b in bars])
    highest = max([0.0] + [b[1] for b in bars] + [b[2] for b in bars])
    span = (highest - lowest) or 1.0
    sky, floor = 22, 176

    def y(value):
        return floor - (value - lowest) / span * (floor - sky)

    slot = W / len(bars)
    width = min(44.0, slot * 0.58)
    body = ['<line class="c-axis-line" x1="0" y1="%.1f" x2="%d" y2="%.1f"></line>' % (y(0), W, y(0))]
    for index, (label, low, high, fill, shown, after) in enumerate(bars):
        cx = slot * (index + 0.5)
        top_y, bottom_y = y(high), y(low)
        body.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2" fill="%s"></rect>' % (cx - width / 2, top_y, width, max(2.0, bottom_y - top_y), fill))
        body.append('<text class="c-value" x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (cx, top_y - 6, esc(shown + unit)))
        body.append('<text class="c-label" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (cx, floor + 19, esc(clip(label, 6))))
        if index + 1 < len(bars):  # 连接线：本柱结束时的累计值 → 下一柱的起点
            body.append('<line class="c-grid" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"></line>' % (cx + width / 2, y(after), cx + slot - width / 2, y(after)))
    summary = '；'.join('%s %s%s' % (bar[0], bar[4], unit) for bar in bars)
    return _svg(floor + 30, _label(spec, summary), ''.join(body))


@_chart('heatmap', '热力表：两个维度交叉的强度，颜色深浅对应数值')
def _heatmap(spec, ctx):
    columns, rows = spec.get('x'), spec.get('y')
    if not isinstance(columns, list) or not 1 <= len(columns) <= 16 or not all(isinstance(c, str) and c.strip() for c in columns):
        raise ValueError('x 必须是 1–16 个非空字符串（列）')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 20 or not all(isinstance(r, str) and r.strip() for r in rows):
        raise ValueError('y 必须是 1–20 个非空字符串（行）')
    values = spec.get('values')
    if not isinstance(values, list) or len(values) != len(rows) or not all(isinstance(r, list) and len(r) == len(columns) for r in values):
        raise ValueError('values 必须是 %d 行 × %d 列的二维数组' % (len(rows), len(columns)))
    flat = [number(v, 'values') for r in values for v in r if v is not None]
    top = number(spec['max'], 'max', 0) if 'max' in spec else max(flat + [0])
    tone_name = tone(spec.get('tone'), 'tone')
    unit = _unit(spec)
    head = '<th></th>' + ''.join('<th>%s</th>' % esc(c) for c in columns)
    body = []
    for label, row in zip(rows, values):
        cells = []
        for value in row:
            if value is None:
                cells.append('<td class="heat-cell is-empty">—</td>')
                continue
            alpha = 0.08 + 0.82 * (value / top if top > 0 else 0)
            dark = ' is-dark' if alpha > 0.55 else ''
            cells.append('<td class="heat-cell%s"><span class="heat-bg tone-%s" style="opacity:%.2f"></span><b>%s</b></td>'
                         % (dark, tone_name, alpha, esc(fmt(value))))
        body.append('<tr><th>%s</th>%s</tr>' % (esc(label), ''.join(cells)))
    legend = '颜色越深数值越大 · 最大值 %s%s' % (fmt(top), unit)
    return ('<div class="md-table-wrap heatmap-wrap"><table class="heatmap"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
            '<p class="legend">%s</p>' % (head, ''.join(body), esc(legend)))
