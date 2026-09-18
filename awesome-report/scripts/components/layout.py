"""版式与素材类组件：分栏、内嵌图片、打印分页。"""
import base64
from pathlib import Path
import re

from . import component, render_many
from .base import esc, inline, listing, optional, text

RATIO = re.compile(r'^[1-4](:[1-4]){1,3}$')
DATA_URI = re.compile(r'^data:image/(png|jpeg|gif|webp|svg\+xml);base64,[A-Za-z0-9+/=\s]+$')
MIME = {'.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.gif': 'gif', '.webp': 'webp', '.svg': 'svg+xml'}
MAX_IMAGE = 5 * 1024 * 1024


@component('columns', group='版式与素材', summary='分栏：把任意组件并排放成 2–4 栏，比例可调（如 2:1）', aliases=('row',))
def _columns(block, ctx):
    columns = listing(block.get('columns'), 'columns', 2, 4)
    ratio = block.get('ratio', ':'.join('1' * len(columns)))
    if not (isinstance(ratio, str) and RATIO.match(ratio)) or len(ratio.split(':')) != len(columns):
        raise ValueError('ratio 必须形如 1:1 / 2:1 / 1:1:1，且份数等于栏数 %d' % len(columns))
    template = ' '.join('minmax(0,%sfr)' % part for part in ratio.split(':'))
    cells = []
    for index, children in enumerate(columns):
        cells.append('<div class="col">%s</div>' % render_many(children, ctx.child('.columns[%d]' % index)))
    return '<div class="cols" style="grid-template-columns:%s">%s</div>' % (template, ''.join(cells))


@component('image', group='版式与素材', summary='内嵌图片：截图、现场照片、原型图，本地文件自动转为内嵌数据，离线可看', tag='figure')
def _image(block, ctx):
    alt = text(block.get('alt'), 'alt（图片必须写替代文字）')
    if block.get('path'):
        path = Path(text(block['path'], 'path'))
        if not path.is_absolute() and ctx.base_dir:
            path = Path(ctx.base_dir) / path
        mime = MIME.get(path.suffix.lower())
        if not mime:
            raise ValueError('path 仅支持 %s' % ' / '.join(MIME))
        if not path.is_file():
            raise ValueError('找不到图片文件：%s' % path)
        if path.stat().st_size > MAX_IMAGE:
            raise ValueError('图片超过 5MB，请先压缩：%s' % path)
        src = 'data:image/%s;base64,%s' % (mime, base64.b64encode(path.read_bytes()).decode('ascii'))
    else:
        src = text(block.get('src'), 'src（或 path）')
        if not DATA_URI.match(src):
            raise ValueError('src 只接受 data:image/...;base64 内嵌数据；本地文件请用 path，禁止外链以保证离线')
    width = block.get('width', 'full')
    if width not in ('full', 'wide', 'half', 'third'):
        raise ValueError('width 必须是 full / wide / half / third')
    caption = optional(block, 'caption')
    return '<img class="img-%s" src="%s" alt="%s">%s' % (
        width, esc(src), esc(alt), '<figcaption>%s</figcaption>' % inline(caption) if caption else '')


@component('pagebreak', group='版式与素材', summary='打印分页：在此处强制换页，只影响打印 / 存 PDF')
def _pagebreak(block, ctx):
    return '<span class="page-break" aria-hidden="true"></span>'
