"""Observable conversion invariants; run: python -m unittest discover -s scripts."""
import base64
import contextlib
import copy
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import tempfile
import unittest

import components
from components import charts as chart_module
import mdlite
from render_report import THEMES, from_markdown, main, render, validate

EXAMPLES = Path(__file__).resolve().parents[1] / 'assets/examples'
CHART_TYPES = sorted(name for name, spec in components.REGISTRY.items() if spec.group == '图表')


class Page(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.text = []
        self.tags = []
        self.resources = []
        self.feed(content)

    def handle_data(self, data):
        self.text.append(data)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        for key, value in attrs:
            if key in ('src', 'href'):
                self.resources.append(value)


def load(name):
    return json.loads((EXAMPLES / name).read_text(encoding='utf-8'))


def block(spec):
    return components.render(spec)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.example = load('daily-report.json')

    def test_theme_switch_preserves_report_facts(self):
        for theme in THEMES:
            page = Page(render(self.example, theme))
            text = '\n'.join(page.text)
            flat = text.replace('\n', '')
            self.assertIn(mdlite.plain(self.example['summary']), flat)
            for highlight in self.example['highlights']:
                self.assertIn(mdlite.plain(highlight['text']), flat)
            for section in self.example['sections']:
                for item in section.get('items', []):
                    for key in ('title', 'detail', 'impact', 'support', 'source'):
                        if key in item:
                            self.assertIn(item[key], text)
            self.assertIn('虚构示例', text)
            self.assertFalse(page.resources)

    def test_untrusted_text_is_inert_and_visible(self):
        payload = '<script>alert("unsafe")</script><img src=x onerror=alert(1)>'
        data = {'title': payload, 'summary': payload, 'sections': [{'title': payload, 'items': [{'title': payload, 'detail': payload}]}],
                'blocks': [{'type': 'table', 'columns': [payload], 'rows': [[payload]]}, {'type': 'callout', 'text': payload}]}
        page = Page(render(data, 'executive'))
        self.assertNotIn('script', page.tags)
        self.assertNotIn('img', page.tags)
        self.assertIn(payload, page.text)

    def test_markdown_body_renders_rich_blocks_without_external_assets(self):
        raw = ('# 审查汇报\n\n## 结论\n\n| 事项 | 结论 |\n| --- | :---: |\n| **迁移** | ==可继续== |\n\n'
               '> [!风险] 账号未开通\n> 影响提测\n\n- [x] 已完成项\n- [ ] 待办项\n\n'
               '正文含 `代码` 与 [站点](https://example.com) 及 [危险](javascript:alert(1))。\n\n'
               '```md\n# 不是标题\n```\n')
        data = from_markdown(raw, 'test')
        self.assertEqual(data['layout'], 'flow')
        self.assertEqual(data['source_text'], raw)
        content = render(data, 'executive')
        page = Page(content)
        for tag in ('table', 'thead', 'td', 'mark', 'strong', 'code', 'pre', 'ul'):
            self.assertIn(tag, page.tags)
        self.assertIn('callout callout-risk', content)
        self.assertIn('md-task is-done', content)
        self.assertIn('# 不是标题', '\n'.join(page.text))
        self.assertIn('https://example.com', page.resources)
        self.assertNotIn('href="javascript', content)

    def test_markdown_keeps_unknown_sections_and_full_text(self):
        raw = '# 原日报\n\n开头结论\n\n## 自定义客户反馈\n- 第一条\n  补充细节\n\n## 附注\n最后一段'
        data = from_markdown(raw, 'test')
        self.assertEqual([section['title'] for section in data['sections']], ['报告要点', '自定义客户反馈', '附注'])
        page = Page(render(data, 'editorial'))
        text = '\n'.join(page.text)
        for fragment in ('开头结论', '第一条', '补充细节', '最后一段'):
            self.assertIn(fragment, text)
        self.assertIn(raw, text)

    def test_markdown_fences_reference_any_component(self):
        raw = ('# 周报\n\n## 计划\n\n```actions\n[{"task": "完成回归", "owner": "李四", "priority": "P0"}]\n```\n\n'
               '```chart\n[{"type": "bar", "source": "台账", "data": [{"label": "服务端", "value": 9}]},'
               ' {"type": "gauge", "source": "OKR", "items": [{"label": "O1", "value": 80}]}]\n```\n\n'
               '```python\nprint("keep")\n```\n')
        content = render(from_markdown(raw, 'test'), 'briefing')
        for marker in ('block-actions', 'block-bar', 'block-gauge'):
            self.assertIn(marker, content)
        self.assertIn('data-lang="python"', content)
        with self.assertRaisesRegex(ValueError, 'Markdown 代码块'):
            render(from_markdown('# x\n\n## y\n\n```risks\n{bad json\n```\n', 't'), 'executive')

    def test_component_gallery_covers_every_component_offline(self):
        content = render(load('component-gallery.json'), 'executive', EXAMPLES)
        for name in components.REGISTRY:
            self.assertIn('block block-%s' % name, content, name)
        for resource in Page(content).resources:
            self.assertTrue(resource.startswith(('data:image/', '#sec-', 'https://example.com')), resource)

    def test_chart_type_reference_matches_registry(self):
        specs = load('chart-types.json')
        self.assertEqual(sorted(spec['type'] for spec in specs), CHART_TYPES)
        for spec in specs:
            page = Page(block(spec))
            self.assertFalse(page.resources)
            self.assertIn(spec['source'], '\n'.join(page.text))

    def test_every_example_validates_in_every_theme(self):
        for path in sorted(EXAMPLES.iterdir()):
            if path.name == 'chart-types.json':
                continue
            data = load(path.name) if path.suffix == '.json' else from_markdown(path.read_text(encoding='utf-8'), path.stem)
            self.assertTrue(data.get('demo') or '虚构' in path.read_text(encoding='utf-8'), path.name)
            for theme in THEMES:
                render(data, theme, EXAMPLES)

    def test_components_reject_unsourced_or_impossible_input(self):
        cases = [
            ({'type': 'bar', 'data': [{'label': 'a', 'value': 1}]}, 'source'),
            ({'type': 'pie', 'source': 's'}, '未知'),
            ({'type': 'bar', 'source': 's', 'data': [{'label': 'a', 'value': '9'}]}, '有限数字'),
            ({'type': 'bar', 'source': 's', 'data': [{'label': 'a', 'value': 9, 'color': '#f00'}]}, 'color'),
            ({'type': 'progress', 'source': 's', 'data': [{'label': 'a', 'value': 140}]}, '0–100'),
            ({'type': 'donut', 'source': 's', 'data': [{'label': 'a', 'value': 0}, {'label': 'b', 'value': 0}]}, '大于 0'),
            ({'type': 'line', 'source': 's', 'x': ['一', '二'], 'series': [{'name': 'a', 'points': [1]}]}, '长度'),
            ({'type': 'heatmap', 'source': 's', 'x': ['a'], 'y': ['r'], 'values': [[1, 2]]}, '二维数组'),
            ({'type': 'gauge', 'source': 's', 'items': [{'label': 'a', 'value': 120}]}, '0–100'),
            ({'type': 'scorecard', 'items': [{'label': 'a', 'target': 1, 'actual': 1}]}, 'source'),
            ({'type': 'kpis', 'items': [{'label': 'a', 'value': '1'}]}, '来源'),
            ({'type': 'rag', 'items': [{'name': 'a', 'status': 'red'}]}, '判据'),
            ({'type': 'rag', 'criteria': {'green': '按期'}, 'items': [{'name': 'a', 'status': 'red'}]}, 'criteria.red'),
            ({'type': 'risks', 'items': [{'title': 'a', 'level': 'urgent'}]}, 'high'),
            ({'type': 'actions', 'items': [{'task': 'a', 'priority': 'P9'}]}, 'P0'),
            ({'type': 'decisions', 'items': [{'decision': 'a', 'status': 'maybe'}]}, 'approved'),
            ({'type': 'evidence', 'items': [{'source': 'a', 'proves': 'b', 'kind': 'guess'}]}, 'observed'),
            ({'type': 'table', 'columns': ['a', 'b'], 'rows': [[1]]}, '列数'),
            ({'type': 'table', 'columns': [{'key': 'a', 'kind': 'money'}], 'rows': [[1]]}, 'kind'),
            ({'type': 'gantt', 'items': [{'task': 'a', 'start': '2026-09-10', 'end': '2026-09-01'}]}, '早于'),
            ({'type': 'gantt', 'items': [{'task': 'a', 'start': '2026/09/10', 'end': '2026-09-11'}]}, 'YYYY-MM-DD'),
            ({'type': 'gantt', 'items': [{'task': 'a', 'start': '2026-09-10'}]}, 'milestone'),
            ({'type': 'comparison', 'options': ['A', 'B'], 'criteria': [{'label': 'x', 'values': ['1']}]}, '一致'),
            ({'type': 'quadrant', 'x': {'label': 'x'}, 'y': {'label': 'y'}, 'items': [{'label': 'a', 'x': 11, 'y': 1}]}, '0–10'),
            ({'type': 'risk-matrix', 'scale': 4, 'items': []}, 'scale'),
            ({'type': 'fishbone', 'effect': 'e', 'categories': [{'name': 'a', 'causes': ['1']}]}, 'categories'),
            ({'type': 'steps', 'items': [{'title': 'only'}]}, '2–10'),
            ({'type': 'columns', 'ratio': '1:1:1', 'columns': [[], []]}, 'ratio'),
            ({'type': 'image', 'alt': 'x', 'src': 'https://example.com/a.png'}, '禁止外链'),
            ({'type': 'image', 'src': 'data:image/png;base64,AAAA'}, 'alt'),
            ({'type': 'callout', 'text': 'x', 'tone': 'purple'}, 'tone'),
            ({'type': 'checklist', 'items': [{'text': 'a', 'state': 'maybe'}]}, 'state'),
            ({'type': 'grid', 'cells': [{'title': 'a', 'items': []}]}, 'cells'),
            ({'type': 'callout', 'text': 'x', 'id': '1bad'}, 'id'),
        ]
        for spec, message in cases:
            with self.subTest(spec=spec['type'], message=message):
                with self.assertRaisesRegex(ValueError, message):
                    block(spec)

    def test_nested_errors_report_full_path(self):
        data = {'title': 't', 'sections': [{'title': 's', 'blocks': [
            {'type': 'columns', 'columns': [[{'type': 'callout', 'text': 'ok'}], [{'type': 'bar', 'data': []}]]}]}]}
        with self.assertRaisesRegex(ValueError, r'sections\[0\]\[0\]\.columns\[1\]\[0\]（bar）'):
            validate(data)

    def test_scorecard_computes_rate_and_shows_criteria(self):
        content = block({'type': 'scorecard', 'source': 's', 'items': [
            {'label': '良率', 'target': 97, 'actual': 96.2}, {'label': '周期', 'target': 90, 'actual': 102, 'lower_is_better': True},
            {'label': '产量', 'target': 12, 'actual': 12.6}]})
        text = ''.join(Page(content).text)
        for fragment in ('99.2%', '88.2%', '105%', '接近', '未达', '达成', '判据'):
            self.assertIn(fragment, text)

    def test_no_data_does_not_invent_metrics_or_charts(self):
        content = render({'title': '无数字日报', 'sections': [{'title': '风险', 'items': []}]}, 'briefing')
        page = Page(content)
        self.assertNotIn('progress', page.tags)
        self.assertNotIn('svg', page.tags)
        self.assertNotIn('class="metrics"', content.split('</style>')[1])
        self.assertNotIn('chart-board', content.split('</style>')[1])
        self.assertIn('待补充', page.text)
        self.assertNotIn('无明显风险', page.text)
        risk = ''.join(Page(block({'type': 'risks', 'items': [{'title': '账号未开通'}]})).text)
        self.assertIn('待补充', risk)

    def test_progress_requires_valid_value_and_evidence(self):
        for value in (-1, 101, True, '80', float('nan'), float('inf')):
            data = copy.deepcopy(self.example)
            data['sections'][1]['items'][0]['progress'] = value
            with self.assertRaises(ValueError):
                validate(data)
        data = copy.deepcopy(self.example)
        del data['sections'][1]['items'][0]['source']
        with self.assertRaises(ValueError):
            validate(data)
        data = copy.deepcopy(self.example)
        data['metrics'][0]['source'] = ''
        with self.assertRaises(ValueError):
            validate(data)

    def test_document_fields_are_checked(self):
        for broken in (
            {'title': 'x', 'highlights': [{'text': ''}]},
            {'title': 'x', 'highlights': [{'text': '要点', 'tone': 'purple'}]},
            {'title': 'x', 'layout': 'grid'},
            {'title': 'x', 'numbering': 'roman'},
            {'title': 'x', 'brand': {'accent': 'blue'}},
            {'title': 'x', 'brand': {'font': 'x'}},
            {'title': 'x', 'sections': [{'title': '空节'}]},
            {'title': 'x', 'sections': [{'title': 'a', 'items': [{'title': 'b', 'tags': 'x'}]}]},
            {'title': 'x', 'charts': [{'type': 'bar', 'data': [{'label': 'a', 'value': 1}]}]},
            {'title': 'x', 'blocks': [{'type': 'nope'}]},
        ):
            with self.assertRaises(ValueError):
                validate(broken)

    def test_brand_numbering_meta_and_indent(self):
        data = {'title': 't', 'brand': {'accent': '#1F6FEB', 'palette': ['#111111', '#222222']}, 'numbering': 'cn', 'indent': True,
                'genre': '审查报告', 'industry': '制造', 'sections': [{'title': '背景', 'body': '正文'}, {'title': '三、已编号', 'body': 'x'}]}
        content = render(data, 'editorial')
        self.assertIn('body.theme-editorial{--accent:#1F6FEB', content)
        self.assertIn('--chart-2:#222222', content)
        self.assertIn('一、背景', content)
        self.assertIn('>三、已编号<', content)
        self.assertNotIn('二、三、已编号', content)
        self.assertIn('indent-paragraphs', content)
        self.assertIn('审查报告', ''.join(Page(content).text))

    def test_flow_layout_adds_navigation_and_cards_layout_does_not(self):
        flow = render(from_markdown('# 报告\n\n## 一\n甲\n\n## 二\n乙\n\n## 三\n丙', 'test'), 'executive')
        self.assertIn('class="toc"', flow)
        self.assertIn('layout-flow', flow)
        self.assertIn('href="#sec-3"', flow)
        cards = render(self.example, 'executive')
        self.assertIn('layout-cards', cards)
        self.assertNotIn('<nav class="toc"', cards)

    def test_image_path_is_embedded_and_resolved_against_input(self):
        png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==')
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / 'shot.png').write_bytes(png)
            source = folder / 'r.json'
            source.write_text(json.dumps({'title': 't', 'blocks': [{'type': 'image', 'path': 'shot.png', 'alt': '截图', 'caption': '压测截图'}]}), encoding='utf-8')
            output = folder / 'r.html'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(source), '--output', str(output)]), 0)
            content = output.read_text(encoding='utf-8')
            self.assertIn('src="data:image/png;base64,', content)
            self.assertIn('压测截图', content)
        with self.assertRaisesRegex(ValueError, '找不到图片'):
            block({'type': 'image', 'path': 'missing.png', 'alt': 'x'})

    def test_cli_check_list_and_overwrite_protection(self):
        with contextlib.redirect_stdout(io.StringIO()) as listing:
            self.assertEqual(main(['--list-components']), 0)
        for name in components.REGISTRY:
            self.assertIn(name, listing.getvalue())
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / '日报.md'
            source.write_text('# 工作日报\n\n- 交付说明 📝', encoding='utf-8-sig')
            output = folder / '预览'
            args = [str(source), '--all', '--output', str(output)]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(source), '--check']), 0)
                self.assertEqual(main(args), 0)
                original = (output / 'executive.html').read_bytes()
                self.assertEqual(main(args), 1)
            self.assertEqual(len(list(output.glob('*.html'))), 4)
            self.assertEqual((output / 'executive.html').read_bytes(), original)
            self.assertIn('交付说明 📝', (output / 'editorial.html').read_text(encoding='utf-8'))

    def test_chart_module_documents_every_chart(self):
        for name in CHART_TYPES:
            self.assertIn(name, chart_module.__doc__)


if __name__ == '__main__':
    unittest.main()
