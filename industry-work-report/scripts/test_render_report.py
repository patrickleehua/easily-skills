"""Observable conversion invariants; run: python -m unittest discover -s scripts."""
import copy
from html.parser import HTMLParser
import json
from pathlib import Path
import tempfile
import unittest

from render_report import THEMES, from_markdown, main, render, validate


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


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.example = json.loads((Path(__file__).resolve().parents[1] / 'assets/examples/daily-report.json').read_text(encoding='utf-8'))

    def test_theme_switch_preserves_report_facts(self):
        for theme in THEMES:
            page = Page(render(self.example, theme))
            text = '\n'.join(page.text)
            self.assertIn(self.example['summary'], text)
            for section in self.example['sections']:
                for item in section['items']:
                    for key in ('title', 'detail', 'impact', 'support', 'source'):
                        if key in item:
                            self.assertIn(item[key], text)
            self.assertIn('虚构示例', text)
            self.assertFalse(page.resources)

    def test_untrusted_text_is_inert_and_visible(self):
        payload = '<script>alert("unsafe")</script><img src=x onerror=alert(1)>'
        data = {'title': payload, 'summary': payload, 'sections': [{'title': payload, 'items': [{'title': payload, 'detail': payload}]}]}
        page = Page(render(data, 'executive'))
        self.assertNotIn('script', page.tags)
        self.assertNotIn('img', page.tags)
        self.assertIn(payload, page.text)

    def test_no_data_does_not_invent_metrics_or_progress(self):
        content = render({'title': '无数字日报', 'sections': [{'title': '风险', 'items': []}]}, 'briefing')
        page = Page(content)
        self.assertNotIn('progress', page.tags)
        self.assertNotIn('class="metrics"', content)
        self.assertIn('待补充', page.text)
        self.assertNotIn('无明显风险', page.text)

    def test_progress_requires_valid_value_and_evidence(self):
        for value in (-1, 101, True, '80', float('nan'), float('inf')):
            data = copy.deepcopy(self.example)
            data['sections'][1]['items'][0]['progress'] = value
            with self.assertRaises(ValueError):
                validate(data)
        for field in ('source',):
            data = copy.deepcopy(self.example)
            del data['sections'][1]['items'][0][field]
            with self.assertRaises(ValueError):
                validate(data)
        data = copy.deepcopy(self.example)
        data['metrics'][0]['source'] = ''
        with self.assertRaises(ValueError):
            validate(data)

    def test_markdown_keeps_unknown_sections_and_code(self):
        raw = '# 原日报\n\n开头结论\n\n## 自定义客户反馈\n- 第一条\n  补充细节\n\n| 金额 | 范围 |\n| 1 | 测试 |\n\n```md\n# 不是标题\n- 不是列表\n```\n\n## 附注\n最后一段'
        data = from_markdown(raw, 'test')
        self.assertEqual(data['source_text'], raw)
        self.assertEqual([section['title'] for section in data['sections']], ['报告正文', '自定义客户反馈', '附注'])
        self.assertNotIn('metrics', data)
        self.assertIn('# 不是标题', data['sections'][1]['items'][-1]['detail'])
        page = Page(render(data, 'editorial'))
        self.assertIn(raw, page.text)

    def test_unicode_bom_cli_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            source = folder / '日报.md'
            source.write_text('# 工作日报\n\n- 交付说明 📝', encoding='utf-8-sig')
            output = folder / '预览'
            args = [str(source), '--all', '--output', str(output)]
            self.assertEqual(main(args), 0)
            self.assertEqual(len(list(output.glob('*.html'))), 4)
            original = (output / 'executive.html').read_bytes()
            self.assertEqual(main(args), 1)
            self.assertEqual((output / 'executive.html').read_bytes(), original)
            self.assertIn('交付说明 📝', (output / 'editorial.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
