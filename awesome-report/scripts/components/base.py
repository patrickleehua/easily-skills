"""组件公共工具：转义、字段校验、语气色、状态词与统一外框（仅标准库）。

所有组件都遵守同一套约定：
- 输入是一个 JSON 对象（block），`type` 决定用哪个组件；
- 公共可选字段 `title` / `note` / `source` / `id`，由 `frame()` 统一渲染；
- 文本字段先转义再按 Markdown 子集渲染，素材里的 HTML 与脚本永远不会执行；
- 校验失败抛 ValueError，信息写清是哪个字段、要求是什么。
"""
import datetime
import html
import math
import re

import mdlite

TONES = ('accent', 'info', 'good', 'warn', 'risk', 'muted')
TONE_LABELS = {'accent': '重点', 'info': '说明', 'good': '建议', 'warn': '注意', 'risk': '风险', 'muted': '备注'}

# 通用状态词：一个状态一种语气色，全报告一致（语义色原则：一义一色、颜色不单独承载含义）
STATUS = {
    'done': ('good', '已完成'), 'active': ('accent', '进行中'), 'planned': ('muted', '计划'),
    'risk': ('warn', '需协调'), 'blocked': ('risk', '阻塞'), 'delayed': ('risk', '延期'),
    'open': ('info', '待处理'), 'cancelled': ('muted', '已取消'), 'na': ('muted', '不适用'),
}
STATUS_ALIASES = {
    '已完成': 'done', '完成': 'done', '进行中': 'active', '计划': 'planned', '未开始': 'planned',
    '需协调': 'risk', '风险': 'risk', '阻塞': 'blocked', '延期': 'delayed', '待处理': 'open',
    '已取消': 'cancelled', '不适用': 'na',
}
LEVELS = {'high': ('risk', '高'), 'medium': ('warn', '中'), 'low': ('muted', '低')}
LEVEL_ALIASES = {'高': 'high', '中': 'medium', '低': 'low', 'h': 'high', 'm': 'medium', 'l': 'low'}
BLOCK_ID = re.compile(r'^[A-Za-z][\w-]{0,40}$')


def esc(value):
    return html.escape(str(value), quote=True)


def inline(text):
    return mdlite.inline(text)


def plain(text):
    return mdlite.plain(text)


def markdown(text):
    """块级 Markdown；正文里的组件代码块会递归渲染成组件。"""
    from . import fence_handler  # 延迟导入：注册表在包初始化后才完整
    return mdlite.to_html(text, handler=fence_handler)


def text(value, field, required=True):
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError('%s 必须是%s字符串' % (field, '非空' if required else ''))
    return value


def optional(block, key, field=None):
    """读取可选字符串字段；存在时必须是字符串。"""
    if key not in block or block[key] is None:
        return ''
    return text(block[key], field or key, False)


def number(value, field, low=None, high=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('%s 必须是有限数字' % field)
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError('%s 必须在 %s–%s 之间' % (field, fmt(low) if low is not None else '-∞', fmt(high) if high is not None else '∞'))
    return float(value)


def listing(value, field, low=1, high=60):
    if not isinstance(value, list) or not low <= len(value) <= high:
        raise ValueError('%s 必须是 %d–%d 项的数组' % (field, low, high))
    return value


def objects(value, field, low=1, high=60):
    for entry in listing(value, field, low, high):
        if not isinstance(entry, dict):
            raise ValueError('%s 的元素必须是对象' % field)
    return value


def tone(value, field='tone', default='accent'):
    if value is None:
        return default
    if value not in TONES:
        raise ValueError('%s 必须是 %s 之一' % (field, ' / '.join(TONES)))
    return value


def status(value, field='status'):
    """状态词归一：支持英文键与中文别名，返回 (键, 语气色, 中文标签)。"""
    key = STATUS_ALIASES.get(value, value)
    if key not in STATUS:
        raise ValueError('%s 必须是 %s 之一' % (field, ' / '.join(STATUS)))
    return (key,) + STATUS[key]


def level(value, field='level'):
    key = LEVEL_ALIASES.get(str(value).lower(), str(value).lower()) if isinstance(value, str) else None
    if key not in LEVELS:
        raise ValueError('%s 必须是 high / medium / low（或 高 / 中 / 低）' % field)
    return (key,) + LEVELS[key]


def date(value, field):
    text(value, field)
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise ValueError('%s 必须是 YYYY-MM-DD 日期' % field) from None


def fmt(value):
    if value is None:
        return ''
    if float(value).is_integer():
        return format(int(value), ',')
    return ('%.2f' % value).rstrip('0').rstrip('.')


def clip(label, limit):
    label = str(label)
    return label if len(label) <= limit else label[:limit - 1] + '…'


def badge(tone_name, label):
    return '<span class="badge badge-%s">%s</span>' % (tone_name, esc(label))


def status_badge(value, field='status'):
    _, tone_name, label = status(value, field)
    return badge(tone_name, label)


def meta(*pairs):
    """渲染“负责人 · 截止”这类次要信息，空值自动省略。"""
    parts = ['<span><b>%s</b>%s</span>' % (esc(label), inline(value)) for label, value in pairs if value]
    return '<div class="meta">%s</div>' % ''.join(parts) if parts else ''


def frame(kind, block, body, tag='div', extra=''):
    """所有组件的统一外框：标题行 + 主体 + 来源行。"""
    head = ''
    title, note = block.get('title'), block.get('note')
    if title or note:
        head = '<div class="block-head">%s%s</div>' % (
            '<span class="block-title">%s</span>' % inline(title) if title else '',
            '<span class="block-note">%s</span>' % inline(note) if note else '')
    foot = '<p class="evidence">来源：%s</p>' % esc(block['source']) if block.get('source') else ''
    ident = ' id="%s"' % esc(block['id']) if block.get('id') else ''
    return '<%s class="block block-%s%s"%s>%s%s%s</%s>' % (tag, kind, extra, ident, head, body, foot, tag)
