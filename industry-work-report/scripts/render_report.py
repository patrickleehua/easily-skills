#!/usr/bin/env python3
"""把 Markdown 或结构化 JSON 渲染成离线、自包含的单文件 HTML 报告（仅标准库）。

文档 = 报告头 + 首屏（结论 / 重点 / 指标 / 图表）+ 自由组件 + 章节。
每个章节由组件积木按顺序拼成，组件目录见 references/components.md。
"""
import argparse
import json
from pathlib import Path
import re
from string import Template
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import components  # noqa: E402
from components import BlockError, Context  # noqa: E402
from components.base import esc, inline  # noqa: E402
import mdlite  # noqa: E402

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'html'
THEMES = {'executive': '商务蓝', 'editorial': '暖白简报', 'briefing': '深色侧栏'}
LAYOUTS = ('cards', 'flow')
NUMBERING = ('auto', 'cn', 'none')
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')
NUMBERED = re.compile(r'^\s*([一二三四五六七八九十百]+[、.．]|第[一二三四五六七八九十百\d]+[章节部分]|\d+(\.\d+)*[、.．\s])')
CN_NUMBERS = '一二三四五六七八九十'
DOC_TEXT = ('subtitle', 'date', 'report_type', 'summary', 'footer', 'source_text', 'genre', 'industry', 'audience', 'author')


def _cn(index):
    if index <= 10:
        return CN_NUMBERS[index - 1]
    tens, ones = divmod(index, 10)
    return ('' if tens == 1 else CN_NUMBERS[tens - 1]) + '十' + (CN_NUMBERS[ones - 1] if ones else '')


def _root(data):
    """文档根字段校验；组件内容由组件自身校验。"""
    if not isinstance(data, dict):
        raise ValueError('JSON 根节点必须是对象')
    components.base.text(data.get('title'), 'title', True)
    for key in DOC_TEXT:
        if key in data:
            components.base.text(data[key], key, False)
    for key in ('demo', 'indent', 'toc'):
        if key in data and not isinstance(data[key], bool):
            raise ValueError('%s 必须是布尔值' % key)
    if 'layout' in data and data['layout'] not in LAYOUTS:
        raise ValueError('layout 必须是 %s 之一' % ' / '.join(LAYOUTS))
    if 'numbering' in data and data['numbering'] not in NUMBERING:
        raise ValueError('numbering 必须是 %s 之一' % ' / '.join(NUMBERING))
    for key in ('metrics', 'sections', 'highlights', 'charts', 'blocks'):
        if not isinstance(data.get(key, []), list):
            raise ValueError('%s 必须是数组' % key)
    brand = data.get('brand', {})
    if not isinstance(brand, dict):
        raise ValueError('brand 必须是对象，如 {"accent": "#1F6FEB"}')
    for key, value in brand.items():
        if key == 'palette':
            if not isinstance(value, list) or not 1 <= len(value) <= 6 or not all(isinstance(v, str) and HEX.match(v) for v in value):
                raise ValueError('brand.palette 必须是 1–6 个 #RRGGBB 颜色')
        elif key in ('accent', 'ink'):
            if not (isinstance(value, str) and HEX.match(value)):
                raise ValueError('brand.%s 必须是 #RRGGBB 颜色' % key)
        else:
            raise ValueError('brand 只支持 accent / ink / palette')
    for index, section in enumerate(data.get('sections', [])):
        field = 'sections[%d]' % index
        if not isinstance(section, dict):
            raise ValueError('%s 必须是对象' % field)
        components.base.text(section.get('title'), field + '.title', True)
        for key in ('summary', 'lead', 'body'):
            if key in section:
                components.base.text(section[key], '%s.%s' % (field, key), False)
        for key in ('items', 'charts', 'blocks'):
            if not isinstance(section.get(key, []), list):
                raise ValueError('%s.%s 必须是数组' % (field, key))
        if not any(key in section for key in ('items', 'body', 'charts', 'blocks')):
            raise ValueError('%s 至少要有 blocks / body / items / charts 之一' % field)


def _section_blocks(section):
    """章节内容统一转成组件序列：正文 → 自由组件 → 图表 → 事项（兼容旧字段）。"""
    blocks = []
    if section.get('body'):
        blocks.append({'type': 'markdown', 'text': section['body']})
    blocks += section.get('blocks', [])
    blocks += section.get('charts', [])
    if section.get('items'):
        blocks.append({'type': 'items', 'items': section['items']})
    return blocks


def _compose(data, base_dir=None):
    """渲染与主题无关的全部片段；任何组件错误都会带完整路径抛出。"""
    _root(data)
    root = Context('', base_dir)
    parts = {}
    parts['summary'] = components.render({'type': 'summary', 'text': data['summary']}, 'summary', base_dir) if data.get('summary') else ''
    parts['highlights'] = components.render({'type': 'highlights', 'items': data['highlights']}, 'highlights', base_dir) if data.get('highlights') else ''
    parts['metrics'] = components.render({'type': 'kpis', 'items': data['metrics']}, 'metrics', base_dir) if data.get('metrics') else ''
    charts = components.render_many(data.get('charts', []), root.child('charts'))
    parts['charts'] = '<section class="chart-board" aria-label="数据图表">%s</section>' % charts if charts else ''
    parts['blocks'] = components.render_many(data.get('blocks', []), root.child('blocks'))

    sections = data.get('sections', [])
    layout = data.get('layout') or ('flow' if any(s.get('body') or s.get('blocks') for s in sections) else 'cards')
    numbering = data.get('numbering', 'auto')
    anchored = data.get('toc', layout == 'flow' and len(sections) >= 3)
    rendered, links = [], []
    for index, section in enumerate(sections, 1):
        title = section['title']
        numbered = bool(NUMBERED.match(title))
        if numbering == 'cn' and not numbered:
            title, numbered = '%s、%s' % (_cn(index), title), True
        chip = '' if numbered or numbering == 'none' else '<span class="section-number">%02d</span>' % index
        anchor = ' id="sec-%d"' % index if anchored else ''
        head = '<div class="section-head">%s<h2%s>%s</h2></div>' % (chip, anchor, esc(title))
        body = []
        if section.get('summary'):
            body.append('<p class="section-summary">%s</p>' % inline(section['summary']))
        if section.get('lead'):
            body.append('<div class="md section-lead">%s</div>' % components.base.markdown(section['lead']))
        body.append(components.render_many(_section_blocks(section), root.child('sections[%d]' % (index - 1))))
        content = ''.join(body) or '<p class="empty">待补充</p>'
        rendered.append('<section class="section">%s%s</section>' % (head, content))
        links.append('<a href="#sec-%d">%s%s</a>' % (index, '' if numbered else '<span>%02d</span>' % index, esc(title)))
    parts['sections'] = ''.join(rendered)
    parts['toc'] = '<nav class="toc" aria-label="本页导航">%s</nav>' % ''.join(links) if anchored and links else ''
    parts['layout'] = layout
    return parts


def validate(data, base_dir=None):
    """完整校验（含全部组件）；通过则原样返回 data。"""
    try:
        _compose(data, base_dir)
    except BlockError as error:
        raise ValueError(str(error)) from None
    return data


def _brand_style(data, theme):
    brand = data.get('brand') or {}
    rules = []
    if brand.get('accent'):
        rules += ['--accent:%s' % brand['accent'], '--tone-accent:%s' % brand['accent'], '--chart-1:%s' % brand['accent']]
    if brand.get('ink'):
        rules.append('--ink:%s' % brand['ink'])
    for index, color in enumerate(brand.get('palette', []), 1):
        rules.append('--chart-%d:%s' % (index, color))
    return '\nbody.theme-%s{%s}' % (theme, ';'.join(rules)) if rules else ''


def _doc_meta(data):
    pairs = [('体裁', data.get('genre')), ('行业', data.get('industry')), ('对象', data.get('audience')), ('撰写', data.get('author'))]
    chips = ''.join('<span><b>%s</b>%s</span>' % (label, esc(value)) for label, value in pairs if value)
    return '<p class="doc-meta">%s</p>' % chips if chips else ''


def render(data, theme, base_dir=None):
    if theme not in THEMES:
        raise ValueError('未知模板：%s' % theme)
    try:
        parts = _compose(data, base_dir)
    except BlockError as error:
        raise ValueError(str(error)) from None
    styles = '\n'.join((ASSETS / name).read_text(encoding='utf-8') for name in ('base.css', 'components.css', '%s.css' % theme))
    classes = 'theme-%s layout-%s%s' % (theme, parts['layout'], ' indent-paragraphs' if data.get('indent') else '')
    values = {
        'title': esc(data['title']), 'styles': styles + _brand_style(data, theme), 'body_class': classes,
        'theme_name': THEMES[theme], 'eyebrow': esc(data.get('report_type') or data.get('genre') or '工作报告'),
        'subtitle': esc(data.get('subtitle', '')), 'doc_meta': _doc_meta(data),
        'date_block': '<div class="date-block"><span>报告日期 / PERIOD</span><strong>%s</strong></div>' % esc(data['date']) if data.get('date') else '',
        'demo_banner': '<div class="demo-banner">模板演示 · 以下为虚构示例，仅用于展示版式</div>' if data.get('demo') else '',
        'source': '<details class="source"><summary>查看原始报告全文</summary><pre>%s</pre></details>' % esc(data['source_text']) if data.get('source_text') else '',
        'footer': esc(data.get('footer', '工作报告')),
    }
    for key in ('summary', 'highlights', 'metrics', 'charts', 'blocks', 'toc', 'sections'):
        values[key] = parts[key]
    return Template((ASSETS / 'report.html').read_text(encoding='utf-8')).substitute(values)


def from_markdown(raw, filename):
    """按一、二级标题切分章节，每章保留完整 Markdown 正文（含组件代码块）。"""
    if not raw.strip():
        raise ValueError('Markdown 不能为空')
    data = {'title': filename, 'sections': [], 'source_text': raw, 'layout': 'flow'}
    lead, current, fence = [], None, None
    for line in raw.replace('\r\n', '\n').split('\n'):
        match = mdlite.FENCE.match(line)
        if match:
            marker, tail = match.group(2), match.group(3)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not tail.strip():
                fence = None
        if fence is None:
            heading = mdlite.HEADING.match(line)
            if heading and len(heading.group(1)) <= 2:
                title = heading.group(2)
                if len(heading.group(1)) == 1 and not data['sections'] and data['title'] == filename:
                    data['title'] = mdlite.plain(title)
                    continue
                current = {'title': mdlite.plain(title), 'lines': []}
                data['sections'].append(current)
                continue
        (lead if current is None else current['lines']).append(line)
    for section in data['sections']:
        body = '\n'.join(section.pop('lines')).strip('\n')
        section['body'] = body
        if not body:
            section['items'] = []
    head = '\n'.join(lead).strip('\n')
    if head:
        data['sections'].insert(0, {'title': '报告要点', 'body': head})
    return data


def gallery(entries=None):
    """预览入口页。entries：[(文件名, 标题, 说明)]；缺省为三套主题。"""
    if entries is None:
        entries = [('%s.html' % key, name, desc) for (key, name), desc in
                   zip(THEMES.items(), ('清晰分区 · 商务汇报', '暖白留白 · 正式归档', '深色侧栏 · 项目简报'))]
    buttons = ''.join('<button type="button" data-file="%s" aria-pressed="%s"><b>%02d / %s</b><span>%s</span></button>'
                      % (esc(file), str(i == 0).lower(), i + 1, esc(name), esc(desc)) for i, (file, name, desc) in enumerate(entries))
    links = ''.join('<a href="%s" download>下载 %s</a>' % (esc(file), esc(name)) for file, name, _ in entries)
    first = esc(entries[0][0])
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>工作报告 · 模板预览</title><style>
*{box-sizing:border-box}body{margin:0;background:#e9edf1;color:#21374d;font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}header{max-width:1280px;margin:auto;padding:26px 28px 16px}small{letter-spacing:.18em;color:#576d83}h1{font-size:24px;margin:6px 0}p{color:#586c80;margin:0}.choices{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:10px;margin:18px 0 14px}button{text-align:left;cursor:pointer;border:1px solid #bdcbd7;background:#f8fafc;color:#263e56;padding:11px 14px;border-radius:4px;font:inherit}button b,button span{display:block}button span{font-size:12px;margin-top:3px;color:#5d7184}button[aria-pressed=true]{border-color:#2e5f8b;box-shadow:inset 0 3px #2e5f8b;background:#fff}button:focus-visible,a:focus-visible{outline:3px solid #2e5f8b;outline-offset:3px}nav{display:flex;gap:16px;flex-wrap:wrap}a{color:#275c8d;text-underline-offset:4px}iframe{display:block;border:0;width:100%;height:calc(100vh - 260px);min-height:620px}noscript{display:block;padding:18px}@media(max-width:600px){header{padding:20px 16px}.choices{grid-template-columns:1fr 1fr}button{padding:9px;font-size:12px}button span{font-size:10px}iframe{min-height:700px}}
</style></head><body><header><small>REPORT TEMPLATE COLLECTION</small><h1>一套组件，覆盖各类报告。</h1><p>选择示例预览，打开独立页面即可打印或保存为 PDF。</p><div class="choices">''' + buttons + '''</div><nav><a id="open" href="''' + first + '''" target="_blank" rel="noopener">在新窗口打开</a>''' + links + '''</nav></header><iframe title="报告预览" src="''' + first + '''"></iframe><noscript>可通过上方链接打开各示例。</noscript><script>
document.querySelectorAll('[data-file]').forEach(button=>button.addEventListener('click',()=>{
document.querySelectorAll('[data-file]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
document.querySelector('iframe').src=button.dataset.file;document.getElementById('open').href=button.dataset.file;
}));</script></body></html>'''


def _load(path):
    raw = path.read_text(encoding='utf-8-sig')
    suffix = path.suffix.lower()
    if suffix == '.json':
        return json.loads(raw)
    if suffix in ('.md', '.markdown', '.txt'):
        return from_markdown(raw, path.stem)
    raise ValueError('输入格式须为 .md / .markdown / .txt / .json')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('input', type=Path, nargs='?', help='UTF-8 Markdown 或 JSON 报告')
    parser.add_argument('--theme', choices=THEMES, default='executive')
    parser.add_argument('--output', type=Path, help='单套 HTML 路径；--all 时为目录')
    parser.add_argument('--all', action='store_true', help='生成三套 HTML 与 index.html 预览入口')
    parser.add_argument('--force', action='store_true', help='允许覆盖已有输出')
    parser.add_argument('--check', action='store_true', help='只校验，不输出文件')
    parser.add_argument('--list-components', action='store_true', help='列出全部组件')
    args = parser.parse_args(argv)
    if args.list_components:
        for spec in components.catalog():
            print('%-6s %-12s %s%s' % (spec.group, spec.name, spec.summary, '（必须写 source）' if spec.source else ''))
        return 0
    if not args.input or not (args.output or args.check):
        parser.error('需要 input，以及 --output 或 --check')
    try:
        data = _load(args.input)
        base_dir = args.input.resolve().parent
        if args.check:
            validate(data, base_dir)
            print('校验通过：%s' % args.input)
            return 0
        if args.all:
            outputs = {args.output / ('%s.html' % theme): render(data, theme, base_dir) for theme in THEMES}
            outputs[args.output / 'index.html'] = gallery()
        else:
            if args.output.suffix.lower() != '.html':
                raise ValueError('单套输出必须使用 .html 扩展名')
            outputs = {args.output: render(data, args.theme, base_dir)}
        for path in outputs:
            if path.resolve() == args.input.resolve():
                raise ValueError('输出不可覆盖输入文件')
            if path.exists() and not args.force:
                raise ValueError('输出已存在：%s；请换路径或使用 --force' % path)
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            print(path.resolve())
        return 0
    except (ValueError, OSError) as error:
        print('转换失败：%s' % error, file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
