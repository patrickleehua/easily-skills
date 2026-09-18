"""管理与决策类组件：红黄绿状态、风险清单、行动项、决策记录。"""
import re

from . import component
from .base import badge, esc, fmt, inline, level, meta, number, objects, optional, status_badge, text

RAG = {'green': ('good', '按计划'), 'yellow': ('warn', '有风险'), 'red': ('risk', '已偏离'), 'grey': ('muted', '未开始')}
RAG_ALIASES = {'绿': 'green', '黄': 'yellow', '红': 'red', '灰': 'grey', 'gray': 'grey',
               'on_track': 'green', 'at_risk': 'yellow', 'off_track': 'red', 'not_started': 'grey'}
DECISIONS = {'approved': ('good', '已决定'), 'proposed': ('accent', '建议'), 'pending': ('warn', '待决策'), 'rejected': ('muted', '已否决')}
DECISION_ALIASES = {'已决定': 'approved', '已批准': 'approved', '建议': 'proposed', '待决策': 'pending', '待定': 'pending', '否决': 'rejected', '已否决': 'rejected'}
PRIORITY = re.compile(r'^P[0-3]$')
PRIORITY_TONES = {'P0': 'risk', 'P1': 'warn', 'P2': 'accent', 'P3': 'muted'}


def _mini_progress(value, field):
    pct = number(value, field, 0, 100)
    return '<div class="mini-progress"><span style="width:%.1f%%"></span></div><span class="mini-value">%s%%</span>' % (pct, fmt(pct))


@component('rag', group='管理与决策', summary='红黄绿状态板：每条工作线的健康度，必须附判据', aliases=('status-board',))
def _rag(block, ctx):
    criteria = block.get('criteria')
    if not isinstance(criteria, dict) or not criteria:
        raise ValueError('criteria 必填：写明绿 / 黄 / 红各自的判据，健康色不能没有依据')
    rows, used = [], set()
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 30)):
        field = 'items[%d]' % index
        key = RAG_ALIASES.get(item.get('status'), item.get('status'))
        if key not in RAG:
            raise ValueError('%s.status 必须是 green / yellow / red / grey（或 绿 / 黄 / 红 / 灰）' % field)
        used.add(key)
        tone_name, word = RAG[key]
        name = text(item.get('name'), field + '.name')
        summary = optional(item, 'summary', field + '.summary')
        progress = _mini_progress(item['progress'], field + '.progress') if 'progress' in item else ''
        rows.append('<li class="rag-row"><span class="rag-dot tone-%s" aria-hidden="true"></span><div class="rag-main">'
                    '<div class="rag-name"><b>%s</b>%s</div>%s%s</div><div class="rag-side">%s</div></li>'
                    % (tone_name, inline(name), badge(tone_name, word), '<p>%s</p>' % inline(summary) if summary else '',
                       meta(('负责人', optional(item, 'owner', field + '.owner')), ('截止', optional(item, 'due', field + '.due'))), progress))
    legend = []
    for key in ('green', 'yellow', 'red'):
        rule = criteria.get(key) or criteria.get({'green': '绿', 'yellow': '黄', 'red': '红'}[key])
        if key in used and not (isinstance(rule, str) and rule.strip()):
            raise ValueError('criteria.%s 缺失：已使用该状态就必须写判据' % key)
        if rule:
            tone_name, word = RAG[key]
            legend.append('<div><dt><span class="rag-dot tone-%s"></span>%s</dt><dd>%s</dd></div>' % (tone_name, word, inline(text(rule, 'criteria.' + key))))
    return '<ul class="rag">%s</ul><dl class="rag-criteria">%s</dl>' % (''.join(rows), ''.join(legend))


@component('risks', group='管理与决策', summary='风险清单：描述 + 等级 + 影响 + 应对 + 需要谁支持')
def _risks(block, ctx):
    rows = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 30)):
        field = 'items[%d]' % index
        _, tone_name, word = level(item.get('level', 'medium'), field + '.level')
        title = text(item.get('title'), field + '.title')
        chip = status_badge(item['status'], field + '.status') if item.get('status') else ''
        impact = optional(item, 'impact', field + '.impact')
        lines = ['<div><dt>影响</dt><dd>%s</dd></div>' % (inline(impact) if impact else '<span class="cell-empty">待补充</span>')]
        for key, label in (('mitigation', '应对'), ('support', '需要支持')):
            value = optional(item, key, '%s.%s' % (field, key))
            if value:
                lines.append('<div><dt>%s</dt><dd>%s</dd></div>' % (label, inline(value)))
        rows.append('<li class="risk risk-%s"><div class="risk-top">%s<b>%s</b>%s</div><dl>%s</dl>%s</li>'
                    % (tone_name, badge(tone_name, '风险·' + word), inline(title), chip, ''.join(lines),
                       meta(('负责人', optional(item, 'owner', field + '.owner')), ('截止', optional(item, 'due', field + '.due')))))
    return '<ul class="risk-list">%s</ul>' % ''.join(rows)


@component('actions', group='管理与决策', summary='行动项 / 下期计划：事项 + 负责人 + 截止 + 完成标准 + 状态', aliases=('next-steps', 'plan'))
def _actions(block, ctx):
    items = objects(block.get('items'), 'items', 1, 40)
    columns = [('priority', '优先级'), ('task', '事项'), ('owner', '负责人'), ('due', '截止'), ('acceptance', '完成标准'), ('status', '状态')]
    present = [(key, label) for key, label in columns if key == 'task' or any(item.get(key) for item in items)]
    rows = []
    for index, item in enumerate(items):
        field = 'items[%d]' % index
        text(item.get('task'), field + '.task')
        cells = []
        for key, _ in present:
            value = item.get(key)
            if not value:
                cells.append('<td><span class="cell-empty">—</span></td>')
            elif key == 'priority':
                if not (isinstance(value, str) and PRIORITY.match(value)):
                    raise ValueError('%s.priority 必须是 P0 / P1 / P2 / P3' % field)
                cells.append('<td>%s</td>' % badge(PRIORITY_TONES[value], value))
            elif key == 'status':
                cells.append('<td>%s</td>' % status_badge(value, field + '.status'))
            else:
                cells.append('<td%s>%s</td>' % (' class="nowrap"' if key in ('owner', 'due') else '', inline(text(value, '%s.%s' % (field, key)))))
        rows.append('<tr>%s</tr>' % ''.join(cells))
    head = ''.join('<th>%s</th>' % label for _, label in present)
    return '<div class="md-table-wrap"><table class="md-table actions-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, ''.join(rows))


@component('decisions', group='管理与决策', summary='决策记录：结论 + 理由 + 被否方案 + 状态，会议纪要与审查结论常用')
def _decisions(block, ctx):
    rows = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 30)):
        field = 'items[%d]' % index
        key = DECISION_ALIASES.get(item.get('status', 'proposed'), item.get('status', 'proposed'))
        if key not in DECISIONS:
            raise ValueError('%s.status 必须是 approved / proposed / pending / rejected（或中文别名）' % field)
        tone_name, word = DECISIONS[key]
        decision = text(item.get('decision'), field + '.decision')
        details = []
        for name, label in (('reason', '理由'), ('alternatives', '被否方案'), ('condition', '生效条件')):
            value = optional(item, name, '%s.%s' % (field, name))
            if value:
                details.append('<div><dt>%s</dt><dd>%s</dd></div>' % (label, inline(value)))
        rows.append('<li class="decision decision-%s"><div class="decision-top">%s<b>%s</b></div>%s%s</li>'
                    % (tone_name, badge(tone_name, word), inline(decision), '<dl>%s</dl>' % ''.join(details) if details else '',
                       meta(('决策人', optional(item, 'owner', field + '.owner')), ('日期', optional(item, 'date', field + '.date')))))
    return '<ol class="decision-list">%s</ol>' % ''.join(rows)
