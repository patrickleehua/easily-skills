"""报告标准组件库（仅标准库，离线、可打印、无脚本）。

一个组件 = 一个名字 + 一个渲染函数。两种引用方式渲染结果完全一致：
- JSON：在 `blocks` 数组里写 {"type": "<组件名>", ...}；
- Markdown：写一个以组件名为语言的代码块，块内是 JSON。

    ```timeline
    [{"date": "2026-09-14", "title": "需求冻结", "status": "done"}]
    ```

代码块内容是 JSON 数组时，按组件名解释为 {"items": [...]} 的简写；
语言写 `chart` / `component` 时，数组表示多个组件。
组件目录与字段说明见 references/components.md。
"""
from dataclasses import dataclass
import json
from typing import Callable

from . import base

REGISTRY = {}
ALIASES = {}
GENERIC_LANGS = ('chart', 'chart-json', '图表', 'component', 'block', '组件')
CODE_LANGS = ('markdown', 'md', 'text', 'txt')


class BlockError(ValueError):
    """已带完整定位路径的组件错误，嵌套渲染时不再重复加前缀。"""


@dataclass(frozen=True)
class Spec:
    name: str
    render: Callable
    group: str
    summary: str
    source: bool
    tag: str
    extra: str


@dataclass(frozen=True)
class Context:
    path: str
    base_dir: object = None

    def child(self, suffix):
        return Context(self.path + suffix, self.base_dir)


def component(name, *, group, summary, source=False, aliases=(), tag='div', extra=''):
    """注册一个组件。source=True 表示组件承载数据，必须写来源。"""
    def register(fn):
        REGISTRY[name] = Spec(name, fn, group, summary, source, tag, extra)
        for alias in aliases:
            ALIASES[alias] = name
        return fn
    return register


def resolve(kind):
    return ALIASES.get(kind, kind) if isinstance(kind, str) else kind


def render(block, path='block', base_dir=None):
    return _render(block, Context(path, base_dir))


def _render(block, ctx):
    if not isinstance(block, dict):
        raise BlockError('%s 必须是对象' % ctx.path)
    kind = resolve(block.get('type'))
    spec = REGISTRY.get(kind)
    if spec is None:
        raise BlockError('%s.type 未知：%r；可用组件见 references/components.md' % (ctx.path, block.get('type')))
    try:
        base.optional(block, 'title')
        base.optional(block, 'note')
        if spec.source:
            base.text(block.get('source'), 'source（该组件承载数据，必须写来源）')
        else:
            base.optional(block, 'source')
        if 'id' in block and not (isinstance(block['id'], str) and base.BLOCK_ID.match(block['id'])):
            raise ValueError('id 须以字母开头，只含字母、数字、下划线或连字符')
        body = spec.render(block, ctx)
    except BlockError:
        raise
    except ValueError as error:
        raise BlockError('%s（%s）：%s' % (ctx.path, kind, error)) from None
    return base.frame(kind, block, body, spec.tag, spec.extra)


def render_many(blocks, ctx):
    if not isinstance(blocks, list):
        raise BlockError('%s 必须是数组' % ctx.path)
    return ''.join(_render(block, ctx.child('[%d]' % index)) for index, block in enumerate(blocks))


def fence_handler(lang, text):
    """mdlite 回调：把组件代码块渲染成组件；其余情况返回 None 保持普通代码块。

    只有块内是 JSON（以 { 或 [ 开头）才当组件；md / markdown / text 永远是代码块，
    这样展示 Markdown 源码、普通文本的代码块不会被误识别。
    """
    key = lang.strip().lower()
    generic = key in GENERIC_LANGS
    if key in CODE_LANGS or (not generic and resolve(key) not in REGISTRY):
        return None
    if not text.lstrip().startswith(('{', '[')):
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise BlockError('Markdown 代码块 ```%s 不是合法 JSON：%s' % (lang, error)) from None
    if generic:
        specs = data if isinstance(data, list) else [data]
    else:
        spec = {'items': data} if isinstance(data, list) else data
        if isinstance(spec, dict):
            spec = dict(spec)
            spec.setdefault('type', key)
        specs = [spec]
    ctx = Context('Markdown 代码块 ```%s' % lang)
    return ''.join(_render(spec, ctx.child('[%d]' % index) if len(specs) > 1 else ctx) for index, spec in enumerate(specs))


def catalog():
    """按分组列出全部组件，用于文档与组件画廊。"""
    return sorted(REGISTRY.values(), key=lambda spec: (GROUP_ORDER.index(spec.group), spec.name))


GROUP_ORDER = ('结论与强调', '指标与数据', '图表', '管理与决策', '进度与流程', '分析框架', '版式与素材')

# 注册全部组件（导入即注册）
from . import text, data, charts, manage, flow, analysis, layout  # noqa: E402,F401
