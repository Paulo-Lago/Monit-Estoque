from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A6, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)

# ==================== FUNÇÃO DE GERAR PDF A6 (REPORTLAB) ====================
def gerar_pdf_recibo_reportlab(dados_venda, itens, numero_recibo):
    buffer = BytesIO()

    page_size = landscape(A6)
    largura_pagina, altura_pagina = page_size

    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        topMargin=0.45 * cm,
        bottomMargin=0.45 * cm,
        leftMargin=0.55 * cm,
        rightMargin=0.55 * cm
    )

    styles = getSampleStyleSheet()

    # ==================== IMAGENS ====================
    assets_dir = Path(__file__).parent / "assets"
    logo_path = assets_dir / "logoico.png"
    qrcode_pix_path = assets_dir / "qrcode_pix.png"

    # ==================== CORES ====================
    cor_primaria = colors.HexColor("#EDC575")
    cor_primaria_escura = colors.HexColor("#996633")
    cor_fundo = colors.HexColor("#F6FAF7")
    cor_fundo_linha = colors.HexColor("#FAFAFA")
    cor_linha = colors.HexColor("#D7E3DA")
    cor_texto = colors.HexColor("#263238")
    cor_cinza = colors.HexColor("#6B7280")
    cor_vermelho = colors.HexColor("#B71C1C")
    cor_vermelho_fundo = colors.HexColor("#FDECEC")
    cor_verde_fundo = colors.HexColor("#E8F5E9")

    # ==================== HELPERS ====================
    def safe_text(valor):
        if valor is None:
            return ""
        return escape(str(valor))

    def to_float(valor):
        try:
            return float(valor or 0)
        except Exception:
            return 0.0

    def fmt_br(valor):
        valor = to_float(valor)
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def fmt_num(valor):
        valor = to_float(valor)
        return f"{valor:.2f}".replace(".", ",")

    def data_formatada(valor):
        if hasattr(valor, "strftime"):
            return valor.strftime("%d/%m/%Y")
        return safe_text(valor)

    def imagem_proporcional(path, max_width, max_height):
        img_reader = ImageReader(str(path))
        largura_img, altura_img = img_reader.getSize()
        escala = min(max_width / largura_img, max_height / altura_img)
        return Image(str(path), width=largura_img * escala, height=altura_img * escala)

    # ==================== ESTILOS ====================
    style_empresa = ParagraphStyle(
        name="EmpresaA6",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=11,
        textColor=cor_primaria_escura,
        alignment=TA_LEFT
    )

    style_sub = ParagraphStyle(
        name="SubA6",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=7.5,
        textColor=cor_cinza,
        alignment=TA_LEFT
    )

    style_recibo = ParagraphStyle(
        name="ReciboA6",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=10,
        textColor=cor_primaria_escura,
        alignment=TA_CENTER
    )

    style_recibo_small = ParagraphStyle(
        name="ReciboSmallA6",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=5.8,
        leading=6.5,
        textColor=cor_primaria_escura,
        alignment=TA_CENTER
    )

    style_secao = ParagraphStyle(
        name="SecaoA6",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8,
        textColor=cor_primaria_escura,
        alignment=TA_LEFT,
        spaceAfter=2
    )

    style_normal = ParagraphStyle(
        name="NormalA6",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.6,
        leading=7.8,
        textColor=cor_texto
    )

    style_bold = ParagraphStyle(
        name="BoldA6",
        parent=style_normal,
        fontName="Helvetica-Bold",
        textColor=cor_texto
    )

    style_produto = ParagraphStyle(
        name="ProdutoA6",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.2,
        leading=7.1,
        textColor=cor_texto
    )

    style_produto_right = ParagraphStyle(
        name="ProdutoRightA6",
        parent=style_produto,
        alignment=TA_RIGHT
    )

    style_footer = ParagraphStyle(
        name="FooterA6",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=5.7,
        leading=6.5,
        alignment=TA_CENTER,
        textColor=cor_cinza
    )

    style_pix_title = ParagraphStyle(
        name="PixTitleA6",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.2,
        leading=9,
        alignment=TA_CENTER,
        textColor=cor_primaria_escura
    )

    style_pix_small = ParagraphStyle(
        name="PixSmallA6",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=5.8,
        leading=6.6,
        alignment=TA_CENTER,
        textColor=cor_cinza
    )

    style_obrigado = ParagraphStyle(
        name="ObrigadoA6",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8,
        alignment=TA_CENTER,
        textColor=cor_primaria_escura
    )

    # ==================== MARCA D'ÁGUA ====================
    def desenhar_marca_dagua(canvas, doc_ref):
        canvas.saveState()

        if logo_path.exists():
            try:
                img_reader = ImageReader(str(logo_path))
                largura_img, altura_img = img_reader.getSize()

                max_w = 7.8 * cm
                max_h = 7.8 * cm
                escala = min(max_w / largura_img, max_h / altura_img)

                w = largura_img * escala
                h = altura_img * escala

                x = (largura_pagina - w) / 2
                y = (altura_pagina - h) / 2

                try:
                    canvas.setFillAlpha(0.055)
                except Exception:
                    pass

                canvas.drawImage(
                    img_reader,
                    x,
                    y,
                    width=w,
                    height=h,
                    mask="auto"
                )

                try:
                    canvas.setFillAlpha(1)
                except Exception:
                    pass
            except Exception:
                pass

        canvas.restoreState()

    elements = []

    # ==================== CABEÇALHO ====================
    if logo_path.exists():
        try:
            logo_topo = imagem_proporcional(logo_path, 1.25 * cm, 1.05 * cm)
        except Exception:
            logo_topo = Paragraph("LOGO", style_bold)
    else:
        logo_topo = Paragraph("LOGO", style_bold)

    empresa_info = [
        Paragraph("GRANJA AVÍCOLA CAIÇARA", style_empresa),
        Paragraph("Recibo de venda • Documento eletrônico", style_sub)
    ]

    recibo_card = Table(
        [
            [Paragraph("RECIBO", style_recibo_small)],
            [Paragraph(f"Nº {safe_text(numero_recibo)}", style_recibo)]
        ],
        colWidths=[3.25 * cm],
        rowHeights=[0.35 * cm, 0.55 * cm]
    )
    recibo_card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_primaria),
        ("BOX", (0, 0), (-1, -1), 0.5, cor_primaria_escura),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))

    header = Table(
        [[logo_topo, empresa_info, recibo_card]],
        colWidths=[1.55 * cm, 9.1 * cm, 3.45 * cm]
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(header)

    linha = Table([[""]], colWidths=[14.1 * cm], rowHeights=[0.05 * cm])
    linha.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_primaria),
    ]))
    elements.append(linha)
    elements.append(Spacer(1, 0.12 * cm))

    # ==================== DADOS DO CLIENTE ====================
    cliente_nome = dados_venda.get("cliente_nome", "")
    data_venda = dados_venda.get("data_venda", "")
    observacoes = dados_venda.get("observacoes", "")
    if not observacoes:
        observacoes = "Sem observações."

    dados_table = Table(
        [
            [
                Paragraph("<b>Cliente:</b>", style_normal),
                Paragraph(safe_text(cliente_nome), style_normal),
                Paragraph("<b>Data:</b>", style_normal),
                Paragraph(data_formatada(data_venda), style_normal),
            ],
            [
                Paragraph("<b>Obs.:</b>", style_normal),
                Paragraph(safe_text(observacoes), style_normal),
                "",
                "",
            ]
        ],
        colWidths=[1.35 * cm, 6.15 * cm, 1.0 * cm, 2.45 * cm]
    )
    dados_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), cor_fundo),
        ("BOX", (0, 0), (-1, -1), 0.35, cor_linha),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, cor_linha),
        ("SPAN", (1, 1), (3, 1)),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    # ==================== PRODUTOS COMPACTOS ====================
    produtos_data = [[
        Paragraph("<b>Produto</b>", style_produto),
        Paragraph("<b>Qtd</b>", style_produto_right),
        Paragraph("<b>Valor</b>", style_produto_right),
    ]]

    max_itens_recibo = 7
    itens_exibidos = itens[:max_itens_recibo]

    for item in itens_exibidos:
        produtos_data.append([
            Paragraph(safe_text(item.get("produto_nome", "")), style_produto),
            Paragraph(fmt_num(item.get("quantidade", 0)), style_produto_right),
            Paragraph(fmt_br(item.get("subtotal", 0)), style_produto_right),
        ])

    itens_ocultos = max(0, len(itens) - max_itens_recibo)
    if itens_ocultos > 0:
        produtos_data.append([
            Paragraph(f"+ {itens_ocultos} item(ns) adicional(is)", style_produto),
            "",
            "",
        ])

    produtos_table = Table(
        produtos_data,
        colWidths=[6.45 * cm, 1.65 * cm, 2.85 * cm],
        repeatRows=1
    )

    produtos_style = [
        ("BACKGROUND", (0, 0), (-1, 0), cor_primaria_escura),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOX", (0, 0), (-1, -1), 0.35, cor_linha),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, cor_linha),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.2),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
    ]

    for row in range(1, len(produtos_data)):
        if row % 2 == 0:
            produtos_style.append(("BACKGROUND", (0, row), (-1, row), cor_fundo_linha))

    produtos_table.setStyle(TableStyle(produtos_style))

    # ==================== TOTAIS ====================
    valor_bruto = sum(
        to_float(item.get("subtotal", 0)) +
        (to_float(item.get("desconto_unit", 0)) * to_float(item.get("quantidade", 0)))
        for item in itens
    )

    desconto_total = sum(
        to_float(item.get("desconto_unit", 0)) * to_float(item.get("quantidade", 0))
        for item in itens
    )

    valor_total = to_float(dados_venda.get("valor_total", 0))
    valor_pago = to_float(dados_venda.get("valor_pago", 0))
    valor_devendo = to_float(dados_venda.get("valor_devendo", 0))

    totais_data = [
        ["Valor bruto", fmt_br(valor_bruto)],
        ["Desconto", fmt_br(desconto_total)],
        ["Valor final", fmt_br(valor_total)],
        ["Pago", fmt_br(valor_pago)],
        ["Devedor", fmt_br(valor_devendo)],
    ]

    totais_table = Table(
        totais_data,
        colWidths=[4.0 * cm, 3.3 * cm]
    )
    totais_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.35, cor_linha),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, cor_linha),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.5),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),

        ("BACKGROUND", (0, 2), (-1, 2), cor_verde_fundo),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 2), (-1, 2), 7.5),

        ("BACKGROUND", (0, 4), (-1, 4), cor_vermelho_fundo if valor_devendo > 0 else cor_fundo),
        ("TEXTCOLOR", (0, 4), (-1, 4), cor_vermelho if valor_devendo > 0 else cor_primaria_escura),
        ("FONTNAME", (0, 4), (-1, 4), "Helvetica-Bold"),
    ]))

    # ==================== COLUNA ESQUERDA ====================
    esquerda = [
        Paragraph("Dados da venda", style_secao),
        dados_table,
        Spacer(1, 0.12 * cm),
        Paragraph("Itens", style_secao),
        produtos_table,
        Spacer(1, 0.12 * cm),
        totais_table,
    ]

    # ==================== QR PIX ====================
    pix_elements = [
        Paragraph("PAGAMENTO PIX", style_pix_title),
        Spacer(1, 0.06 * cm),
    ]

    if qrcode_pix_path.exists():
        try:
            qr_img = imagem_proporcional(qrcode_pix_path, 3.45 * cm, 3.45 * cm)
            pix_elements.append(qr_img)
        except Exception:
            pix_elements.append(Paragraph("QR Code Pix não carregado.", style_pix_small))
    else:
        pix_elements.append(Paragraph("Adicione o QR em:", style_pix_small))
        pix_elements.append(Paragraph("<b>assets/qrcode_pix.png</b>", style_pix_small))

    pix_elements.extend([
        Spacer(1, 0.06 * cm),
        Paragraph("Escaneie para pagar", style_pix_small),
        Paragraph("ou use sua chave Pix cadastrada.", style_pix_small),
        Spacer(1, 0.15 * cm),
        Paragraph("Obrigado pela preferência!", style_obrigado),
        Paragraph("Granja Avícola Caiçara", style_footer),
    ])

    pix_card = Table(
        [[pix_elements]],
        colWidths=[3.0 * cm]
    )
    pix_card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.45, cor_linha),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    # ==================== LAYOUT PRINCIPAL A6 ====================
    corpo = Table(
        [[esquerda, pix_card]],
        colWidths=[11.0 * cm, 3.1 * cm]
    )
    corpo.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))

    elements.append(corpo)
    elements.append(Spacer(1, 0.10 * cm))

    elements.append(Paragraph(
        "Documento emitido eletronicamente - não é necessária assinatura.",
        style_footer
    ))

    doc.build(
        elements,
        onFirstPage=desenhar_marca_dagua,
        onLaterPages=desenhar_marca_dagua
    )

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes