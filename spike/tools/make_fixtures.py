"""Generate synthetic Phase 0 fixtures (no real personal data).

Dev-only. Runs on any machine, not on the floor:
    python3 -m venv .venv && .venv/bin/pip install -r spike/tools/requirements-dev.txt
    .venv/bin/python spike/tools/make_fixtures.py fixtures/spike

Writes:
    qrbill-qrr.pdf / qrbill-scor.pdf   Swiss QR-bill payment part (vector) + *.payload.txt (exact QR content)
    ocr-<lang>.pdf                     image-only page (no text layer) + ocr-<lang>.txt (ground truth)
    invoice-<lang>.txt                 plain-text invoice for the S3 model test
"""
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from qrbill import QRBill
from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from svglib.svglib import svg2rlg

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# Fictitious parties. IBANs and references are the public SIX sample values.
CREDITOR = {"name": "Muster Treuhand AG", "street": "Musterstrasse", "house_num": "1",
            "pcode": "8000", "city": "Zürich", "country": "CH"}
DEBTOR = {"name": "Erika Beispiel", "street": "Beispielweg", "house_num": "7",
          "pcode": "3000", "city": "Bern", "country": "CH"}
BILLS = {
    "qrr": dict(account="CH4431999123000889012", reference_number="210000000003139471430009017",
                amount="1957.04", additional_information="Rechnung 2026-0417"),
    "scor": dict(account="CH5800791123000889012", reference_number="RF18539007547034",
                 amount="249.98", additional_information="Facture 2026-0042"),
}

INVOICES = {
    "de": ("Muster Treuhand AG\nMusterstrasse 1, 8000 Zürich\nCHE-123.456.788 MWST\n\n"
           "Erika Beispiel\nBeispielweg 7, 3000 Bern\n\nZürich, 17. April 2026\n\n"
           "Rechnung Nr. 2026-0417\n\nBuchhaltung 1. Quartal 2026     CHF 1'810.40\n"
           "MWST 8.1 %                       CHF   146.64\nTotal                            CHF 1'957.04\n\n"
           "Zahlbar innert 30 Tagen bis 17. Mai 2026.\nIBAN CH44 3199 9123 0008 8901 2\n"),
    "fr": ("Muster Treuhand AG\nMusterstrasse 1, 8000 Zürich\nCHE-123.456.788 TVA\n\n"
           "Erika Beispiel\nBeispielweg 7, 3000 Berne\n\nZurich, le 3 mars 2026\n\n"
           "Facture n° 2026-0042\n\nTenue de la comptabilité 2025     CHF 231.25\n"
           "TVA 8,1 %                         CHF  18.73\nTotal                             CHF 249.98\n\n"
           "Payable dans les 30 jours, au plus tard le 2 avril 2026.\nIBAN CH58 0079 1123 0008 8901 2\n"),
    "it": ("Muster Treuhand AG\nMusterstrasse 1, 8000 Zurigo\nCHE-123.456.788 IVA\n\n"
           "Erika Beispiel\nBeispielweg 7, 3000 Berna\n\nZurigo, 9 febbraio 2026\n\n"
           "Fattura n. 2026-0031\n\nConsulenza fiscale 2025           CHF 462.50\n"
           "IVA 8,1 %                         CHF  37.46\nTotale                            CHF 499.96\n\n"
           "Pagabile entro 30 giorni, entro l'11 marzo 2026.\nIBAN CH58 0079 1123 0008 8901 2\n"),
    "en": ("Muster Treuhand AG\nMusterstrasse 1, 8000 Zurich\nCHE-123.456.788 VAT\n\n"
           "Erika Beispiel\nBeispielweg 7, 3000 Bern\n\nZurich, 20 January 2026\n\n"
           "Invoice no. 2026-0007\n\nPayroll services December 2025    CHF 925.07\n"
           "VAT 8.1 %                         CHF  74.93\nTotal                             CHF 1'000.00\n\n"
           "Payable within 30 days, by 19 February 2026.\nIBAN CH44 3199 9123 0008 8901 2\n"),
}

OCR_TEXT = {
    "de": "Steueramt des Kantons Muster\nVeranlagungsverfügung 2025\nGegen diese Verfügung kann innert 30 Tagen\nschriftlich Einsprache erhoben werden.\nÄnderungen über Grösse, Strasse und Gebühr.",
    "fr": "Office des poursuites de Muster\nCommandement de payer n° 26-0815\nLe débiteur peut former opposition\ndans les dix jours dès la notification.\nCréancier : Société Exemple SA, Genève.",
    "it": "Ufficio esecuzioni di Muster\nPrecetto esecutivo n. 26-0815\nIl debitore può fare opposizione\nentro dieci giorni dalla notificazione.\nCreditore: Società Esempio SA, Lugano.",
    "en": "Muster Insurance Ltd\nPolicy renewal notice 2026\nPlease confirm the renewal\nwithin 30 days of this letter.\nPolicy holder: Erika Beispiel, Bern.",
}


def qrbill_pdf(out: Path, key: str) -> None:
    bill = QRBill(creditor=CREDITOR, debtor=DEBTOR, language="de", **BILLS[key])
    svg = io.StringIO()
    bill.as_svg(svg, full_page=True)
    drawing = svg2rlg(io.BytesIO(svg.getvalue().encode("utf-8")))
    c = canvas.Canvas(str(out / f"qrbill-{key}.pdf"), pagesize=A4, invariant=1)
    sx, sy = A4[0] / drawing.width, A4[1] / drawing.height
    drawing.scale(sx, sy)
    renderPDF.draw(drawing, c, 0, 0)
    c.showPage()
    c.save()
    # Exact QR content, byte for byte, for the Vision decode comparison.
    (out / f"qrbill-{key}.payload.txt").write_bytes(bill.qr_data().encode("utf-8"))


def ocr_pdf(out: Path, lang: str) -> None:
    dpi = 200
    w, h = int(8.27 * dpi), int(11.69 * dpi)
    img = Image.new("L", (w, h), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 40)
    y = 300
    for line in OCR_TEXT[lang].splitlines():
        draw.text((200, y), line, fill=0, font=font)
        y += 70
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    c = canvas.Canvas(str(out / f"ocr-{lang}.pdf"), pagesize=A4, invariant=1)
    c.drawImage(ImageReader(io.BytesIO(buf.getvalue())), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()
    (out / f"ocr-{lang}.txt").write_text(OCR_TEXT[lang] + "\n", encoding="utf-8")


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures/spike")
    out.mkdir(parents=True, exist_ok=True)
    for key in BILLS:
        qrbill_pdf(out, key)
    for lang in OCR_TEXT:
        ocr_pdf(out, lang)
    for lang, text in INVOICES.items():
        (out / f"invoice-{lang}.txt").write_text(text, encoding="utf-8")
    print(f"fixtures written to {out}")


if __name__ == "__main__":
    main()
