#!/usr/bin/env python3
"""Safe Markdown -> HTML for offline reports.

Stdlib only. Everything is escaped first and only a fixed set of marks is
re-applied, so user material can never inject HTML, scripts or external assets.
Supported: 标题 / 段落 / 有序无序嵌套列表 / 任务列表 / 表格 / 引用 / 提示框 /
代码块 / 分隔线 / 组件块，以及行内 **粗体**、*斜体*、行内代码、~~删除~~、==高亮==、链接。
"""
import html
import re

SAFE_URL = re.compile(r'^(?:https?://|mailto:|#)', re.I)
FENCE = re.compile(r'^(\s*)(`{3,}|~{3,})\s*([^`]*)$')
HEADING = re.compile(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$')
BULLET = re.compile(r'^(\s*)([-+*]|\d{1,9}[.)])\s+(.*)$')
RULE = re.compile(r'^\s{0,3}(?:-\s*-\s*-[-\s]*|\*\s*\*\s*\*[*\s]*|_\s*_\s*_[_\s]*)$')
QUOTE = re.compile(r'^\s{0,3}>\s?(.*)$')
DELIM = re.compile(r'^\s*\|?(\s*:?-{2,}:?\s*\|)+\s*:?-{2,}:?\s*\|?\s*$')
TASK = re.compile(r'^\[([ xX])\]\s+(.*)$')
ALERT = re.compile(r'^\[!([A-Za-z一-龥]{2,8})\]\s*(.*)$')

# GitHub 警告语法与中文别名，统一映射到报告的语气色
ALERTS = {
    'NOTE': ('info', '说明'), 'TIP': ('good', '建议'), 'IMPORTANT': ('accent', '重点'),
    'WARNING': ('warn', '注意'), 'CAUTION': ('risk', '风险'),
    '说明': ('info', '说明'), '建议': ('good', '建议'), '重点': ('accent', '重点'),
    '结论': ('accent', '结论'), '注意': ('warn', '注意'), '风险': ('risk', '风险'),
    '提醒': ('warn', '提醒'), '待办': ('info', '待办'),
}


def esc(value):
    return html.escape(str(value), quote=True)


def inline(text):
    """Render one line of inline Markdown; unsupported syntax degrades to plain text."""
    store = []

    def keep(rendered):
        store.append(rendered)
        return '\x00%d\x00' % (len(store) - 1)

    text = str(text).replace('\x00', '')
    text = re.sub(r'\\([\\`*_{}\[\]()#+\-.!~=|>])', lambda m: keep(esc(m.group(1))), text)
    text = re.sub(r'(`+)(.+?)\1', lambda m: keep('<code>' + esc(m.group(2).strip()) + '</code>'), text, flags=re.S)
    text = esc(text)
    text = re.sub(r'!\[([^\]]*)\]\([^)]*\)', lambda m: '［图：%s］' % m.group(1) if m.group(1).strip() else '［图］', text)

    def link(match):
        label, url = match.group(1), html.unescape(match.group(2)).strip()
        if not SAFE_URL.match(url):
            return label
        return '<a href="%s" rel="noopener noreferrer">%s</a>' % (esc(url), label)

    text = re.sub(r'\[([^\]]+)\]\((\S*?(?:\([^\s)]*\))?[^\s)]*)(?:\s+&quot;[^&]*&quot;)?\)', link, text)
    text = re.sub(r'\*\*(?=\S)(.+?)(?<=\S)\*\*', r'<strong>\1</strong>', text, flags=re.S)
    text = re.sub(r'__(?=\S)(.+?)(?<=\S)__', r'<strong>\1</strong>', text, flags=re.S)
    text = re.sub(r'~~(?=\S)(.+?)(?<=\S)~~', r'<del>\1</del>', text, flags=re.S)
    text = re.sub(r'==(?=\S)(.+?)(?<=\S)==', r'<mark>\1</mark>', text, flags=re.S)
    text = re.sub(r'(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])', r'<em>\1</em>', text)
    text = re.sub(r'(?<![\w_])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])', r'<em>\1</em>', text)
    return re.sub(r'\x00(\d+)\x00', lambda m: store[int(m.group(1))], text)


def plain(text):
    """Inline Markdown stripped to readable plain text (用于 aria-label 与摘要)。"""
    text = re.sub(r'`+([^`]*)`+', r'\1', str(text))
    text = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'(\*\*|__|~~|==|\*|_)', '', text)
    return text.strip()


def _indent(line):
    return len(line) - len(line.lstrip(' '))


def _dedent(lines, width):
    return [line if not line.strip() else line[width:] if not line[:width].strip() else line.lstrip(' ') for line in lines]


def _cells(line):
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|') and not line.endswith('\\|'):
        line = line[:-1]
    return [cell.strip().replace('\\|', '|') for cell in re.split(r'(?<!\\)\|', line)]


def _table(head, delim, body):
    aligns = []
    for cell in _cells(delim):
        left, right = cell.startswith(':'), cell.endswith(':')
        aligns.append('center' if left and right else 'right' if right else 'left' if left else '')

    def row(cells, tag):
        out = []
        for index, cell in enumerate(cells):
            align = aligns[index] if index < len(aligns) else ''
            style = ' style="text-align:%s"' % align if align else ''
            out.append('<%s%s>%s</%s>' % (tag, style, inline(cell), tag))
        return '<tr>' + ''.join(out) + '</tr>'

    rows = ''.join(row(_cells(line), 'td') for line in body)
    return ('<div class="md-table-wrap"><table class="md-table"><thead>%s</thead><tbody>%s</tbody></table></div>'
            % (row(_cells(head), 'th'), rows))


def _paragraph(lines):
    text = '<br>'.join(inline(line.strip().lstrip('　')) for line in lines if line.strip())
    return '<p>%s</p>' % text if text else ''


def _list(lines, handler, level):
    base = _indent(lines[0])
    ordered = BULLET.match(lines[0]).group(2)[-1] in '.)'
    items = []
    for line in lines:
        match = BULLET.match(line)
        if match and _indent(line) - base < 2:
            items.append({'width': len(match.group(1)) + len(match.group(2)) + 1, 'lines': [match.group(3)]})
        elif items:
            items[-1]['lines'].append(line)
    rendered = []
    for item in items:
        body = [item['lines'][0]] + _dedent(item['lines'][1:], item['width'])
        task, mark = TASK.match(body[0].strip()), ''
        if task:
            body[0] = task.group(2)
            state = 'is-done' if task.group(1).lower() == 'x' else 'is-open'
            mark = '<span class="md-task %s" aria-hidden="true"></span>' % state
        content = to_html('\n'.join(body), handler=handler, level=level + 1)
        single = re.fullmatch(r'<p>(.*)</p>', content, flags=re.S)
        rendered.append('<li>%s%s</li>' % (mark, single.group(1) if single else content))
    tag = 'ol' if ordered else 'ul'
    return '<%s class="md-list%s">%s</%s>' % (tag, ' md-ordered' if ordered else '', ''.join(rendered), tag)


def _quote(lines, handler, level):
    body = [QUOTE.match(line).group(1) if QUOTE.match(line) else line.strip() for line in lines]
    alert = ALERT.match(body[0].strip()) if body else None
    if alert:
        key = alert.group(1).upper() if alert.group(1).isascii() else alert.group(1)
        tone, label = ALERTS.get(key, ('info', alert.group(1)))
        inner = to_html('\n'.join([alert.group(2)] + body[1:]), handler=handler, level=level + 1)
        return ('<div class="callout callout-%s"><span class="callout-label">%s</span><div class="callout-body">%s</div></div>'
                % (tone, esc(label), inner))
    return '<blockquote class="md-quote">%s</blockquote>' % to_html('\n'.join(body), handler=handler, level=level + 1)


def _breaks(line):
    return bool(HEADING.match(line) or RULE.match(line) or FENCE.match(line) or QUOTE.match(line) or BULLET.match(line))


def to_html(raw, handler=None, level=0):
    """Convert Markdown to report HTML.

    `handler(lang, text)` may render a fenced block (e.g. a report component) and
    return HTML; returning None keeps the default code block.
    """
    lines = str(raw).replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out, index = [], 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        fence = FENCE.match(line)
        if fence:
            pad, marker, lang = fence.groups()
            body, index = [], index + 1
            while index < len(lines):
                close = FENCE.match(lines[index])
                if close and close.group(2)[0] == marker[0] and len(close.group(2)) >= len(marker) and not close.group(3).strip():
                    index += 1
                    break
                body.append(lines[index][len(pad):] if lines[index].startswith(pad) else lines[index])
                index += 1
            text = '\n'.join(body)
            rendered = handler(lang.strip(), text) if handler and lang.strip() else None
            if rendered is not None:
                out.append(rendered)
            else:
                attr = ' data-lang="%s"' % esc(lang.strip()) if lang.strip() else ''
                out.append('<pre class="md-code"%s><code>%s</code></pre>' % (attr, esc(text)))
            continue
        heading = HEADING.match(line)
        if heading:
            depth = min(6, max(3, len(heading.group(1)) + level))
            out.append('<h%d class="md-h">%s</h%d>' % (depth, inline(heading.group(2)), depth))
            index += 1
            continue
        if RULE.match(line):
            out.append('<hr class="md-rule">')
            index += 1
            continue
        if QUOTE.match(line):
            block = []
            while index < len(lines) and (QUOTE.match(lines[index]) or (block and lines[index].strip() and not _breaks(lines[index]))):
                block.append(lines[index])
                index += 1
            out.append(_quote(block, handler, level))
            continue
        if '|' in line and index + 1 < len(lines) and DELIM.match(lines[index + 1]):
            head, delim = line, lines[index + 1]
            index += 2
            body = []
            while index < len(lines) and lines[index].strip() and '|' in lines[index]:
                body.append(lines[index])
                index += 1
            out.append(_table(head, delim, body))
            continue
        if BULLET.match(line):
            block, base = [], _indent(line)
            ordered = BULLET.match(line).group(2)[-1] in '.)'
            while index < len(lines):
                current = lines[index]
                if not current.strip():
                    following = next((lines[j] for j in range(index + 1, len(lines)) if lines[j].strip()), '')
                    marker = BULLET.match(following) if following else None
                    if not following or (_indent(following) <= base and not marker):
                        break
                    # 空行后换了标记类型（有序 ↔ 无序）即另起一个列表
                    if marker and _indent(following) <= base and (marker.group(2)[-1] in '.)') != ordered:
                        break
                    block.append(current)
                    index += 1
                    continue
                if _indent(current) <= base and _breaks(current) and not BULLET.match(current):
                    break
                block.append(current)
                index += 1
            out.append(_list(block, handler, level))
            continue
        block = []
        while index < len(lines) and lines[index].strip():
            current = lines[index]
            if _breaks(current):
                break
            if '|' in current and index + 1 < len(lines) and DELIM.match(lines[index + 1]):
                break
            block.append(current)
            index += 1
        paragraph = _paragraph(block)
        if paragraph:
            out.append(paragraph)
    return ''.join(out)
