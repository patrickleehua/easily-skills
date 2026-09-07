#!/usr/bin/env python3
"""Render Markdown or structured JSON into offline, self-contained reports (stdlib only)."""
import argparse
import html
import json
import math
from pathlib import Path
import re
from string import Template
import sys

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'html'
THEMES = {'executive': '商务蓝', 'editorial': '暖白简报', 'briefing': '深色侧栏'}
STATUS = {'done': '已完成', 'active': '进行中', 'risk': '需协调', 'planned': '计划'}


def esc(value):
    return html.escape(str(value), quote=True)


def require_text(value, field, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f'{field} 必须是{ "非空" if required else "" }字符串')


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('JSON 根节点必须是对象')
    require_text(data.get('title'), 'title', True)
    for key in ('subtitle', 'date', 'report_type', 'summary', 'footer', 'source_text'):
        if key in data:
            require_text(data[key], key)
    if 'demo' in data and not isinstance(data['demo'], bool):
        raise ValueError('demo 必须是布尔值')
    for key in ('metrics', 'sections'):
        if not isinstance(data.get(key, []), list):
            raise ValueError(f'{key} 必须是数组')
    for metric in data.get('metrics', []):
        if not isinstance(metric, dict):
            raise ValueError('metric 必须是对象')
        for key in ('label', 'value', 'source'):
            require_text(metric.get(key), f'metric.{key}', True)
        for key in ('unit', 'note'):
            if key in metric:
                require_text(metric[key], f'metric.{key}')
    for section in data.get('sections', []):
        if not isinstance(section, dict):
            raise ValueError('section 必须是对象')
        require_text(section.get('title'), 'section.title', True)
        if not isinstance(section.get('items'), list):
            raise ValueError('section.items 必须是数组')
        for item in section['items']:
            if not isinstance(item, dict):
                raise ValueError('item 必须是对象')
            require_text(item.get('title'), 'item.title', True)
            for key in ('detail', 'source', 'impact', 'support'):
                if key in item:
                    require_text(item[key], f'item.{key}')
            if 'status' in item and (not isinstance(item['status'], str) or item['status'] not in STATUS):
                raise ValueError('item.status 必须是 done / active / risk / planned')
            if 'progress' in item:
                value = item['progress']
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
                    raise ValueError('item.progress 必须是 0–100 的有限数字')
                require_text(item.get('source'), '含 progress 的 item.source', True)
    return data


def from_markdown(raw, filename):
    """Conservative heading/list conversion; preserve all other syntax as escaped text."""
    data = {'title': filename, 'sections': [], 'source_text': raw}
    section = None
    block = []
    fence = None
    got_title = False

    def flush():
        nonlocal block, section
        if block:
            if section is None:
                section = {'title': '报告正文', 'items': []}
                data['sections'].append(section)
            content = '\n'.join(block).strip()
            if content:
                lines = content.split('\n', 1)
                section['items'].append({'title': lines[0], 'detail': lines[1] if len(lines) > 1 else ''})
            block = []

    for line in raw.splitlines():
        fence_match = re.match(r'^\s*(`{3,}|~{3,})(.*)$', line)
        if fence_match:
            marker, tail = fence_match.groups()
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1] and not tail.strip():
                fence = None
            block.append(line)
            continue
        if fence:
            block.append(line)
            continue
        heading = re.match(r'^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$', line)
        if heading:
            flush()
            level, title = heading.groups()
            if len(level) == 1 and not got_title and not data['sections']:
                data['title'] = title
                got_title = True
            else:
                section = {'title': title, 'items': []}
                data['sections'].append(section)
        elif re.match(r'^\s{0,3}(?:[-+*]|\d+[.)])\s+', line):
            flush()
            block.append(re.sub(r'^\s{0,3}(?:[-+*]|\d+[.)])\s+', '', line))
        elif not line.strip():
            flush()
        else:
            block.append(line)
    flush()
    if not raw.strip():
        raise ValueError('Markdown 不能为空')
    return validate(data)


def render_item(item):
    status = item.get('status')
    badge = f'<span class="status status-{status}">{STATUS[status]}</span>' if status else ''
    parts = [f'<li class="item"><div class="item-top"><span class="item-title">{esc(item["title"])}</span>{badge}</div>']
    if item.get('detail'):
        parts.append(f'<p>{esc(item["detail"])}</p>')
    for key, label in [('impact', '影响'), ('support', '需要支持')]:
        if item.get(key):
            parts.append(f'<p class="risk-detail"><b>{label}：</b>{esc(item[key])}</p>')
    if 'progress' in item:
        value = format(item['progress'], 'g')
        parts.append(f'<div class="progress-wrap"><div class="progress-caption"><span>已报告进度</span><span>{value}%</span></div><progress max="100" value="{value}" aria-label="{esc(item["title"])}：{value}%">{value}%</progress></div>')
    if item.get('source'):
        parts.append(f'<p class="evidence">来源：{esc(item["source"])}</p>')
    return ''.join(parts) + '</li>'


def render(data, theme):
    validate(data)
    if theme not in THEMES:
        raise ValueError(f'未知模板：{theme}')
    styles = (ASSETS / 'base.css').read_text(encoding='utf-8') + '\n' + (ASSETS / f'{theme}.css').read_text(encoding='utf-8')
    metrics = []
    for metric in data.get('metrics', []):
        metrics.append(f'<article class="metric"><div class="metric-label">{esc(metric["label"])}</div><div class="metric-value">{esc(metric["value"])}<span class="metric-unit">{esc(metric.get("unit", ""))}</span></div><div class="metric-note">{esc(metric.get("note", ""))}</div><div class="evidence">来源：{esc(metric["source"])}</div></article>')
    sections = []
    for index, section in enumerate(data.get('sections', []), 1):
        items = ''.join(render_item(item) for item in section['items'])
        items = f'<ul class="section-items">{items}</ul>' if items else '<p class="empty">待补充</p>'
        sections.append(f'<section class="section"><div class="section-head"><span class="section-number">{index:02d}</span><h2>{esc(section["title"])}</h2></div>{items}</section>')
    values = {
        'title': esc(data['title']), 'styles': styles, 'theme': theme,
        'theme_name': THEMES[theme], 'eyebrow': esc(data.get('report_type', '工作报告')),
        'subtitle': esc(data.get('subtitle', '')),
        'date_block': f'<div class="date-block"><span>报告日期 / PERIOD</span><strong>{esc(data["date"])}</strong></div>' if data.get('date') else '',
        'demo_banner': '<div class="demo-banner">模板演示 · 以下为虚构示例，仅用于展示版式</div>' if data.get('demo') else '',
        'summary': f'<section class="summary" aria-label="核心结论"><span class="summary-label">核心结论</span><p>{esc(data["summary"])}</p></section>' if data.get('summary') else '',
        'metrics': '<section class="metrics" aria-label="关键数据">' + ''.join(metrics) + '</section>' if metrics else '',
        'sections': ''.join(sections),
        'source': f'<details class="source"><summary>查看原始日报</summary><pre>{esc(data["source_text"])}</pre></details>' if data.get('source_text') else '',
        'footer': esc(data.get('footer', '工作报告')),
    }
    return Template((ASSETS / 'report.html').read_text(encoding='utf-8')).substitute(values)


def gallery():
    descriptions = {'executive': '清晰分区 · 商务汇报', 'editorial': '暖白留白 · 正式归档', 'briefing': '深色侧栏 · 项目简报'}
    buttons = ''.join(f'<button type="button" data-theme="{key}" aria-pressed="{str(key == "executive").lower()}"><b>0{i} / {name}</b><span>{descriptions[key]}</span></button>' for i, (key, name) in enumerate(THEMES.items(), 1))
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>工作日报 · 模板预览</title><style>
*{box-sizing:border-box}body{margin:0;background:#e9edf1;color:#21374d;font:14px/1.6 "Segoe UI","Microsoft YaHei",sans-serif}header{max-width:1200px;margin:auto;padding:30px 28px 20px}small{letter-spacing:.18em;color:#576d83}h1{font-size:26px;margin:8px 0}p{color:#586c80;margin:0}.choices{display:flex;gap:12px;margin:22px 0 16px}button{flex:1;text-align:left;cursor:pointer;border:1px solid #bdcbd7;background:#f8fafc;color:#263e56;padding:13px 18px;border-radius:4px;font:inherit}button b,button span{display:block}button span{font-size:12px;margin-top:4px;color:#5d7184}button[aria-pressed=true]{border-color:#2e5f8b;box-shadow:inset 0 3px #2e5f8b;background:#fff}button:focus-visible,a:focus-visible{outline:3px solid #2e5f8b;outline-offset:3px}nav{display:flex;gap:18px;flex-wrap:wrap}a{color:#275c8d;text-underline-offset:4px}iframe{display:block;border:0;width:100%;height:calc(100vh - 285px);min-height:600px}noscript{display:block;padding:18px}@media(max-width:600px){header{padding:22px 16px}.choices{gap:8px}button{padding:10px;font-size:12px}button span{font-size:10px}iframe{min-height:700px}}
</style></head><body><header><small>REPORT TEMPLATE COLLECTION</small><h1>一份日报，三种正式表达。</h1><p>选择版式预览，打开独立页面即可打印或保存为 PDF。</p><div class="choices">''' + buttons + '''</div><nav><a id="open" href="executive.html" target="_blank" rel="noopener">打开商务蓝</a><a href="executive.html" download>下载商务蓝</a><a href="editorial.html" download>下载暖白简报</a><a href="briefing.html" download>下载深色侧栏</a></nav></header><iframe title="日报模板预览" src="executive.html"></iframe><noscript>可通过上方链接打开各模板。</noscript><script>
document.querySelectorAll('[data-theme]').forEach(button=>button.addEventListener('click',()=>{
document.querySelectorAll('[data-theme]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
const file=button.dataset.theme+'.html';document.querySelector('iframe').src=file;
const link=document.getElementById('open');link.href=file;link.textContent='打开'+button.querySelector('b').textContent.split(' / ')[1];
}));</script></body></html>'''


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='UTF-8 Markdown 或 JSON 日报')
    parser.add_argument('--theme', choices=THEMES, default='executive')
    parser.add_argument('--output', type=Path, required=True, help='单套 HTML 路径；--all 时为目录')
    parser.add_argument('--all', action='store_true', help='生成三套 HTML 与 index.html 预览入口')
    parser.add_argument('--force', action='store_true', help='允许覆盖已有输出')
    args = parser.parse_args(argv)
    try:
        raw = args.input.read_text(encoding='utf-8-sig')
        if args.input.suffix.lower() == '.json':
            data = validate(json.loads(raw))
        elif args.input.suffix.lower() in ('.md', '.markdown', '.txt'):
            data = from_markdown(raw, args.input.stem)
        else:
            raise ValueError('输入格式须为 .md / .markdown / .txt / .json')
        if args.all:
            outputs = {args.output / f'{theme}.html': render(data, theme) for theme in THEMES}
            outputs[args.output / 'index.html'] = gallery()
        else:
            if args.output.suffix.lower() != '.html':
                raise ValueError('单套输出必须使用 .html 扩展名')
            outputs = {args.output: render(data, args.theme)}
        for path in outputs:
            if path.resolve() == args.input.resolve():
                raise ValueError('输出不可覆盖输入文件')
            if path.exists() and not args.force:
                raise ValueError(f'输出已存在：{path}；请换路径或使用 --force')
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding='utf-8')
            print(path.resolve())
        return 0
    except (ValueError, OSError) as error:
        print(f'转换失败：{error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
