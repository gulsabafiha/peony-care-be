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
        title="UduFood Personal Data Export",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Meta", parent=styles["Normal"], textColor=colors.grey))
    story = [
        Paragraph("UduFood", styles["Title"]),
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


def build_restaurant_data_pdf(user: User) -> bytes:
    from apps.accounts.restaurant_account_services import build_restaurant_data_export

    data = build_restaurant_data_export(user)
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
        title="UduFood Restaurant Data Export",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Meta", parent=styles["Normal"], textColor=colors.grey))
    story = [
        Paragraph("UduFood", styles["Title"]),
        Paragraph("Restaurant Data Export (PDPA)", styles["Heading1"]),
        Paragraph(f"Generated: {data['exported_at']}", styles["Meta"]),
        Spacer(1, 0.4 * cm),
        _section_title("Profile", styles),
        _body(f"Name: {profile['name']}", styles),
        _body(f"Phone: {profile['phone']}", styles),
        _body(f"UEN: {profile['uen']}", styles),
        _body(f"Address: {profile['address']}", styles),
        _body(f"Contact: {profile['contact_name']}", styles),
        _body(f"Email: {profile['contact_email'] or '—'}", styles),
        _body(f"Member since: {profile['member_since']}", styles),
        Spacer(1, 0.3 * cm),
        _section_title("Impact summary", styles),
        _body(f"People fed: {stats['people_fed']}", styles),
        _body(f"Donations posted: {stats['donations_posted']}", styles),
        _body(
            f"Claim rate: {stats['claim_rate_pct']}%"
            if stats["claim_rate_pct"] is not None
            else "Claim rate: —",
            styles,
        ),
        Spacer(1, 0.3 * cm),
    ]

    analytics = data.get("analytics") or {}
    if analytics:
        story.extend(
            [
                _section_title("Analytics", styles),
                _body(f"Sponsored total: SGD {analytics.get('sponsored_sgd', '0.00')}", styles),
                Spacer(1, 0.3 * cm),
            ]
        )

    if data["donations"]:
        story.append(_section_title("Donation history", styles))
        donation_rows = [["Date", "Food", "Qty", "Status"]]
        for food in data["donations"][:50]:
            donation_rows.append(
                [
                    food["created_at"][:10],
                    food["name"],
                    str(food["quantity_original"]),
                    food["list_status"],
                ]
            )
        donation_table = Table(donation_rows, colWidths=[2.5 * cm, 7 * cm, 2 * cm, 3.5 * cm])
        donation_table.setStyle(
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
        story.extend([donation_table, Spacer(1, 0.3 * cm)])

    if data["claims"]:
        story.append(_section_title("Claim history", styles))
        claim_rows = [["Date", "Food", "Status", "Qty"]]
        for claim in data["claims"][:50]:
            claim_rows.append(
                [
                    claim["claimed_at"][:10],
                    claim["food_name"],
                    claim["status"],
                    str(claim["quantity_claimed"]),
                ]
            )
        claim_table = Table(claim_rows, colWidths=[2.5 * cm, 7 * cm, 3.5 * cm, 2 * cm])
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

    sponsored_orders = data.get("sponsored_orders") or []
    if sponsored_orders:
        story.append(_section_title("Sponsored orders / payouts", styles))
        order_rows = [["Date", "Amount", "Status", "Donor"]]
        for order in sponsored_orders[:50]:
            order_rows.append(
                [
                    order["ordered_at"][:10],
                    order["total_amount_sgd"],
                    order["status"],
                    order.get("donor_label") or "—",
                ]
            )
        order_table = Table(order_rows, colWidths=[2.5 * cm, 3 * cm, 3 * cm, 6.5 * cm])
        order_table.setStyle(
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
        story.extend([order_table, Spacer(1, 0.3 * cm)])

    if data["notification_settings"]:
        story.append(_section_title("Notification preferences", styles))
        for key, value in data["notification_settings"].items():
            label = key.replace("_", " ").title()
            story.append(_body(f"{label}: {'On' if value else 'Off'}", styles))

    doc.build(story)
    return buffer.getvalue()