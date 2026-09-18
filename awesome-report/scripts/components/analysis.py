"""分析框架类组件：方案对比、四象限、风险矩阵、鱼骨图、金字塔、卡片网格（SWOT / KISS / 4Ls）。"""
from . import component
from .base import badge, clip, esc, inline, listing, markdown, number, objects, optional, text, tone

FISH_W = 760


@component('comparison', group='分析框架', summary='方案对比矩阵：选项 × 维度，标出推荐项与结论，适合技术选型、方案评审', aliases=('matrix',))
def _comparison(block, ctx):
    options = []
    for index, option in enumerate(listing(block.get('options'), 'options', 2, 6)):
        if isinstance(option, str):
            option = {'name': option}
        if not isinstance(option, dict):
            raise ValueError('options[%d] 必须是字符串或对象' % index)
        pick = option.get('recommended', False)
        if not isinstance(pick, bool):
            raise ValueError('options[%d].recommended 必须是布尔值' % index)
        options.append({'name': text(option.get('name'), 'options[%d].name' % index), 'pick': pick,
                        'tag': optional(option, 'tag', 'options[%d].tag' % index)})
    head = ['<th>对比维度</th>']
    for option in options:
        chips = (badge('good', '推荐') if option['pick'] else '') + ('<span class="tag">%s</span>' % esc(option['tag']) if option['tag'] else '')
        head.append('<th%s>%s%s</th>' % (' class="is-pick"' if option['pick'] else '', esc(option['name']), chips))
    rows = []
    for c_index, criterion in enumerate(objects(block.get('criteria'), 'criteria', 1, 24)):
        field = 'criteria[%d]' % c_index
        label = text(criterion.get('label'), field + '.label')
        weight = optional(criterion, 'weight', field + '.weight')
        values = criterion.get('values')
        if not isinstance(values, list) or len(values) != len(options):
            raise ValueError('%s.values 必须与 options 数量一致（%d 个）' % (field, len(options)))
        cells = ['<th scope="row">%s%s</th>' % (inline(label), '<small>%s</small>' % esc(weight) if weight else '')]
        for o_index, value in enumerate(values):
            cell_tone = None
            if isinstance(value, dict):
                cell_tone = tone(value.get('tone'), '%s.values[%d].tone' % (field, o_index), None)
                value = value.get('text')
            classes = [name for name, on in (('is-pick', options[o_index]['pick']), ('cell-%s' % cell_tone, cell_tone)) if on]
            cells.append('<td%s>%s</td>' % (' class="%s"' % ' '.join(classes) if classes else '', inline(text(value, '%s.values[%d]' % (field, o_index)))))
        rows.append('<tr>%s</tr>' % ''.join(cells))
    verdict = optional(block, 'verdict')
    tail = ('<div class="callout callout-accent"><span class="callout-label">结论</span><div class="callout-body">%s</div></div>'
            % markdown(verdict)) if verdict else ''
    return ('<div class="md-table-wrap"><table class="md-table compare-table"><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>%s'
            % (''.join(head), ''.join(rows), tail))


def _axis(block, key):
    axis = block.get(key)
    if not isinstance(axis, dict):
        raise ValueError('%s 必须是 {"label": "...", "low": "...", "high": "..."}' % key)
    return (text(axis.get('label'), key + '.label'), optional(axis, 'low', key + '.low'), optional(axis, 'high', key + '.high'))


@component('quadrant', group='分析框架', summary='四象限：两个维度定位事项，如重要-紧急、价值-成本、影响-投入')
def _quadrant(block, ctx):
    x_label, x_low, x_high = _axis(block, 'x')
    y_label, y_low, y_high = _axis(block, 'y')
    names = block.get('quadrants', {})
    if not isinstance(names, dict):
        raise ValueError('quadrants 必须是 {"tr": "...", "tl": "...", "bl": "...", "br": "..."}')
    cells = ''.join('<div class="q-cell q-%s"><span>%s</span></div>' % (key, esc(optional(names, key, 'quadrants.' + key)))
                    for key in ('tl', 'tr', 'bl', 'br'))
    dots, legend = [], []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 24)):
        field = 'items[%d]' % index
        label = text(item.get('label'), field + '.label')
        x = number(item.get('x'), field + '.x', 0, 10)
        y = number(item.get('y'), field + '.y', 0, 10)
        tone_name = tone(item.get('tone'), field + '.tone')
        dots.append('<span class="q-dot tone-%s" style="left:%.1f%%;bottom:%.1f%%" title="%s"><i>%d</i></span>'
                    % (tone_name, x * 10, y * 10, esc(label), index + 1))
        legend.append('<li><i class="tone-%s">%d</i>%s</li>' % (tone_name, index + 1, inline(label)))
    axis = ('<div class="q-yaxis"><span>%s</span><b>%s ↑</b><span>%s</span></div>' % (esc(y_high), esc(y_label), esc(y_low)),
            '<div class="q-xaxis"><span>%s</span><b>%s →</b><span>%s</span></div>' % (esc(x_low), esc(x_label), esc(x_high)))
    return ('<div class="quadrant">%s<div class="q-plane">%s%s</div>%s</div><ol class="q-legend">%s</ol>'
            % (axis[0], cells, ''.join(dots), axis[1], ''.join(legend)))


@component('risk-matrix', group='分析框架', summary='风险矩阵：可能性 × 影响热力格，风险按编号落格')
def _risk_matrix(block, ctx):
    scale = block.get('scale', 5)
    if scale not in (3, 5):
        raise ValueError('scale 必须是 3 或 5')
    words = {3: ['低', '中', '高'], 5: ['很低', '低', '中', '高', '很高']}[scale]
    grid = {}
    legend = []
    for index, item in enumerate(objects(block.get('items'), 'items', 1, 30)):
        field = 'items[%d]' % index
        label = text(item.get('label'), field + '.label')
        chance = int(number(item.get('likelihood'), field + '.likelihood', 1, scale))
        impact = int(number(item.get('impact'), field + '.impact', 1, scale))
        grid.setdefault((chance, impact), []).append(index + 1)
        tone_name = _score_tone(chance * impact, scale)
        legend.append('<li><i class="tone-%s">%d</i>%s<small>可能性 %s · 影响 %s</small></li>'
                      % (tone_name, index + 1, inline(label), words[chance - 1], words[impact - 1]))
    rows = []
    for impact in range(scale, 0, -1):
        cells = ['<th scope="row">%s</th>' % words[impact - 1]]
        for chance in range(1, scale + 1):
            tone_name = _score_tone(chance * impact, scale)
            marks = ''.join('<i>%d</i>' % n for n in grid.get((chance, impact), []))
            cells.append('<td class="rm-cell rm-%s">%s</td>' % (tone_name, marks))
        rows.append('<tr>%s</tr>' % ''.join(cells))
    foot = '<tr><th></th>%s</tr>' % ''.join('<th>%s</th>' % word for word in words)
    return ('<div class="risk-matrix"><div class="rm-ylabel">影响程度</div><table class="rm-grid"><tbody>%s</tbody><tfoot>%s</tfoot></table>'
            '<div class="rm-xlabel">可能性 →</div></div><ol class="q-legend">%s</ol>' % (''.join(rows), foot, ''.join(legend)))


def _score_tone(score, scale):
    high, mid = (10, 5) if scale == 5 else (6, 3)
    return 'risk' if score >= high else 'warn' if score >= mid else 'good'


@component('fishbone', group='分析框架', summary='鱼骨图：结果 ← 4–6 类原因，适合根因分析、质量问题、事故复盘', tag='figure')
def _fishbone(block, ctx):
    effect = text(block.get('effect'), 'effect')
    categories = objects(block.get('categories'), 'categories', 2, 6)
    parsed, total = [], 0
    for index, category in enumerate(categories):
        field = 'categories[%d]' % index
        causes = [text(c, '%s.causes[]' % field) for c in listing(category.get('causes'), field + '.causes', 1, 5)]
        total += len(causes)
        parsed.append((text(category.get('name'), field + '.name'), causes))
    if total > 24:
        raise ValueError('原因总数超过 24 条，请合并同类原因')
    deepest = max(len(causes) for _, causes in parsed)
    bone = 44 + deepest * 26
    height = bone * 2 + 56
    spine_y, head_x, tail_x = height / 2, FISH_W - 150, 18
    cols = (len(parsed) + 1) // 2
    spacing = (head_x - tail_x - 20) / cols
    body = ['<line class="fb-spine" x1="%d" y1="%.1f" x2="%d" y2="%.1f"></line>' % (tail_x, spine_y, head_x, spine_y),
            '<rect class="fb-head" x="%d" y="%.1f" width="142" height="60" rx="6"></rect>' % (head_x, spine_y - 30)]
    lines = [effect[i:i + 8] for i in range(0, min(len(effect), 24), 8)]
    for n, line in enumerate(lines):
        body.append('<text class="fb-effect" x="%d" y="%.1f" text-anchor="middle">%s</text>'
                    % (head_x + 71, spine_y + 5 + (n - (len(lines) - 1) / 2) * 17, esc(line + ('…' if n == 2 and len(effect) > 24 else ''))))
    for index, (name, causes) in enumerate(parsed):
        up = index % 2 == 0
        joint_x = tail_x + 20 + (index // 2 + 1) * spacing
        end_x, end_y = joint_x - bone * 0.55, spine_y + (-bone if up else bone)
        body.append('<line class="fb-bone" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"></line>' % (joint_x, spine_y, end_x, end_y))
        body.append('<text class="fb-cat" x="%.1f" y="%.1f" text-anchor="middle">%s</text>' % (end_x, end_y + (-10 if up else 20), esc(clip(name, 10))))
        for k, cause in enumerate(causes):
            t = (k + 1) / (len(causes) + 1)
            px, py = end_x + (joint_x - end_x) * t, end_y + (spine_y - end_y) * t
            # 文字放在骨线“让开”的一侧：上骨写在小骨下方，下骨写在小骨上方，避免与斜骨相交
            text_y = py + 15 if up else py - 5
            body.append('<line class="fb-rib" x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"></line>' % (px - 100, py, px, py))
            body.append('<text class="fb-cause" x="%.1f" y="%.1f" text-anchor="end"><title>%s</title>%s</text>' % (px - 6, text_y, esc(cause), esc(clip(cause, 11))))
    summary = '%s：%s' % (effect, '；'.join('%s（%s）' % (name, '、'.join(causes)) for name, causes in parsed))
    text_list = ''.join('<li><b>%s</b>：%s</li>' % (esc(name), '；'.join(inline(c) for c in causes)) for name, causes in parsed)
    return ('<svg class="diagram-svg" viewBox="0 0 %d %d" role="img" aria-label="%s">%s</svg>'
            '<details class="alt-text"><summary>文字版</summary><ul>%s</ul></details>'
            % (FISH_W, height, esc(summary), ''.join(body), text_list))


@component('pyramid', group='分析框架', summary='金字塔：结论 → 论据 → 事实的层级，或目标 → 策略 → 动作')
def _pyramid(block, ctx):
    levels = objects(block.get('levels'), 'levels', 2, 6)
    rows = []
    for index, item in enumerate(levels):
        field = 'levels[%d]' % index
        width = 38 + 62 * index / (len(levels) - 1)
        tone_name = tone(item.get('tone'), field + '.tone')
        desc = optional(item, 'desc', field + '.desc')
        rows.append('<li><div class="py-shape"><span class="py-bar tone-%s" style="width:%.1f%%">%s</span></div><div class="py-desc">%s</div></li>'
                    % (tone_name, width, inline(text(item.get('title'), field + '.title')), inline(desc) if desc else ''))
    return '<ol class="pyramid">%s</ol>' % ''.join(rows)


@component('grid', group='分析框架', summary='卡片网格：SWOT、KISS（保持/改进/开始/停止）、4Ls、优劣对照等并列框架', aliases=('swot', 'cards'))
def _grid(block, ctx):
    cells = objects(block.get('cells'), 'cells', 2, 9)
    columns = block.get('columns', 2 if len(cells) in (2, 4) else 3)
    if columns not in (1, 2, 3, 4):
        raise ValueError('columns 必须是 1–4')
    out = []
    for index, cell in enumerate(cells):
        field = 'cells[%d]' % index
        tone_name = tone(cell.get('tone'), field + '.tone', 'muted')
        title = text(cell.get('title'), field + '.title')
        if 'items' in cell:
            body = '<ul>%s</ul>' % ''.join('<li>%s</li>' % inline(text(v, field + '.items[]')) for v in listing(cell['items'], field + '.items', 0, 20))
        else:
            body = markdown(text(cell.get('text'), field + '.text（或 items）'))
        out.append('<section class="gc gc-%s"><h4>%s</h4>%s</section>' % (tone_name, inline(title), body))
    return '<div class="grid-cards" style="--cols:%d">%s</div>' % (columns, ''.join(out))
