"""进度与流程类组件：时间线、甘特图、步骤条、看板。纯 HTML/CSS，窄屏自动换成竖排。"""
import datetime

from . import component
from .base import badge, date, esc, fmt, inline, number, objects, optional, status, text, tone


@component('timeline', group='进度与流程', summary='时间线 / 里程碑：日期 + 事件 + 状态，竖排或横排')
def _timeline(block, ctx):
    layout = block.get('layout', 'vertical')
    if layout not in ('vertical', 'horizontal'):
        raise ValueError('layout 必须是 vertical / horizontal')
    rows = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 30)):
        field = 'items[%d]' % index
        when = text(item.get('date'), field + '.date')
        title = text(item.get('title'), field + '.title')
        desc = optional(item, 'desc', field + '.desc')
        tone_name, chip = 'accent', ''
        if item.get('status'):
            _, tone_name, word = status(item['status'], field + '.status')
            chip = badge(tone_name, word)
        rows.append('<li class="tl tl-%s"><span class="tl-dot" aria-hidden="true"></span><div class="tl-date">%s</div>'
                    '<div class="tl-title"><b>%s</b>%s</div>%s</li>'
                    % (tone_name, esc(when), inline(title), chip, '<p>%s</p>' % inline(desc) if desc else ''))
    return '<ol class="timeline timeline-%s">%s</ol>' % (layout, ''.join(rows))


def _ticks(start, days):
    """按跨度选刻度：两周内按天，一个月内隔天，四个月内按周一，更长按月初。"""
    ticks = []
    if days <= 14:
        step = [start + datetime.timedelta(n) for n in range(days)]
    elif days <= 31:
        step = [start + datetime.timedelta(n) for n in range(0, days, 3)]
    elif days <= 124:
        first = start + datetime.timedelta((7 - start.weekday()) % 7)
        step = [first + datetime.timedelta(n) for n in range(0, days, 7) if (first - start).days + n < days]
    else:
        step, cursor = [], datetime.date(start.year, start.month, 1)
        while (cursor - start).days < days:
            if cursor >= start:
                step.append(cursor)
            cursor = datetime.date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    for day in step:
        label = '%d月' % day.month if days > 124 else '%d/%d' % (day.month, day.day)
        ticks.append((day, label))
    return ticks


@component('gantt', group='进度与流程', summary='甘特图：计划区间 vs 实际区间 + 进度 + 里程碑 + 今天线')
def _gantt(block, ctx):
    items = objects(block.get('items'), 'items', 1, 40)
    parsed, every = [], []
    for index, item in enumerate(items):
        field = 'items[%d]' % index
        task = text(item.get('task'), field + '.task')
        start = date(item.get('start'), field + '.start')
        milestone = item.get('milestone', False)
        if not isinstance(milestone, bool):
            raise ValueError('%s.milestone 必须是布尔值' % field)
        end = date(item['end'], field + '.end') if item.get('end') else start
        if not milestone and not item.get('end'):
            raise ValueError('%s.end 必填（里程碑可省略，需写 "milestone": true）' % field)
        if end < start:
            raise ValueError('%s 的 end 早于 start' % field)
        actual = None
        if item.get('actual_start'):
            a_start = date(item['actual_start'], field + '.actual_start')
            a_end = date(item['actual_end'], field + '.actual_end') if item.get('actual_end') else a_start
            if a_end < a_start:
                raise ValueError('%s 的 actual_end 早于 actual_start' % field)
            actual = (a_start, a_end)
            every += [a_start, a_end]
        progress = number(item['progress'], field + '.progress', 0, 100) if 'progress' in item else None
        tone_name = status(item['status'], field + '.status')[1] if item.get('status') else 'accent'
        parsed.append({'task': task, 'start': start, 'end': end, 'actual': actual, 'progress': progress, 'tone': tone_name,
                       'milestone': milestone, 'group': optional(item, 'group', field + '.group'),
                       'owner': optional(item, 'owner', field + '.owner')})
        every += [start, end]
    first = date(block['start'], 'start') if block.get('start') else min(every)
    last = date(block['end'], 'end') if block.get('end') else max(every)
    if last < first:
        raise ValueError('end 早于 start')
    days = (last - first).days + 1
    if days > 800:
        raise ValueError('时间跨度超过 800 天，请拆分或按季度汇总')

    def left(day):
        return max(0.0, min(100.0, (day - first).days / days * 100))

    def width(a, b):
        return max(0.6, min(100.0, ((b - a).days + 1) / days * 100))

    today = ''
    if block.get('today'):
        now = date(block['today'], 'today')
        if first <= now <= last:
            today = '<span class="gantt-today" style="left:%.2f%%" title="今天 %s"></span>' % (left(now) + 50 / days, now.isoformat())
    scale = ''.join('<span style="left:%.2f%%">%s</span>' % (left(day), esc(label)) for day, label in _ticks(first, days))
    rows, group = [], None
    for item in parsed:
        if item['group'] and item['group'] != group:
            group = item['group']
            rows.append('<div class="gantt-group">%s</div>' % esc(group))
        span = item['start'].isoformat()[5:] if item['milestone'] else '%s → %s' % (item['start'].isoformat()[5:], item['end'].isoformat()[5:])
        label = '<div class="gantt-label"><b>%s</b><small>%s%s</small></div>' % (
            inline(item['task']), esc(span), ' · ' + esc(item['owner']) if item['owner'] else '')
        if item['milestone']:
            bars = '<span class="gantt-milestone tone-%s" style="left:%.2f%%" title="%s"></span>' % (item['tone'], left(item['start']) + 50 / days, esc(item['start'].isoformat()))
        else:
            fill = '<i style="width:%.1f%%"></i>' % item['progress'] if item['progress'] is not None else ''
            bars = '<span class="gantt-bar tone-%s%s" style="left:%.2f%%;width:%.2f%%">%s</span>' % (
                item['tone'], ' has-actual' if item['actual'] else '', left(item['start']), width(item['start'], item['end']), fill)
            if item['actual']:
                bars += '<span class="gantt-actual tone-%s" style="left:%.2f%%;width:%.2f%%"></span>' % (
                    item['tone'], left(item['actual'][0]), width(*item['actual']))
        pct = '<span class="gantt-pct">%s%%</span>' % fmt(item['progress']) if item['progress'] is not None else ''
        rows.append('<div class="gantt-row">%s<div class="gantt-track">%s%s%s</div></div>' % (label, bars, today, pct))
    legend = ['<span><i class="lg-plan"></i>计划</span>']
    if any(item['actual'] for item in parsed):
        legend.append('<span><i class="lg-actual"></i>实际</span>')
    if any(item['progress'] is not None for item in parsed):
        legend.append('<span><i class="lg-progress"></i>已完成比例</span>')
    if any(item['milestone'] for item in parsed):
        legend.append('<span><i class="lg-milestone"></i>里程碑</span>')
    if today:
        legend.append('<span><i class="lg-today"></i>今天</span>')
    return ('<div class="gantt"><div class="gantt-head"><div class="gantt-label">%s — %s</div><div class="gantt-scale">%s</div></div>%s</div>'
            '<p class="legend gantt-legend">%s</p>' % (first.isoformat(), last.isoformat(), scale, ''.join(rows), ''.join(legend)))


@component('steps', group='进度与流程', summary='步骤条 / 流程：阶段顺序 + 每步状态，适合流程、阶段门、审批链')
def _steps(block, ctx):
    rows = []
    for index, item in enumerate(objects(block.get('items'), 'items', 2, 10)):
        field = 'items[%d]' % index
        title = text(item.get('title'), field + '.title')
        desc = optional(item, 'desc', field + '.desc')
        tone_name, chip = 'muted', ''
        if item.get('status'):
            _, tone_name, word = status(item['status'], field + '.status')
            chip = badge(tone_name, word)
        rows.append('<li class="step step-%s"><span class="step-no">%d</span><div class="step-body"><b>%s</b>%s%s</div></li>'
                    % (tone_name, index + 1, inline(title), chip, '<p>%s</p>' % inline(desc) if desc else ''))
    return '<ol class="steps">%s</ol>' % ''.join(rows)


@component('kanban', group='进度与流程', summary='看板：按状态分列的任务卡片，适合迭代、工单、项目池')
def _kanban(block, ctx):
    columns = objects(block.get('columns'), 'columns', 2, 6)
    out = []
    for c_index, column in enumerate(columns):
        field = 'columns[%d]' % c_index
        title = text(column.get('title'), field + '.title')
        tone_name = tone(column.get('tone'), field + '.tone', 'muted')
        cards = column.get('cards', [])
        if not isinstance(cards, list) or len(cards) > 40:
            raise ValueError('%s.cards 必须是最多 40 项的数组' % field)
        rendered = []
        for k_index, card in enumerate(cards):
            c_field = '%s.cards[%d]' % (field, k_index)
            if isinstance(card, str):
                card = {'title': card}
            if not isinstance(card, dict):
                raise ValueError('%s 必须是字符串或对象' % c_field)
            tags = card.get('tags', [])
            if not isinstance(tags, list):
                raise ValueError('%s.tags 必须是数组' % c_field)
            info = optional(card, 'meta', c_field + '.meta')
            rendered.append('<li class="kb-card">%s%s%s</li>' % (
                inline(text(card.get('title'), c_field + '.title')), '<div class="kb-meta">%s</div>' % inline(info) if info else '',
                '<div class="tags">%s</div>' % ''.join('<span class="tag">%s</span>' % esc(text(tag, c_field + '.tags[]')) for tag in tags) if tags else ''))
        body = '<ul>%s</ul>' % ''.join(rendered) if rendered else '<p class="kb-empty">暂无</p>'
        out.append('<section class="kb-col kb-%s"><header><b>%s</b><span class="kb-count">%d</span></header>%s</section>'
                   % (tone_name, esc(title), len(rendered), body))
    return '<div class="kanban" style="--cols:%d">%s</div>' % (len(columns), ''.join(out))
