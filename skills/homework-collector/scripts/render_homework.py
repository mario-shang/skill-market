#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小学生作业汇总图片生成器

docx 精确排版 → LibreOffice 转 PDF → pdftoppm 转 PNG。
从 src/agents/homework_collector/generate_homework.py 抽出的独立版，
无项目内依赖，供 homework-collector skill 使用。

依赖：python-docx（venv）、libreoffice、pdftoppm、文泉驿字体。

用法：
  render_homework.py --chinese "听写第5课\n预习课文" --english "抄写单词" --math "口算第3页" --output homework.png
  render_homework.py --confirm ...   # 只打印确认文本，不出图
"""
import argparse
import os
import subprocess
import tempfile

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

FONT = 'WenQuanYi Micro Hei'


def generate_confirmation_text(chinese_items, english_items, math_items):
    """生成确认文本，用于用户确认和修正（与原 agent 输出格式一致）"""
    lines = []
    for title, items in (('【语文作业】', chinese_items),
                         ('【英语作业】', english_items),
                         ('【数学作业】', math_items)):
        if items:
            lines.append(title)
            lines.extend(f"  {i}. {item}" for i, item in enumerate(items, 1))
            lines.append("")

    lines.append("请确认以上内容是否正确：")
    lines.append("- 内容正确：回复【确认】生成图片")
    lines.append("- 有错误：请直接说明问题，或提供完整的修正内容")
    return "\n".join(lines)


def _set_table_borders(table):
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')
    if tbl.tblPr is None:
        tbl.insert(0, tblPr)
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:color'), '000000')
        border.set(qn('w:space'), '0')
        tblBorders.append(border)
    tblPr.append(tblBorders)


def _set_cell_vertical_alignment(cell, align='top'):
    tcPr = cell._tc.get_or_add_tcPr()
    vAlign = OxmlElement('w:vAlign')
    vAlign.set(qn('w:val'), align)
    tcPr.append(vAlign)


def _cn_font(run, size):
    run.font.size = Pt(size)
    run.font.name = FONT
    run._element.rPr.rFonts.set(qn('w:eastAsia'), FONT)


def create_homework_doc(chinese_items, english_items, math_items):
    """创建作业汇总 Word 文档。固定结构：2 行 3 列（标题行 + 内容行）"""
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Cm(21.0), Cm(29.7)
    section.left_margin = section.right_margin = Cm(1.4)
    section.top_margin = section.bottom_margin = Cm(1.8)

    table = doc.add_table(rows=2, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    col_width = int((section.page_width - section.left_margin - section.right_margin) / 3)
    for col in table.columns:
        col.width = col_width

    for col_idx, title in enumerate(['语文作业', '英语作业', '数学作业']):
        cell = table.rows[0].cells[col_idx]
        cell.text = title
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_before = Pt(6)
        paragraph.paragraph_format.space_after = Pt(6)
        _cn_font(paragraph.runs[0], 18)
        rPr = paragraph.runs[0]._element.get_or_add_rPr()
        rPr.append(OxmlElement('w:b'))
        _set_cell_vertical_alignment(cell, 'center')

    for col_idx, items in enumerate([chinese_items, english_items, math_items]):
        cell = table.rows[1].cells[col_idx]
        cell.text = ""
        for item_idx, item in enumerate(items):
            paragraph = cell.paragraphs[0] if item_idx == 0 else cell.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paragraph.paragraph_format.space_before = Pt(2)
            paragraph.paragraph_format.space_after = Pt(2)
            paragraph.paragraph_format.line_spacing = 1.5
            run = paragraph.add_run(f"□ {item}")
            _cn_font(run, 14)
        _set_cell_vertical_alignment(cell, 'top')

    _set_table_borders(table)
    return doc


def doc_to_image(doc, output_path):
    """docx → PDF → PNG。

    并发隔离：LibreOffice 默认共享 ~/.config/libreoffice 锁，多进程同时跑会
    卡死或冲突。用 -env:UserInstallation 为每次转换分配独立 profile dir，
    随 tempdir 清理。转换失败时保留 docx 到输出路径（.png→.docx）以便人工排版兜底。
    """
    output_dir = os.path.dirname(output_path) or '.'
    base_name = os.path.splitext(os.path.basename(output_path))[0]
    tmp_docx = os.path.join(output_dir, f'{base_name}.docx')
    tmp_pdf = os.path.join(output_dir, f'{base_name}.pdf')

    try:
        doc.save(tmp_docx)

        with tempfile.TemporaryDirectory(prefix='lo_profile_') as lo_profile:
            result = subprocess.run(
                ['libreoffice', f'-env:UserInstallation=file://{lo_profile}',
                 '--headless', '--convert-to', 'pdf', '--outdir', output_dir, tmp_docx],
                capture_output=True, text=True, timeout=60)

        if not os.path.exists(tmp_pdf):
            raise RuntimeError(f"LibreOffice 转换失败: {result.stderr}")

        png_prefix = os.path.join(output_dir, f'{base_name}_tmp')
        result = subprocess.run(['pdftoppm', '-png', '-r', '200', tmp_pdf, png_prefix],
                                capture_output=True, text=True, timeout=60)
        tmp_png = f'{png_prefix}-1.png'
        if not os.path.exists(tmp_png):
            raise RuntimeError(f"pdftoppm 转换失败: {result.stderr}")

        os.rename(tmp_png, output_path)
        if os.path.exists(tmp_docx):
            os.unlink(tmp_docx)
        if os.path.exists(tmp_pdf):
            os.unlink(tmp_pdf)
        print(f"已生成图片: {output_path}")
        return True
    except Exception as e:
        print(f"转换失败: {e}")
        if os.path.exists(tmp_docx):
            docx_fallback = output_path.replace('.png', '.docx')
            os.rename(tmp_docx, docx_fallback)
            print(f"已保存 Word 文档: {docx_fallback}")
        return False


def main():
    parser = argparse.ArgumentParser(description='生成小学生作业汇总图片')
    parser.add_argument('--chinese', default='', help='语文作业，多项用 \\n 分隔')
    parser.add_argument('--english', default='', help='英语作业，多项用 \\n 分隔')
    parser.add_argument('--math', default='', help='数学作业，多项用 \\n 分隔')
    parser.add_argument('--output', default='homework.png', help='输出图片路径')
    parser.add_argument('--confirm', action='store_true', help='生成确认文本（不生成图片）')
    args = parser.parse_args()

    split = lambda s: [x.strip() for x in s.split('\n') if x.strip()]
    chinese_items, english_items, math_items = (
        split(args.chinese), split(args.english), split(args.math))

    if args.confirm:
        print(generate_confirmation_text(chinese_items, english_items, math_items))
        return

    if not (chinese_items or english_items or math_items):
        parser.error('三科内容全空：请至少提供一科作业（--chinese/--english/--math）')
    doc = create_homework_doc(chinese_items, english_items, math_items)
    ok = doc_to_image(doc, args.output)
    raise SystemExit(0 if ok else 1)


if __name__ == '__main__':
    main()
