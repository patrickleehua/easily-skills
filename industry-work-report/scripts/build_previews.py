#!/usr/bin/env python3
"""重新生成 assets/previews：组件库、各体裁示例、日报三套主题，以及 index.html 入口。

    python scripts/build_previews.py
"""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render_report import THEMES, from_markdown, gallery, render  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / 'assets' / 'examples'
PREVIEWS = ROOT / 'assets' / 'previews'

# (输出文件, 示例文件, 主题, 名称, 说明)
PAGES = [
    ('components.html', 'component-gallery.json', 'executive', '组件库', '全部 38 个标准组件'),
    ('weekly-status.html', 'weekly-status.json', 'executive', '研发周报', '红黄绿 · 甘特 · 风险 · 计划'),
    ('audit-review.html', 'audit-review.json', 'editorial', '审查报告', '决策 · 证据台账 · 发现分级'),
    ('tech-validation.html', 'tech-validation.json', 'executive', '技术验证', '判据 · 方案对比 · 压测曲线'),
    ('monthly-manufacturing.html', 'monthly-manufacturing.json', 'briefing', '制造月报', '达成表 · 热力 · 鱼骨 · 8D'),
    ('retrospective.html', 'retrospective.json', 'editorial', '项目复盘', 'GRAI · 瀑布 · KISS'),
    ('daily-markdown.html', 'daily-report.md', 'briefing', 'Markdown 日报', 'Markdown 内嵌组件'),
] + [('%s.html' % key, 'daily-report.json', key, '日报 · %s' % name, '同一份日报的%s版式' % name) for key, name in THEMES.items()]


def load(path):
    raw = path.read_text(encoding='utf-8')
    return json.loads(raw) if path.suffix == '.json' else from_markdown(raw, path.stem)


def main():
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    for output, source, theme, _, _ in PAGES:
        target = PREVIEWS / output
        target.write_text(render(load(EXAMPLES / source), theme, EXAMPLES), encoding='utf-8')
        print(target.relative_to(ROOT))
    (PREVIEWS / 'index.html').write_text(gallery([(output, name, desc) for output, _, _, name, desc in PAGES]), encoding='utf-8')
    print((PREVIEWS / 'index.html').relative_to(ROOT))


if __name__ == '__main__':
    main()
