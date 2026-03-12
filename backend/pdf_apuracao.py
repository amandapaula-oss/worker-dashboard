"""
Gerador de PDF — Memória de Cálculo de Bônus Q4 2025
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

# ── Paleta de cores FCamara ──────────────────────────────────────────────────
AZUL      = colors.HexColor("#2d50a0")
AZUL_DARK = colors.HexColor("#1a2e5a")
VERDE     = colors.HexColor("#52c41a")
AMARELO   = colors.HexColor("#faad14")
VERMELHO  = colors.HexColor("#ff4d4f")
CINZA     = colors.HexColor("#f4f6fb")
CINZA_BD  = colors.HexColor("#dde3f0")
BRANCO    = colors.white


def _cor_ating(v: float):
    if v >= 1.0: return VERDE
    if v >= 0.5: return AMARELO
    return VERMELHO


def _fmt(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _pct_dir(v: float) -> str:
    """Para valores já em percentual (ex: 29.9)"""
    return f"{v:.2f}%"


def _tbl_style(header_rows=1, zebra=True):
    style = [
        ("BACKGROUND",  (0, 0), (-1, header_rows - 1), AZUL),
        ("TEXTCOLOR",   (0, 0), (-1, header_rows - 1), BRANCO),
        ("FONTNAME",    (0, 0), (-1, header_rows - 1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, header_rows), (-1, -1),
         [CINZA, BRANCO] if zebra else [BRANCO]),
        ("GRID",        (0, 0), (-1, -1), 0.4, CINZA_BD),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    return TableStyle(style)


def gerar_pdf_ae(dados: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    styles = getSampleStyleSheet()
    story = []

    titulo = ParagraphStyle("titulo", fontSize=16, textColor=AZUL_DARK,
                             fontName="Helvetica-Bold", spaceAfter=2)
    sub    = ParagraphStyle("sub",    fontSize=9,  textColor=colors.grey,
                             spaceAfter=12)
    secao  = ParagraphStyle("secao",  fontSize=11, textColor=AZUL,
                             fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
    normal = ParagraphStyle("normal", fontSize=9,  spaceAfter=4)
    bold9  = ParagraphStyle("bold9",  fontSize=9,  fontName="Helvetica-Bold")
    total_s= ParagraphStyle("total",  fontSize=13, fontName="Helvetica-Bold",
                             textColor=VERDE, alignment=TA_RIGHT)

    # ── Cabeçalho ──────────────────────────────────────────────────────────────
    story.append(Paragraph("FCamara — Memória de Cálculo de Bônus", titulo))
    story.append(Paragraph(
        f"<b>{dados['nome']}</b> &nbsp;|&nbsp; {dados['posicao']} &nbsp;|&nbsp; "
        f"Contrato: {dados['contrato']} &nbsp;|&nbsp; {dados['periodo']}",
        sub
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=AZUL, spaceAfter=12))

    # ── Dados gerais ───────────────────────────────────────────────────────────
    story.append(Paragraph("1. Dados Cadastrais e Parâmetros", secao))
    params_data = [
        ["Campo", "Valor"],
        ["Nome completo", dados["nome"]],
        ["Posição", dados["posicao"]],
        ["Contrato", dados["contrato"]],
        ["Salário Q4", _fmt(dados["salario_q4"])],
        ["Peso Receita", _pct(dados["peso_receita"])],
        ["Peso MB%",     _pct(dados["peso_mb"])],
        ["Período apurado", dados["periodo"]],
        ["Trigger Receita Q4", "85%"],
        ["Trigger MB Q4", "98,5% da meta MB%"],
    ]
    t = Table(params_data, colWidths=[6*cm, 10*cm])
    t.setStyle(_tbl_style())
    story.append(t)

    # ── Visão geral ────────────────────────────────────────────────────────────
    story.append(Paragraph("2. Visão Geral — Meta vs. Realizado", secao))

    ov_data = [
        ["Métrica", "Meta", "Realizado", "Atingimento", "Status"],
        [
            "Receita Total",
            _fmt(dados["budget_rec_total"]),
            _fmt(dados["real_rec_total"]),
            _pct(dados["ating_rec_total"]),
            "✓ Atingido" if dados["ating_rec_total"] >= 1 else
            ("⚠ Parcial" if dados["ating_rec_total"] > 0 else "✗ Abaixo"),
        ],
        [
            "MB% Total",
            _pct_dir(dados["budget_mb_pct"]),
            _pct_dir(dados["real_mb_pct"]),
            _pct(dados["ating_mb_total"]),
            "✓ Atingido" if dados["ating_mb_total"] >= 1 else
            ("⚠ Parcial" if dados["ating_mb_total"] > 0 else "✗ Abaixo"),
        ],
    ]
    t = Table(ov_data, colWidths=[4.5*cm, 3.5*cm, 3.5*cm, 3*cm, 2.5*cm])
    ts = _tbl_style()
    for i, row in enumerate(ov_data[1:], 1):
        status = row[4]
        cor = VERDE if "✓" in status else (AMARELO if "⚠" in status else VERMELHO)
        ts.add("TEXTCOLOR", (4, i), (4, i), cor)
        ts.add("FONTNAME",  (4, i), (4, i), "Helvetica-Bold")
    t.setStyle(ts)
    story.append(t)

    # ── Fórmula de cálculo ────────────────────────────────────────────────────
    story.append(Paragraph("3. Fórmula de Cálculo", secao))
    story.append(Paragraph(
        "Bônus = Quantidade (1 quarter) × Peso WS × Atingimento × Salário × Peso Meta",
        normal
    ))
    story.append(Paragraph(
        "Atingimento: 0% se abaixo do trigger | 50%→100% linear entre trigger e 100% da meta | 100% na meta",
        normal
    ))
    story.append(Paragraph(
        "Trigger MB (somente Apps): Realizado MB% ≥ 98,5% da Meta MB% para ativar o bônus de MB.",
        normal
    ))

    # ── Detalhe por Workstream ────────────────────────────────────────────────
    if dados.get("detalhe_ws"):
        story.append(Paragraph("4. Detalhe por Workstream", secao))

        ws_data = [[
            "WS", "Peso WS",
            "Meta Rec.", "Real. Rec.", "Ating. Rec.",
            "Meta MB%", "Real MB%", "Ating. MB",
            "Bônus Rec.", "Bônus MB", "Bônus WS"
        ]]
        for ws in dados["detalhe_ws"]:
            ws_data.append([
                ws["ws"].upper(),
                _pct(ws["peso_ws"]),
                _fmt(ws["budget_rec"]),
                _fmt(ws["real_rec"]),
                _pct(ws["ating_rec"]),
                _pct_dir(ws["budget_mb_pct"]),
                _pct_dir(ws["real_mb_pct"]),
                _pct(ws["ating_mb"]),
                _fmt(ws["bonus_rec"]),
                _fmt(ws["bonus_mb"]),
                _fmt(ws["bonus_ws"]),
            ])
        # Linha de total
        ws_data.append([
            "TOTAL", "",
            _fmt(dados["budget_rec_total"]),
            _fmt(dados["real_rec_total"]),
            _pct(dados["ating_rec_total"]),
            _pct_dir(dados["budget_mb_pct"]),
            _pct_dir(dados["real_mb_pct"]),
            _pct(dados["ating_mb_total"]),
            _fmt(sum(w["bonus_rec"] for w in dados["detalhe_ws"])),
            _fmt(sum(w["bonus_mb"] for w in dados["detalhe_ws"])),
            _fmt(dados["bonus_total"]),
        ])

        colw = [1.5*cm, 1.5*cm, 2.2*cm, 2.2*cm, 1.8*cm,
                1.8*cm, 1.8*cm, 1.8*cm, 2.2*cm, 2.2*cm, 2.2*cm]
        t = Table(ws_data, colWidths=colw)
        ts = _tbl_style()
        # Linha total em negrito com fundo azul claro
        n = len(ws_data) - 1
        ts.add("BACKGROUND", (0, n), (-1, n), colors.HexColor("#dce6f7"))
        ts.add("FONTNAME",   (0, n), (-1, n), "Helvetica-Bold")
        t.setStyle(ts)
        story.append(t)

    # ── Total ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=CINZA_BD))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Bônus Total Q4 2025: {_fmt(dados['bonus_total'])}", total_s))

    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph(
        "<font color='grey' size='7'>Documento gerado automaticamente pelo sistema FCamara FP&amp;A — "
        "Cálculo referente ao Q4 2025 (out-dez/2025)</font>",
        ParagraphStyle("rodape", fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buf.getvalue()


def gerar_pdf_diretor(dados: dict) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    styles = getSampleStyleSheet()
    story = []

    titulo = ParagraphStyle("titulo", fontSize=16, textColor=AZUL_DARK,
                             fontName="Helvetica-Bold", spaceAfter=2)
    sub    = ParagraphStyle("sub",    fontSize=9,  textColor=colors.grey, spaceAfter=12)
    secao  = ParagraphStyle("secao",  fontSize=11, textColor=AZUL,
                             fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
    normal = ParagraphStyle("normal", fontSize=9,  spaceAfter=4)
    total_s= ParagraphStyle("total",  fontSize=13, fontName="Helvetica-Bold",
                             textColor=VERDE, alignment=TA_RIGHT)

    # ── Cabeçalho ──────────────────────────────────────────────────────────────
    story.append(Paragraph("FCamara — Memória de Cálculo de Bônus", titulo))
    story.append(Paragraph(
        f"<b>{dados['nome']}</b> &nbsp;|&nbsp; DIRETOR &nbsp;|&nbsp; "
        f"Vertical: {dados.get('vertical','N/D')} &nbsp;|&nbsp; "
        f"Contrato: {dados['contrato']} &nbsp;|&nbsp; {dados['periodo']}",
        sub
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=AZUL, spaceAfter=12))

    # ── Gate MC ────────────────────────────────────────────────────────────────
    gate_ok = dados.get("mc_gate", 0) == 1
    gate_txt = "✓ GATE MC ATINGIDO — Todas as métricas apuradas" if gate_ok \
               else "✗ GATE MC NÃO ATINGIDO — Sem apuração de TCV e Receita"
    gate_cor = VERDE if gate_ok else VERMELHO
    gate_bg  = colors.HexColor("#f6ffed") if gate_ok else colors.HexColor("#fff2f0")

    gate_tbl = Table([[Paragraph(f"<b>{gate_txt}</b>",
                                 ParagraphStyle("g", fontSize=10, textColor=gate_cor))]],
                     colWidths=[16.4*cm])
    gate_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), gate_bg),
        ("BOX", (0, 0), (-1, -1), 1.5, gate_cor),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(gate_tbl)
    story.append(Spacer(1, 0.4*cm))

    # ── Parâmetros ────────────────────────────────────────────────────────────
    story.append(Paragraph("1. Dados Cadastrais e Parâmetros", secao))
    params_data = [
        ["Campo", "Valor"],
        ["Nome", dados["nome"]],
        ["Vertical", dados.get("vertical", "N/D")],
        ["Contrato", dados["contrato"]],
        ["Salário Q4", _fmt(dados["salario_q4"])],
        ["Peso TCV", _pct(dados["peso_tcv"])],
        ["Peso Receita", _pct(dados["peso_receita"])],
        ["Peso MC%", _pct(dados["peso_mc"])],
        ["Trigger Receita/TCV Q4", "85%"],
        ["Trigger MC% Q4", "Meta MC% − 1,5 p.p."],
        ["Gate Mestre", "MC% deve atingir o trigger para liberar TCV e Receita"],
    ]
    t = Table(params_data, colWidths=[6*cm, 10*cm])
    t.setStyle(_tbl_style())
    story.append(t)

    # ── Métricas ──────────────────────────────────────────────────────────────
    story.append(Paragraph("2. Meta vs. Realizado por Métrica", secao))

    def status_str(v): return "✓ Atingido" if v >= 1 else ("⚠ Parcial" if v > 0 else "✗ Abaixo")

    metricas_data = [
        ["Métrica", "Peso", "Meta", "Realizado", "Ating.", "Bônus", "Status"],
        [
            "TCV",
            _pct(dados["peso_tcv"]),
            _fmt(dados["budget_tcv_q4"]),
            _fmt(dados["real_tcv_q4"]) + "\n(*Salesforce)",
            _pct(dados["ating_tcv"]),
            _fmt(dados["bonus_tcv"]),
            status_str(dados["ating_tcv"]),
        ],
        [
            "Receita",
            _pct(dados["peso_receita"]),
            _fmt(dados["budget_rec_q4"]),
            _fmt(dados["real_rec_q4"]),
            _pct(dados["ating_rec"]),
            _fmt(dados["bonus_rec"]),
            status_str(dados["ating_rec"]),
        ],
        [
            "MC% (Gate)",
            _pct(dados["peso_mc"]),
            _pct_dir(dados["budget_mc_pct"]),
            _pct_dir(dados["real_mc_pct"]),
            _pct(dados["ating_mc"]),
            _fmt(dados["bonus_mc"]),
            status_str(dados["ating_mc"]) + (" 🔑" if gate_ok else " 🔒"),
        ],
        [
            "TOTAL", "",  "", "", "",
            _fmt(dados["bonus_total"]),
            "",
        ],
    ]

    t = Table(metricas_data, colWidths=[3*cm, 1.8*cm, 3.2*cm, 3.2*cm, 2*cm, 2.5*cm, 2.5*cm])
    ts = _tbl_style()
    for i, row in enumerate(metricas_data[1:], 1):
        status = row[6]
        cor = VERDE if "✓" in status else (AMARELO if "⚠" in status else VERMELHO)
        ts.add("TEXTCOLOR", (6, i), (6, i), cor)
        ts.add("FONTNAME",  (6, i), (6, i), "Helvetica-Bold")
    # Linha total
    n = len(metricas_data) - 1
    ts.add("BACKGROUND", (0, n), (-1, n), colors.HexColor("#dce6f7"))
    ts.add("FONTNAME",   (0, n), (-1, n), "Helvetica-Bold")
    t.setStyle(ts)
    story.append(t)

    # ── Nota TCV ─────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(
        "(*) TCV realizado requer integração com base Salesforce — valor pendente de atualização.",
        ParagraphStyle("nota", fontSize=7.5, textColor=colors.grey)
    ))

    # ── Fórmula ───────────────────────────────────────────────────────────────
    story.append(Paragraph("3. Fórmula de Cálculo", secao))
    story.append(Paragraph(
        "Bônus por métrica = 1 quarter × 1,0 (peso WS) × Atingimento × Salário × Peso Meta", normal
    ))
    story.append(Paragraph(
        "Gate Mestre: se MC% < (Meta MC% − 1,5 p.p.), bônus de TCV e Receita = R$ 0,00.", normal
    ))

    # ── Total ─────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 0.5*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=CINZA_BD))
    story.append(Spacer(1, 0.3*cm))
    story.append(Paragraph(f"Bônus Total Q4 2025: {_fmt(dados['bonus_total'])}", total_s))

    story.append(Spacer(1, 0.8*cm))
    story.append(Paragraph(
        "<font color='grey' size='7'>Documento gerado automaticamente pelo sistema FCamara FP&amp;A — "
        "Cálculo referente ao Q4 2025 (out-dez/2025)</font>",
        ParagraphStyle("rodape", fontSize=7, textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buf.getvalue()


def gerar_pdf(dados: dict) -> bytes:
    if dados.get("posicao") == "DIRETOR":
        return gerar_pdf_diretor(dados)
    return gerar_pdf_ae(dados)
