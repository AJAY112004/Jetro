"""SpendLens dashboard-style PDF report (reportlab only — no matplotlib)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, BinaryIO

# Bump when PDF layout changes (logged at Flask startup).
PDF_BUILD_ID = "styled-v3"

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics import renderPDF
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


class _DrawingFlowable(Flowable):
    """Embed a reportlab Drawing in platypus without rasterizing."""

    def __init__(self, drawing: Drawing, width: float | None = None, height: float | None = None):
        self.drawing = drawing
        self.width = width or drawing.width
        self.height = height or drawing.height

    def wrap(self, avail_width: float, avail_height: float) -> tuple[float, float]:
        return self.width, self.height

    def draw(self) -> None:
        renderPDF.draw(self.drawing, self.canv, 0, 0)

# Palette aligned with SpendLens UI / reference dashboard
C_PRIMARY = colors.HexColor("#1e40af")
C_HEADER_BG = colors.HexColor("#1e3a8a")
C_INCOME = colors.HexColor("#16a34a")
C_EXPENSE = colors.HexColor("#dc2626")
C_SAVINGS = colors.HexColor("#2563eb")
C_SCORE = colors.HexColor("#7c3aed")
C_MUTED = colors.HexColor("#64748b")
C_BORDER = colors.HexColor("#e2e8f0")
C_CARD_BG = colors.HexColor("#f8fafc")
C_ALERT_BG = colors.HexColor("#fef2f2")
C_INSIGHT_BG = colors.HexColor("#eff6ff")
C_REBAL_BG = colors.HexColor("#dbeafe")
C_WHITE = colors.white

CHART_COLORS = [
    "#3b82f6",
    "#22c55e",
    "#ef4444",
    "#eab308",
    "#a855f7",
    "#f97316",
    "#06b6d4",
    "#ec4899",
    "#84cc16",
    "#64748b",
]

_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"


def _register_fonts() -> None:
    """Prefer Arial on Windows so INR symbol (₹) renders in PDF."""
    global _FONT, _FONT_BOLD
    candidates = [
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for regular, bold in candidates:
        try:
            import os

            if os.path.isfile(regular):
                pdfmetrics.registerFont(TTFont("SpendSans", regular))
                _FONT = "SpendSans"
                if os.path.isfile(bold):
                    pdfmetrics.registerFont(TTFont("SpendSans-Bold", bold))
                    _FONT_BOLD = "SpendSans-Bold"
                else:
                    _FONT_BOLD = "SpendSans"
                return
        except Exception:
            continue


_register_fonts()


def _inr(n: float) -> str:
    val = float(n)
    sign = "-" if val < 0 else ""
    return f"{sign}₹{abs(val):,.0f}"


def _clean_text(text: str) -> str:
    return str(text).replace("₹", "₹")


def _category_status(pct: float) -> tuple[str, colors.Color]:
    if pct >= 35:
        return "High", colors.HexColor("#dc2626")
    if pct >= 15:
        return "Moderate", colors.HexColor("#ea580c")
    if pct >= 8:
        return "Normal", colors.HexColor("#2563eb")
    return "Low", colors.HexColor("#16a34a")


def _derive_stats(report: dict) -> dict[str, Any]:
    trend = report.get("daily_spend_trend") or []
    s = report.get("spend_summary") or {}
    expenses = float(s.get("total_expenses") or 0)
    stats = report.get("stats") or {}
    n_days = max(1, len(trend))
    avg_daily = expenses / n_days if trend else 0.0

    hi = stats.get("highest_spend_day")
    lo = stats.get("lowest_spend_day")
    if not hi and trend:
        hi = max(trend, key=lambda x: float(x.get("spend") or 0))
    if not lo and trend:
        lo = min(trend, key=lambda x: float(x.get("spend") or 0))

    def _fmt_day(row: dict | str | None) -> str:
        if not row:
            return "—"
        if isinstance(row, str):
            return row
        d = str(row.get("date") or "")
        spend = _inr(row.get("spend") or 0)
        if len(d) >= 10:
            try:
                dt = datetime.strptime(d[:10], "%Y-%m-%d")
                return f"{spend} ({dt.strftime('%b %d')})"
            except ValueError:
                pass
        return spend

    return {
        "transaction_count": stats.get("transaction_count") or report.get("transaction_count") or len(trend) * 5,
        "avg_daily_spend": stats.get("avg_daily_spend") or round(avg_daily, 0),
        "highest_spend_day": _fmt_day(hi),
        "lowest_spend_day": _fmt_day(lo),
        "savings_rate_pct": s.get("savings_rate_pct", 0),
    }


def _pie_chart_drawing(categories: list[dict], width: float = 220, height: float = 160) -> Drawing:
    d = Drawing(width, height)
    if not categories:
        d.add(String(width / 2 - 30, height / 2, "No data", fontName=_FONT, fontSize=9))
        return d

    pie = Pie()
    pie.x = 10
    pie.y = 15
    pie.width = min(95, height - 30)
    pie.height = min(95, height - 30)
    pie.data = [float(c.get("amount") or 0) for c in categories[:8]]
    pie.labels = None
    pie.slices.strokeWidth = 0.5
    pie.slices.strokeColor = colors.white
    for i, hex_c in enumerate(CHART_COLORS):
        if i < len(pie.data):
            pie.slices[i].fillColor = colors.HexColor(hex_c)
    d.add(pie)
    return d


def _line_chart_drawing(trend: list[dict], width: float = 280, height: float = 160) -> Drawing:
    d = Drawing(width, height)
    if not trend:
        d.add(String(width / 2 - 30, height / 2, "No trend data", fontName=_FONT, fontSize=9))
        return d

    points = trend
    if len(points) > 20:
        step = max(1, len(points) // 20)
        points = points[::step]

    values = [float(p.get("spend") or 0) for p in points]
    chart = LinePlot()
    chart.x = 40
    chart.y = 22
    chart.width = width - 55
    chart.height = height - 48
    chart.data = [[(i, v) for i, v in enumerate(values)]]
    chart.lines[0].strokeColor = colors.HexColor("#3b82f6")
    chart.lines[0].strokeWidth = 1.5
    chart.lines[0].symbol = None
    chart.xValueAxis.valueMin = 0
    chart.xValueAxis.labels.fontName = _FONT
    chart.xValueAxis.labels.fontSize = 6
    chart.yValueAxis.valueMin = 0
    chart.yValueAxis.labels.fontName = _FONT
    chart.yValueAxis.labels.fontSize = 6
    d.add(chart)
    return d


def _drawing_flowable(drawing: Drawing, max_w: float) -> _DrawingFlowable:
    scale = max_w / max(drawing.width, 1)
    return _DrawingFlowable(drawing, drawing.width * scale, drawing.height * scale)


def _section_header(title: str, width: float) -> Table:
    t = Table([[Paragraph(f"<b>{title.upper()}</b>", _style("section_hdr"))]], colWidths=[width])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), C_HEADER_BG),
                ("TEXTCOLOR", (0, 0), (-1, -1), C_WHITE),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return t


def _style(name: str) -> ParagraphStyle:
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "title",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=14,
            textColor=colors.HexColor("#0f172a"),
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=base["Normal"],
            fontName=_FONT,
            fontSize=7,
            textColor=C_MUTED,
            leading=9,
        ),
        "kpi_lbl": ParagraphStyle(
            "kpi_lbl",
            parent=base["Normal"],
            fontName=_FONT,
            fontSize=7,
            textColor=C_MUTED,
            alignment=TA_CENTER,
        ),
        "kpi_val": ParagraphStyle(
            "kpi_val",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=13,
            alignment=TA_CENTER,
            leading=15,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName=_FONT,
            fontSize=8,
            textColor=colors.HexColor("#334155"),
            leading=11,
        ),
        "alert": ParagraphStyle(
            "alert",
            parent=base["Normal"],
            fontName=_FONT,
            fontSize=8,
            textColor=colors.HexColor("#991b1b"),
            leading=11,
        ),
        "insight": ParagraphStyle(
            "insight",
            parent=base["Normal"],
            fontName=_FONT,
            fontSize=8,
            textColor=colors.HexColor("#1e40af"),
            leading=11,
        ),
        "section_hdr": ParagraphStyle(
            "section_hdr",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=8,
            textColor=C_WHITE,
        ),
        "badge": ParagraphStyle(
            "badge",
            parent=base["Normal"],
            fontName=_FONT_BOLD,
            fontSize=7,
            alignment=TA_CENTER,
        ),
    }
    return styles[name]


def _kpi_card(label: str, value: str, value_color: colors.Color, badge: str | None = None) -> Table:
    rows = [
        [Paragraph(label.upper(), _style("kpi_lbl"))],
        [
            Paragraph(
                f"<b>{value}</b>",
                ParagraphStyle("kv", parent=_style("kpi_val"), textColor=value_color),
            )
        ],
    ]
    if badge:
        sc = report_savings_colour(badge)
        rows.append(
            [
                Paragraph(
                    f"<b>{badge}</b>",
                    ParagraphStyle("kb", parent=_style("kpi_lbl"), textColor=sc),
                )
            ]
        )
    t = Table(rows, colWidths=[1.85 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), C_WHITE),
                ("BOX", (0, 0), (-1, -1), 0.75, C_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return t


def report_savings_colour(label: str) -> colors.Color:
    low = label.lower()
    if "critical" in low or "poor" in low:
        return C_EXPENSE
    if "good" in low or "excellent" in low:
        return C_INCOME
    return colors.HexColor("#ca8a04")


def _card_table(inner: Table, width: float) -> Table:
    wrap = Table([[inner]], colWidths=[width])
    wrap.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), C_WHITE),
                ("BOX", (0, 0), (-1, -1), 0.75, C_BORDER),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return wrap


def build_styled_pdf(report: dict, buffer: BinaryIO) -> None:
    """Render dashboard PDF into *buffer* (file-like). Caller owns io.BytesIO()."""
    page_w, page_h = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=28,
        rightMargin=28,
        topMargin=24,
        bottomMargin=24,
        title="SpendLens Report",
    )

    s = report.get("spend_summary") or {}
    sc = report.get("savings_score") or {}
    cats = report.get("category_breakdown") or []
    trend = report.get("daily_spend_trend") or []
    stats = _derive_stats(report)
    generated = datetime.now().strftime("%d %B %Y | %I:%M %p")
    month = report.get("month_label") or "Report"

    usable_w = page_w - doc.leftMargin - doc.rightMargin
    half_w = (usable_w - 12) / 2
    kpi_w = (usable_w - 36) / 4

    story: list[Any] = []

    # --- Header ---
    header = Table(
        [
            [
                Paragraph("REPORT PERIOD", _style("muted")),
                Paragraph("GENERATED ON", _style("muted")),
            ],
            [
                Paragraph(f"<b>{month}</b>", _style("title")),
                Paragraph(f"<b>{generated}</b>", ParagraphStyle("gen", parent=_style("body"), alignment=TA_RIGHT)),
            ],
        ],
        colWidths=[usable_w * 0.55, usable_w * 0.45],
    )
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header)
    story.append(Spacer(1, 10))

    # --- KPI row ---
    score_label = sc.get("label") or ""
    kpis = Table(
        [
            [
                _kpi_card("Total Income", _inr(s.get("total_income", 0)), C_INCOME),
                _kpi_card("Total Expenses", _inr(s.get("total_expenses", 0)), C_EXPENSE),
                _kpi_card("Net Savings", _inr(s.get("net_savings", 0)), C_SAVINGS),
                _kpi_card(
                    "Savings Score",
                    f"{sc.get('score', 0)}/100",
                    C_SCORE,
                    badge=score_label if score_label else None,
                ),
            ]
        ],
        colWidths=[kpi_w] * 4,
        hAlign="CENTER",
    )
    kpis.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(kpis)
    story.append(Spacer(1, 10))

    # --- Charts row ---
    pie_d = _pie_chart_drawing(cats[:8], width=200, height=150)
    line_d = _line_chart_drawing(trend, width=300, height=150)

    legend_rows = []
    for i, c in enumerate(cats[:6]):
        colour = CHART_COLORS[i % len(CHART_COLORS)]
        legend_rows.append(
            [
                Paragraph(
                    f'<font color="{colour}">●</font> <b>{c.get("category", "")}</b>',
                    _style("body"),
                ),
                Paragraph(_inr(c.get("amount", 0)), _style("body")),
                Paragraph(f"{c.get('pct', 0):.0f}%", _style("muted")),
            ]
        )
    legend = Table(legend_rows, colWidths=[half_w * 0.45, half_w * 0.32, half_w * 0.15])
    legend.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )

    cat_inner = Table(
        [
            [_section_header("Category Breakdown", half_w - 16)],
            [
                Table(
                    [[_drawing_flowable(pie_d, 1.1 * inch), legend]],
                    colWidths=[1.2 * inch, half_w - 1.4 * inch],
                )
            ],
            [
                Table(
                    [
                        [
                            Paragraph("Total Expenses", _style("muted")),
                            Paragraph(
                                f"<b>{_inr(s.get('total_expenses', 0))}</b>",
                                ParagraphStyle("te", parent=_style("body"), textColor=C_SAVINGS, alignment=TA_RIGHT),
                            ),
                        ]
                    ],
                    colWidths=[(half_w - 24) * 0.5, (half_w - 24) * 0.5],
                )
            ],
        ],
        colWidths=[half_w - 16],
    )
    cat_card = _card_table(cat_inner, half_w)

    line_inner = Table(
        [
            [_section_header("Daily Spend Trend", half_w - 16)],
            [[_drawing_flowable(line_d, half_w - 40)]],
        ],
        colWidths=[half_w - 16],
    )
    line_card = _card_table(line_inner, half_w)

    charts_row = Table([[cat_card, line_card]], colWidths=[half_w, half_w], spaceBefore=0, spaceAfter=0)
    charts_row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(charts_row)
    story.append(Spacer(1, 10))

    # --- Alerts & insights ---
    anomalies = report.get("anomalies") or []
    insights = report.get("ai_insights") or []

    alert_body = (
        [Paragraph(f"! {_clean_text(a.get('message', ''))}", _style("alert")) for a in anomalies[:4]]
        if anomalies
        else [Paragraph("No anomalies flagged this period.", _style("body"))]
    )
    insight_body = (
        [Paragraph(f"- {_clean_text(t)}", _style("insight")) for t in insights[:4]]
        if insights
        else [Paragraph("No additional insights.", _style("body"))]
    )

    def _insight_card(title: str, icon: str, body: list, bg: colors.Color, title_color: colors.Color) -> Table:
        inner = Table(
            [
                [Paragraph(f"{icon} <b>{title.upper()}</b>", ParagraphStyle("it", parent=_style("body"), textColor=title_color))],
                body,
            ],
            colWidths=[half_w - 24],
        )
        wrap = Table([[inner]], colWidths=[half_w])
        wrap.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), bg),
                    ("BOX", (0, 0), (-1, -1), 0.75, C_BORDER),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return wrap

    insights_row = Table(
        [
            [
                _insight_card("Anomaly Alerts", "!", alert_body, C_ALERT_BG, C_EXPENSE),
                _insight_card("AI Insights", "i", insight_body, C_INSIGHT_BG, C_PRIMARY),
            ]
        ],
        colWidths=[half_w, half_w],
    )
    story.append(insights_row)
    story.append(Spacer(1, 8))

    # --- Rebalancing ---
    rebal = report.get("rebalancing_recommendation") or ""
    rebal_tbl = Table(
        [[Paragraph(f"<b>RECOMMENDATIONS</b> — {_clean_text(rebal)}", _style("insight"))]],
        colWidths=[usable_w],
    )
    rebal_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), C_REBAL_BG),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#93c5fd")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(rebal_tbl)
    story.append(Spacer(1, 10))

    # --- Bottom tables ---
    rate = float(stats.get("savings_rate_pct") or 0)
    rate_color = C_EXPENSE if rate < 0 else C_INCOME
    summary_rows = [
        ["Total Transactions", str(int(stats.get("transaction_count", 0)))],
        ["Average Daily Spend", _inr(stats.get("avg_daily_spend", 0))],
        ["Highest Spend Day", str(stats.get("highest_spend_day", "—"))],
        ["Lowest Spend Day", str(stats.get("lowest_spend_day", "—"))],
        ["Savings Rate", f"{rate:.0f}%"],
    ]
    sum_data = [
        [Paragraph(f"<b>{k}</b>", _style("body")), Paragraph(str(v), ParagraphStyle("sv", parent=_style("body"), textColor=rate_color if k == "Savings Rate" else colors.HexColor("#0f172a"), alignment=TA_RIGHT))]
        for k, v in summary_rows
    ]
    sum_inner = Table(
        [[_section_header("Spend Summary", half_w - 16)], [Table(sum_data, colWidths=[(half_w - 32) * 0.62, (half_w - 32) * 0.38])]],
        colWidths=[half_w - 16],
    )
    sum_card = _card_table(sum_inner, half_w)

    cat_rows = [["Category", "%", "Status"]]
    for c in cats[:5]:
        label, badge_c = _category_status(float(c.get("pct") or 0))
        cat_rows.append(
            [
                Paragraph(c.get("category", ""), _style("body")),
                Paragraph(f"{c.get('pct', 0):.0f}%", _style("body")),
                Paragraph(f"<b>{label}</b>", ParagraphStyle("bdg", parent=_style("badge"), textColor=badge_c)),
            ]
        )
    cat_tbl = Table(cat_rows, colWidths=[(half_w - 32) * 0.5, (half_w - 32) * 0.2, (half_w - 32) * 0.3])
    cat_tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_CARD_BG),
                ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, C_BORDER),
            ]
        )
    )
    cat_ins_inner = Table(
        [[_section_header("Category Insights", half_w - 16)], [cat_tbl]],
        colWidths=[half_w - 16],
    )
    cat_ins_card = _card_table(cat_ins_inner, half_w)

    bottom = Table([[sum_card, cat_ins_card]], colWidths=[half_w, half_w])
    story.append(bottom)

    doc.build(story)
