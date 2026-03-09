import io
import logging
import math
import re
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import qrcode
from pypdf import PdfReader, PdfWriter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent / "templates" / "certificado_vacio.pdf"

_CURSO_MINISTRADO_TEXT = (
    "Faculdade NeuroSaber - Credenciado pela Portaria MEC nº813/24 - "
    "Certificado emitido e registrado de acordo com a Resolução CNE/CES n/º "
    "1, de 6 de abril de 2018. - Registro nº 411 Livro nº 1 Folha nº 9 "
    "Londrina/PR, 09 de julho de 2025."
)

_PT_WEEKDAYS = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo",
}

_PT_MONTHS = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


def _format_pt_date(dt: datetime) -> str:
    weekday = _PT_WEEKDAYS[dt.weekday()]
    return (
        f"{weekday} - {dt.hour}h{dt.minute:02d}, "
        f"{dt.day} de {_PT_MONTHS[dt.month]}/{dt.strftime('%y')}"
    )


def _register_fonts():
    try:
        pdfmetrics.getFont("Helvetica")
    except KeyError:
        pass


def _generate_qr_image(data: str, box_size: int = 4) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=1,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _bold_lesson_number(lesson: str) -> str:
    escaped = xml_escape(lesson)
    match = re.match(r"^(\d+\.\d+)\s", escaped)
    if match:
        num = match.group(1)
        rest = escaped[match.end() :]
        return f"<b>{num}</b> {rest}"
    return escaped


def generate_certificate_pdf(
    contact_name: str,
    contact_cpf: str,
    course_name: str,
    course_display_name: str | None,
    carga_horaria: int,
    conteudo_programatico: dict | None,
    registration_info: str | None,
    issued_at: datetime,
    issued_location: str | None,
    token: str,
) -> bytes:
    _register_fonts()

    template_reader = PdfReader(str(TEMPLATE_PATH))
    writer = PdfWriter()

    validation_url = f"{settings.FRONTEND_URL}/validar/{token}"
    qr_buf = _generate_qr_image(validation_url, box_size=3)

    cpf_formatted = (
        f"{contact_cpf[:3]}.{contact_cpf[3:6]}.{contact_cpf[6:9]}-{contact_cpf[9:]}"
        if len(contact_cpf) == 11
        else contact_cpf
    )
    date_str = _format_pt_date(issued_at)

    # --- Page 1: Front of certificate ---
    template_page_1 = template_reader.pages[0]
    page_width = float(template_page_1.mediabox.width)
    page_height = float(template_page_1.mediabox.height)

    overlay1_buf = io.BytesIO()
    c = canvas.Canvas(overlay1_buf, pagesize=(page_width, page_height))

    c.setFont("Helvetica-BoldOblique", 22)
    name_y = page_height * 0.44
    c.drawCentredString(page_width / 2, name_y, contact_name)

    c.setFont("Helvetica", 11)
    cpf_y = name_y - 25
    c.drawCentredString(page_width / 2, cpf_y, f"CPF: {cpf_formatted}")

    course_label = course_display_name or course_name
    completion_text = (
        f"completou com sucesso, o Círculo de Palestras: "
        f"<b>{xml_escape(course_label)}</b>, "
        f"<b>com carga horária de {carga_horaria} horas</b>, realizado pela "
        f"Faculdade NeuroSaber, em Londrina - PR."
    )
    completion_style = ParagraphStyle(
        "completion",
        fontName="Helvetica",
        fontSize=16,
        leading=19,
        alignment=1,
    )
    completion_para = Paragraph(completion_text, completion_style)
    comp_max_w = page_width * 0.75
    _, comp_h = completion_para.wrap(comp_max_w, 999)
    comp_x = (page_width - comp_max_w) / 2
    comp_y_top = cpf_y - 18
    completion_para.drawOn(c, comp_x, comp_y_top - comp_h)

    c.setFont("Helvetica-Oblique", 11)
    date_y = page_height * 0.215
    c.drawCentredString(page_width / 2, date_y, date_str)

    from reportlab.lib.utils import ImageReader

    qr_img = ImageReader(qr_buf)
    qr_size = 28 * mm
    qr_x = page_width - qr_size - 12 * mm
    qr_y = 8 * mm
    c.drawImage(qr_img, qr_x, qr_y, width=qr_size, height=qr_size)

    c.setFont("Helvetica", 6)
    c.drawCentredString(qr_x + qr_size / 2, qr_y - 8, token)

    c.showPage()
    c.save()
    overlay1_buf.seek(0)

    overlay1_reader = PdfReader(overlay1_buf)
    template_page_1.merge_page(overlay1_reader.pages[0])
    writer.add_page(template_page_1)

    # --- Page 2: Back of certificate (details) ---
    if len(template_reader.pages) > 1:
        template_page_2 = template_reader.pages[1]
        p2_width = float(template_page_2.mediabox.width)
        p2_height = float(template_page_2.mediabox.height)
    else:
        p2_width = page_width
        p2_height = page_height
        template_page_2 = None

    overlay2_buf = io.BytesIO()
    c2 = canvas.Canvas(overlay2_buf, pagesize=(p2_width, p2_height))

    left_margin = 45
    right_margin = 45
    content_width = p2_width - left_margin - right_margin
    y = p2_height - 45

    field_style = ParagraphStyle(
        "field", fontName="Helvetica", fontSize=11, leading=14
    )
    conteudo_heading_style = ParagraphStyle(
        "conteudo_heading", fontName="Helvetica-Bold", fontSize=11, leading=14
    )
    module_name_style = ParagraphStyle(
        "module_name", fontName="Helvetica-Bold", fontSize=9, leading=12
    )
    lesson_style = ParagraphStyle(
        "lesson", fontName="Helvetica", fontSize=9, leading=12
    )
    emission_style = ParagraphStyle(
        "emission", fontName="Helvetica", fontSize=9, leading=12, alignment=2
    )

    def _draw_para(para: Paragraph, x: float, top_y: float, max_w: float) -> float:
        _, h = para.wrap(max_w, 999)
        para.drawOn(c2, x, top_y - h)
        return h

    # Aluno(a)
    p = Paragraph(f"<b>Aluno(a):</b> {xml_escape(contact_name)}", field_style)
    y -= _draw_para(p, left_margin, y, content_width) + 6

    # CPF
    p = Paragraph(f"<b>CPF:</b> {xml_escape(cpf_formatted)}", field_style)
    y -= _draw_para(p, left_margin, y, content_width) + 6

    # Curso ministrado por (fixed legal text)
    p = Paragraph(
        f"<b>Curso ministrado por:</b> {xml_escape(_CURSO_MINISTRADO_TEXT)}",
        field_style,
    )
    y -= _draw_para(p, left_margin, y, content_width) + 6

    # Carga horária
    p = Paragraph(f"<b>Carga horária:</b> {carga_horaria} horas", field_style)
    y -= _draw_para(p, left_margin, y, content_width) + 10

    # Conteúdo Programático heading
    p = Paragraph("Conteúdo Programático:", conteudo_heading_style)
    y -= _draw_para(p, left_margin, y, content_width) + 12

    # Two-column bordered content box
    if conteudo_programatico and conteudo_programatico.get("modules"):
        box_x = left_margin
        box_width = content_width
        box_pad = 10
        col_gap = 15
        col_width = (box_width - 2 * box_pad - col_gap) / 2

        modules_layout = []
        total_content_h = 0

        for module in conteudo_programatico["modules"]:
            module_name = module.get("name", "")
            lessons = module.get("lessons", [])

            mp = Paragraph(f"<b>{xml_escape(module_name)}</b>", module_name_style)
            _, mh = mp.wrap(box_width - 2 * box_pad, 999)

            mid = math.ceil(len(lessons) / 2)
            left_lessons = lessons[:mid]
            right_lessons = lessons[mid:]

            left_paras = []
            left_h = 0
            for lesson in left_lessons:
                lp = Paragraph(_bold_lesson_number(lesson), lesson_style)
                _, lh = lp.wrap(col_width, 999)
                left_paras.append((lp, lh))
                left_h += lh + 2

            right_paras = []
            right_h = 0
            for lesson in right_lessons:
                rp = Paragraph(_bold_lesson_number(lesson), lesson_style)
                _, rh = rp.wrap(col_width, 999)
                right_paras.append((rp, rh))
                right_h += rh + 2

            cols_h = max(left_h, right_h)
            module_total = mh + 4 + cols_h
            total_content_h += module_total

            modules_layout.append(
                {
                    "name_para": mp,
                    "name_h": mh,
                    "left_paras": left_paras,
                    "right_paras": right_paras,
                    "cols_h": cols_h,
                }
            )

        box_height = total_content_h + 2 * box_pad
        box_top = y
        box_bottom = box_top - box_height

        c2.setStrokeColorRGB(0, 0, 0)
        c2.setLineWidth(0.5)
        c2.rect(box_x, box_bottom, box_width, box_height, fill=0, stroke=1)

        cy = box_top - box_pad
        for mod in modules_layout:
            mod["name_para"].drawOn(c2, box_x + box_pad, cy - mod["name_h"])
            cy -= mod["name_h"] + 4

            ly = cy
            for lp, lh in mod["left_paras"]:
                lp.drawOn(c2, box_x + box_pad, ly - lh)
                ly -= lh + 2

            ry = cy
            for rp, rh in mod["right_paras"]:
                rp.drawOn(c2, box_x + box_pad + col_width + col_gap, ry - rh)
                ry -= rh + 2

            cy -= mod["cols_h"]

        y = box_bottom

    # Emission info (bottom-right aligned)
    location_str = f"{issued_location}, " if issued_location else ""
    emission_text = (
        f"<b>Certificado emitido em:</b> "
        f"{xml_escape(location_str)}{xml_escape(date_str)}"
    )
    ep = Paragraph(emission_text, emission_style)
    _, eh = ep.wrap(content_width, 999)
    ep.drawOn(c2, left_margin, 30)

    c2.showPage()
    c2.save()
    overlay2_buf.seek(0)

    overlay2_reader = PdfReader(overlay2_buf)
    if template_page_2:
        template_page_2.merge_page(overlay2_reader.pages[0])
        writer.add_page(template_page_2)
    else:
        writer.add_page(overlay2_reader.pages[0])

    output_buf = io.BytesIO()
    writer.write(output_buf)
    output_buf.seek(0)
    return output_buf.getvalue()
