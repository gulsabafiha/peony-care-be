from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.accounts.models import User


def _section_title(text: str, styles) -> Paragraph:
    return Paragraph(text, styles["Heading2"])


def _body(text: str, styles) -> Paragraph:
    safe = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, styles["BodyText"])


def build_receiver_data_pdf(user: User) -> bytes:
    from apps.accounts.receiver_account_services import build_receiver_data_export

    data = build_receiver_data_export(user)
    profile = data["profile"]
    stats = profile["stats"]
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title="Peony Care Personal Data Export",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Meta", parent=styles["Normal"], textColor=colors.grey))
    story = [
        Paragraph("Peony Care", styles["Title"]),
        Paragraph("Personal Data Export (PDPA)", styles["Heading1"]),
        Paragraph(f"Generated: {data['exported_at']}", styles["Meta"]),
        Spacer(1, 0.4 * cm),
        _section_title("Profile", styles),
        _body(f"Name: {profile['display_name']}", styles),
        _body(f"Phone: {profile['phone']}", styles),
        _body(f"Member since: {profile['member_since']}", styles),
        _body(f"Browse radius: {profile['browse_radius_km']} km", styles),
        _body(
            f"Location services: {'On' if profile['location_services_enabled'] else 'Off'}",
            styles,
        ),
        _body(
            f"Save location history: {'On' if profile['save_location_history'] else 'Off'}",
            styles,
        ),
        Spacer(1, 0.3 * cm),
        _section_title("Activity summary", styles),
        _body(f"Meals claimed: {stats['meals']}", styles),
        _body(f"Restaurants visited: {stats['restaurants']}", styles),
        _body(f"Days active: {stats['days']}", styles),
        Spacer(1, 0.3 * cm),
    ]

    if data["claims"]:
        story.append(_section_title("Claim history", styles))
        claim_rows = [["Date", "Food", "Restaurant", "Status"]]
        for claim in data["claims"]:
            claim_rows.append(
                [
                    claim["claimed_at"][:10],
                    claim["food_name"],
                    claim["restaurant_name"],
                    claim["status"],
                ]
            )
        claim_table = Table(claim_rows, colWidths=[2.5 * cm, 5 * cm, 5 * cm, 3 * cm])
        claim_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5F5F5")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.extend([claim_table, Spacer(1, 0.3 * cm)])

    if data["location_history"]:
        story.append(_section_title("Saved locations", styles))
        for entry in data["location_history"][:20]:
            story.append(_body(f"{entry['place_name']} — {entry['area_label']}", styles))
        story.append(Spacer(1, 0.3 * cm))

    if data["notification_settings"]:
        story.append(_section_title("Notification preferences", styles))
        for key, value in data["notification_settings"].items():
            label = key.replace("_", " ").title()
            story.append(_body(f"{label}: {'On' if value else 'Off'}", styles))
        story.append(Spacer(1, 0.3 * cm))

    if data["reports_submitted"]:
        story.append(_section_title("Reports submitted", styles))
        for report in data["reports_submitted"]:
            story.append(
                _body(
                    f"{report['created_at'][:10]} — {report['food_name']} "
                    f"({report['restaurant_name']}): {report['reason']}",
                    styles,
                )
            )

    doc.build(story)
    return buffer.getvalue()
