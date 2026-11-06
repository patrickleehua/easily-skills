"""指标与数据类组件：指标卡、目标达成、数据表、证据台账、事项列表。"""
from . import component
from .base import (badge, esc, fmt, inline, level, markdown, number, objects, optional,
                   plain, status_badge, text, tone)

EVIDENCE_KINDS = {
    'observed': ('good', '已核查事实'), 'inferred': ('info', '推断'),
    'proposed': ('accent', '建议'), 'unknown': ('muted', '待确认'),
}
CELL_KINDS = ('text', 'number', 'status', 'progress', 'tag', 'level', 'markdown')


def _value(value, field):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return fmt(number(value, field))
    return text(value, field)


@component('kpis', group='指标与数据', summary='指标卡：关键数字 + 单位 + 口径 + 变化 + 来源', aliases=('metrics',))
def _kpis(block, ctx):
    shared = block.get('source')
    cards = []
    for index, metric in enumerate(objects(block.get('items'), 'items', 1, 8)):
        field = 'items[%d]' % index
        label = text(metric.get('label'), field + '.label')
        value = _value(metric.get('value'), field + '.value')
        source = optional(metric, 'source', field + '.source')
        if not source.strip() and not shared:
            raise ValueError('%s.source 缺失：指标必须写来源（或在组件上统一写 source）' % field)
        tone_name = tone(metric.get('tone'), field + '.tone')
        unit, note = optional(metric, 'unit', field + '.unit'), optional(metric, 'note', field + '.note')
        delta, target = optional(metric, 'delta', field + '.delta'), optional(metric, 'target', field + '.target')
        parts = ['<article class="metric metric-tone-%s"><div class="metric-label">%s</div>' % (tone_name, esc(label)),
                 '<div class="metric-value">%s<span class="metric-unit">%s</span></div>' % (esc(value), esc(unit))]
        if delta:
            parts.append('<div class="metric-delta metric-%s">%s</div>' % (tone_name, esc(delta)))
        if target:
            parts.append('<div class="metric-target">%s</div>' % esc(target))
        if note:
            parts.append('<div class="metric-note">%s</div>' % esc(note))
        if source and source != shared:
            parts.append('<div class="evidence">来源：%s</div>' % esc(source))
        cards.append(''.join(parts) + '</article>')
    return '<div class="metrics">%s</div>' % ''.join(cards)


@component('scorecard', group='指标与数据', summary='目标达成表：目标值 / 实际值 / 达成率 / 判据，适合 KPI、OKR、经营指标', source=True)
def _scorecard(block, ctx):
    thresholds = block.get('thresholds', {'good': 100, 'warn': 90})
    if not isinstance(thresholds, dict):
        raise ValueError('thresholds 必须是 {"good": 100, "warn": 90} 形式')
    good = number(thresholds.get('good', 100), 'thresholds.good', 0)
    warn = number(thresholds.get('warn', 90), 'thresholds.warn', 0, good)
    rows = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 30)):
        field = 'items[%d]' % index
        label = text(item.get('label'), field + '.label')
        target = number(item.get('target'), field + '.target')
        actual = number(item.get('actual'), field + '.actual')
        lower = item.get('lower_is_better', False)
        if not isinstance(lower, bool):
            raise ValueError('%s.lower_is_better 必须是布尔值' % field)
        unit, note = optional(item, 'unit', field + '.unit'), optional(item, 'note', field + '.note')
        if lower:
            rate = (target / actual * 100) if actual else None
        else:
            rate = (actual / target * 100) if target else None
        if rate is None:
            verdict, tone_name, rate_text, width = '无法计算', 'muted', '—', 0
        else:
            tone_name = 'good' if rate >= good else 'warn' if rate >= warn else 'risk'
            verdict = {'good': '达成', 'warn': '接近', 'risk': '未达'}[tone_name]
            rate_text, width = '%s%%' % fmt(round(rate, 1)), min(rate, 120) / 120 * 100
        bar = ('<div class="bullet" aria-hidden="true"><span class="bullet-fill tone-%s" style="width:%.1f%%"></span>'
               '<span class="bullet-target" style="left:%.1f%%"></span></div>' % (tone_name, width, 100 / 120 * 100))
        rows.append('<tr><td><b>%s</b>%s</td><td class="num">%s%s</td><td class="num">%s%s</td><td class="num">%s</td><td>%s</td><td>%s</td></tr>'
                    % (esc(label), '<div class="cell-note">%s</div>' % inline(note) if note else '',
                       fmt(target), esc(unit), fmt(actual), esc(unit), rate_text, bar, badge(tone_name, verdict)))
    legend = '判据：达成率 ≥%s%% 为达成 · %s%%–%s%% 为接近 · <%s%% 为未达%s' % (
        fmt(good), fmt(warn), fmt(good), fmt(warn), '（该项越低越好时按 目标÷实际 计算）' if any(i.get('lower_is_better') for i in block['items']) else '')
    return ('<div class="md-table-wrap"><table class="md-table scorecard"><thead><tr><th>指标</th><th class="num">目标</th>'
            '<th class="num">实际</th><th class="num">达成率</th><th>对照</th><th>判定</th></tr></thead><tbody>%s</tbody></table></div>'
            '<p class="legend">%s</p>' % (''.join(rows), esc(legend)))


def _columns(block):
    columns = []
    for index, column in enumerate(block.get('columns') or []):
        if isinstance(column, str):
            column = {'key': column, 'label': column}
        if not isinstance(column, dict):
            raise ValueError('columns[%d] 必须是字符串或对象' % index)
        label = text(column.get('label', column.get('key')), 'columns[%d].label' % index)
        kind = column.get('kind', 'text')
        if kind not in CELL_KINDS:
            raise ValueError('columns[%d].kind 必须是 %s 之一' % (index, ' / '.join(CELL_KINDS)))
        align = column.get('align', 'right' if kind == 'number' else '')
        if align not in ('', 'left', 'center', 'right'):
            raise ValueError('columns[%d].align 必须是 left / center / right' % index)
        columns.append({'key': column.get('key', label), 'label': label, 'kind': kind, 'align': align})
    if not columns:
        raise ValueError('columns 至少一列')
    return columns


def _cell(value, kind, field):
    if value is None or value == '':
        return '<span class="cell-empty">—</span>'
    if kind == 'number':
        return esc(_value(value, field))
    if kind == 'status':
        return status_badge(value, field)
    if kind == 'level':
        _, tone_name, word = level(value, field)
        return badge(tone_name, word)
    if kind == 'progress':
        pct = number(value, field, 0, 100)
        return ('<div class="mini-progress"><span style="width:%.1f%%"></span></div><span class="mini-value">%s%%</span>'
                % (pct, fmt(pct)))
    if kind == 'tag':
        tags = value if isinstance(value, list) else [value]
        return ''.join('<span class="tag">%s</span>' % esc(text(tag, field)) for tag in tags)
    if kind == 'markdown':
        return markdown(text(value, field))
    return inline(_value(value, field))


@component('table', group='指标与数据', summary='数据表：列可声明 number / status / progress / tag / level 类型，行可着色')
def _table(block, ctx):
    columns = _columns(block)
    head = ''.join('<th%s>%s</th>' % (' class="num"' if column['kind'] == 'number' else '', esc(column['label'])) for column in columns)
    rows = []
    for row_index, row in enumerate(block.get('rows') or []):
        field = 'rows[%d]' % row_index
        if isinstance(row, list):
            if len(row) != len(columns):
                raise ValueError('%s 的单元格数必须等于列数 %d' % (field, len(columns)))
            values, row_tone = row, None
        elif isinstance(row, dict):
            values = [row.get(column['key']) for column in columns]
            row_tone = tone(row['_tone'], field + '._tone') if row.get('_tone') else None
        else:
            raise ValueError('%s 必须是数组或对象' % field)
        cells = []
        for column, value in zip(columns, values):
            style = ' style="text-align:%s"' % column['align'] if column['align'] else ''
            classes = ' class="num"' if column['kind'] == 'number' else ''
            cells.append('<td%s%s>%s</td>' % (classes, style, _cell(value, column['kind'], '%s.%s' % (field, column['key']))))
        rows.append('<tr%s>%s</tr>' % (' class="row-%s"' % row_tone if row_tone else '', ''.join(cells)))
    if not rows:
        raise ValueError('rows 至少一行')
    caption = optional(block, 'caption')
    compact = ' is-compact' if block.get('compact') else ''
    return ('<div class="md-table-wrap"><table class="md-table data-table%s">%s<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>'
            % (compact, '<caption>%s</caption>' % inline(caption) if caption else '', head, ''.join(rows)))


@component('evidence', group='指标与数据', summary='证据台账：来源 → 证明了什么 → 边界 → 事实/推断/建议/未知')
def _evidence(block, ctx):
    rows = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 40)):
        field = 'items[%d]' % index
        kind = item.get('kind', 'observed')
        if kind not in EVIDENCE_KINDS:
            raise ValueError('%s.kind 必须是 %s 之一' % (field, ' / '.join(EVIDENCE_KINDS)))
        tone_name, word = EVIDENCE_KINDS[kind]
        rows.append('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            inline(text(item.get('source'), field + '.source')), inline(text(item.get('proves'), field + '.proves')),
            inline(optional(item, 'boundary', field + '.boundary')) or '<span class="cell-empty">—</span>', badge(tone_name, word)))
    return ('<div class="md-table-wrap"><table class="md-table"><thead><tr><th>证据来源</th><th>证明了什么</th><th>边界 / 不能证明</th>'
            '<th>性质</th></tr></thead><tbody>%s</tbody></table></div>' % ''.join(rows))


@component('items', group='管理与决策', summary='事项列表：标题 + 说明 + 状态 + 标签 + 进度 + 影响/支持', aliases=('tasks',))
def _items(block, ctx):
    rows = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 60)):
        field = 'items[%d]' % index
        title = text(item.get('title'), field + '.title')
        chip = status_badge(item['status'], field + '.status') if item.get('status') else ''
        classes = 'item is-highlight' if item.get('highlight') is True else 'item'
        if 'highlight' in item and not isinstance(item['highlight'], bool):
            raise ValueError('%s.highlight 必须是布尔值' % field)
        parts = ['<li class="%s"><div class="item-top"><span class="item-title">%s</span>%s</div>' % (classes, inline(title), chip)]
        tags = item.get('tags', [])
        if not isinstance(tags, list):
            raise ValueError('%s.tags 必须是数组' % field)
        if tags:
            parts.append('<div class="tags">%s</div>' % ''.join('<span class="tag">%s</span>' % esc(text(tag, field + '.tags[]')) for tag in tags))
        if item.get('detail'):
            parts.append('<div class="item-body">%s</div>' % markdown(text(item['detail'], field + '.detail')))
        for key, label in (('impact', '影响'), ('support', '需要支持')):
            if item.get(key):
                parts.append('<p class="risk-detail"><b>%s：</b>%s</p>' % (label, inline(text(item[key], '%s.%s' % (field, key)))))
        source = optional(item, 'source', field + '.source')
        if 'progress' in item:
            value = number(item['progress'], field + '.progress', 0, 100)
            if not source.strip():
                raise ValueError('%s 含 progress 时必须写 source' % field)
            shown = fmt(value)
            parts.append('<div class="progress-wrap"><div class="progress-caption"><span>已报告进度</span><span>%s%%</span></div>'
                         '<progress max="100" value="%s" aria-label="%s：%s%%">%s%%</progress></div>'
                         % (shown, shown, esc(plain(title)), shown, shown))
        if source:
            parts.append('<p class="evidence">来源：%s</p>' % esc(source))
        rows.append(''.join(parts) + '</li>')
    return '<ul class="section-items">%s</ul>' % ''.join(rows)
