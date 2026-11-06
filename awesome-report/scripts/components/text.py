"""结论与强调类组件：核心结论、重点色块、提示框、正文、术语表、检查清单。"""
from . import component
from .base import (TONE_LABELS, esc, inline, markdown, objects, optional, text, tone)

CHECK_STATES = {'done': ('good', '已完成'), 'open': ('muted', '未完成'), 'blocked': ('risk', '受阻'), 'na': ('muted', '不适用')}


@component('summary', group='结论与强调', summary='首屏核心结论条，一至两句话回答“结果是什么”')
def _summary(block, ctx):
    label = optional(block, 'label') or '核心结论'
    body = markdown(text(block.get('text'), 'text'))
    return '<div class="summary"><span class="summary-label">%s</span><div class="summary-body">%s</div></div>' % (esc(label), body)


@component('highlights', group='结论与强调', summary='2–4 条语气色块：进展 / 阻塞 / 下一步 / 决策')
def _highlights(block, ctx):
    cards = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 6)):
        body = inline(text(item.get('text'), 'items[%d].text' % index))
        label = optional(item, 'label', 'items[%d].label' % index)
        tone_name = tone(item.get('tone'), 'items[%d].tone' % index)
        head = '<span class="highlight-label">%s</span>' % esc(label) if label else ''
        cards.append('<article class="highlight highlight-%s">%s<p>%s</p></article>' % (tone_name, head, body))
    return '<div class="highlights">%s</div>' % ''.join(cards)


@component('callout', group='结论与强调', summary='跳出正文的提示框：风险、决策建议、口径说明', aliases=('alert',))
def _callout(block, ctx):
    tone_name = tone(block.get('tone'), default='info')
    label = optional(block, 'label') or TONE_LABELS[tone_name]
    body = markdown(text(block.get('text'), 'text'))
    return ('<div class="callout callout-%s"><span class="callout-label">%s</span><div class="callout-body">%s</div></div>'
            % (tone_name, esc(label), body))


@component('markdown', group='结论与强调', summary='富文本正文：段落、表格、列表、代码、行内高亮', aliases=('md', 'text'))
def _markdown(block, ctx):
    return '<div class="md">%s</div>' % markdown(text(block.get('text'), 'text'))


@component('glossary', group='结论与强调', summary='术语表：首次出现的专有名词、缩写、内部代号')
def _glossary(block, ctx):
    rows = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 40)):
        term = text(item.get('term'), 'items[%d].term' % index)
        desc = text(item.get('desc'), 'items[%d].desc' % index)
        rows.append('<div><dt>%s</dt><dd>%s</dd></div>' % (inline(term), inline(desc)))
    return '<dl class="glossary">%s</dl>' % ''.join(rows)


@component('checklist', group='结论与强调', summary='检查清单：验收项、上线检查、合规核对，逐项给状态')
def _checklist(block, ctx):
    rows, done = [], 0
    items = objects(block.get('items'), 'items', 1, 60)
    for index, item in enumerate(items):
        label = text(item.get('text'), 'items[%d].text' % index)
        state = item.get('state', 'open')
        if state not in CHECK_STATES:
            raise ValueError('items[%d].state 必须是 %s 之一' % (index, ' / '.join(CHECK_STATES)))
        done += state == 'done'
        tone_name, word = CHECK_STATES[state]
        note = optional(item, 'note', 'items[%d].note' % index)
        rows.append('<li class="check check-%s"><span class="check-box" aria-hidden="true"></span>'
                    '<span class="check-text">%s%s</span><span class="badge badge-%s">%s</span></li>'
                    % (state, inline(label), '<em>%s</em>' % inline(note) if note else '', tone_name, word))
    counted = [item for item in items if item.get('state', 'open') != 'na']
    tally = '<p class="check-tally">已完成 %d / %d 项</p>' % (done, len(counted)) if counted else ''
    return '<ul class="checklist">%s</ul>%s' % (''.join(rows), tally)
