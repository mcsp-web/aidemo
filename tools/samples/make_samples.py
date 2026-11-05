"""Builds the demo sample documents in app/static/samples/<pack>/.

Every business, person, plan and address in these files is invented. They exist so a
prospect can try AskDoc on documents that look like their own industry's. Rerun after
editing the text below:

    python tools/samples/make_samples.py

Needs reportlab (dev-only, like the tests).
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parents[2] / "app" / "static" / "samples"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=17, spaceAfter=6)
SUB = ParagraphStyle("SUB", parent=ss["BodyText"], fontSize=10.5, textColor=colors.HexColor("#555555"), spaceAfter=14)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=12.5, spaceBefore=10, spaceAfter=5)
B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10.5, leading=14.5, spaceAfter=6)


CELL = ParagraphStyle("CELL", parent=ss["BodyText"], fontSize=9.5, leading=12)


def table(rows, widths):
    # Cells as paragraphs so long text wraps inside its column.
    rows = [[Paragraph(str(c), CELL) for c in r] for r in rows]
    t = Table(rows, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#999999")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eef3")),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build(path: Path, title: str, subtitle: str, pages: list[list]) -> None:
    """pages: list of pages; each page is a list of ('h'|'p'|'t', content[, widths])."""
    path.parent.mkdir(parents=True, exist_ok=True)

    def foot(c, d):
        c.setFont("Helvetica", 8.5)
        c.setFillColor(colors.HexColor("#666666"))
        c.drawString(72, 40, f"{title}  |  Fictional sample for demonstration  |  Page {d.page}")

    story = [Paragraph(title, H1), Paragraph(subtitle, SUB)]
    for i, page in enumerate(pages):
        if i:
            story.append(PageBreak())
        for item in page:
            kind = item[0]
            if kind == "h":
                story.append(Paragraph(item[1], H2))
            elif kind == "p":
                story.append(Paragraph(item[1], B))
            elif kind == "t":
                story += [table(item[1], item[2]), Spacer(1, 8)]
    doc = SimpleDocTemplate(str(path), pagesize=letter, title=title,
                            author="AskDoc demo (fictional sample)", topMargin=60, bottomMargin=60)
    doc.build(story, onFirstPage=foot, onLaterPages=foot)


# ------------------------------------------------------------------ HOA
HOA = "Palm Hollow Homeowners Association"

hoa_ccrs = [
    [
        ("p", f"This Declaration governs every lot in {HOA}, a community of 312 single-family homes in Coral Point, Florida. Owners, tenants and guests must follow it. Where this Declaration and the Rules disagree, this Declaration controls."),
        ("h", "Article 4 - Assessments"),
        ("p", "The regular assessment for 2026 is $485 per lot per quarter, due on January 1, April 1, July 1 and October 1."),
        ("p", "An assessment not paid within 15 days of its due date is late. A late fee of $25 is charged, and the unpaid balance earns interest at 18% per year until paid."),
        ("p", "After 90 days of non-payment, the Board may suspend the owner's use of the pool and clubhouse until the account is brought current. Suspension never affects access to the owner's home or to the roads."),
        ("p", "A special assessment above $1,000 per lot in any year requires approval by a majority of the voting interests present at a meeting where a quorum is reached."),
    ],
    [
        ("h", "Article 6 - Architectural review"),
        ("p", "No fence, wall, pool, screen enclosure, shed, solar panel or change to a home's exterior colour may be started without written approval from the Architectural Review Committee (ARC)."),
        ("p", "Applications are made on the ARC form with a site plan and, for colour changes, a paint sample. The ARC decides within 30 days of receiving a complete application. An application not decided within 30 days is treated as approved."),
        ("p", "Fences may only be installed in rear and side yards, may not extend past the front corner of the home, and may not be taller than 6 feet. Permitted materials are white vinyl or black aluminum. Chain-link and wood fences are not permitted."),
        ("p", "Approved work must start within 6 months and be finished within 9 months of approval, or the approval lapses."),
        ("p", "Hurricane shutters may be put up no earlier than 48 hours before a named storm is forecast to reach Coral Point and must be removed within 7 days after the storm has passed."),
    ],
    [
        ("h", "Article 7 - Pets"),
        ("p", "Each home may keep up to 3 household pets. Dogs must be leashed whenever they are outside the owner's lot, and owners must pick up after them immediately. Livestock, poultry and reptiles longer than 3 feet are prohibited."),
        ("p", "A pet that the Board finds, after notice and a hearing, to be a nuisance or a danger may be required to be removed from the community."),
        ("h", "Article 8 - Leasing"),
        ("p", "An owner must have owned the home for at least 12 months before leasing it. Leases must be for the whole home and for a minimum term of 7 months. No home may be leased more than twice in any 12-month period. Short-term and vacation rentals are prohibited."),
        ("p", "The owner must give the Association a copy of the signed lease and the tenants' names at least 10 days before the tenants move in. Tenants receive gate access only after the lease is on file."),
    ],
    [
        ("h", "Article 9 - Vehicles and parking"),
        ("p", "Vehicles must be parked in garages or driveways. Overnight parking on the street is not allowed between 2:00 a.m. and 6:00 a.m."),
        ("p", "Commercial vehicles with lettering or ladder racks may not be parked overnight. Boats, trailers and recreational vehicles may be parked in a driveway for no more than 24 hours for loading and unloading."),
        ("p", "Vehicles parked in violation of this Article may be towed at the owner's expense after a warning notice has been posted on the vehicle for 24 hours."),
        ("h", "Article 11 - Fines and enforcement"),
        ("p", "The Board may fine an owner up to $100 per violation, or up to $100 per day for a continuing violation, to a maximum of $1,000. A fine may only be imposed after 14 days' written notice and an opportunity for a hearing before the Fining Committee."),
    ],
]

hoa_bylaws = [
    [
        ("h", "Article 2 - Board of Directors"),
        ("p", "The Association is governed by a Board of 5 directors elected by the members. Directors serve 2-year staggered terms: 3 seats are elected in even years and 2 in odd years."),
        ("p", "A director who misses 3 consecutive regular Board meetings without an excuse accepted by the Board may be removed by a vote of the other directors."),
        ("p", "Directors serve without pay. Reasonable expenses approved in advance by the Board are reimbursed."),
        ("h", "Article 3 - Officers"),
        ("p", "The Board elects a President, Vice President, Treasurer and Secretary from among its members at the first Board meeting after each annual meeting. The Treasurer presents a financial report at every regular Board meeting."),
    ],
    [
        ("h", "Article 4 - Meetings"),
        ("p", "The annual meeting of members is held in March each year. Written notice of the annual meeting is mailed or emailed to every owner at least 14 days before the meeting and posted at the clubhouse."),
        ("p", "Regular Board meetings are held at least every other month. Notice of every Board meeting is posted at the clubhouse and on the community website at least 48 hours in advance, except in an emergency."),
        ("p", "A Board meeting at which a special assessment or a change to the Rules will be considered requires 14 days' mailed or emailed notice to owners, stating the purpose."),
        ("p", "Owners may attend Board meetings and may speak for up to 3 minutes on any item on the agenda."),
        ("h", "Article 5 - Quorum and voting"),
        ("p", "A quorum at a members' meeting is 30% of the voting interests, present in person or by proxy. Each lot has one vote. Unless the Declaration requires more, decisions are made by a majority of the votes cast at a meeting where a quorum is present."),
    ],
    [
        ("h", "Article 6 - Budget and reserves"),
        ("p", "The Board adopts the annual budget at a meeting held in November and sends a copy to every owner at least 14 days before that meeting. The budget includes reserves for the roads, the pool and the clubhouse roof."),
        ("h", "Article 7 - Official records"),
        ("p", "Owners may inspect the official records of the Association. A written request must be answered within 10 business days. Copies cost $0.25 per page; electronic copies are free."),
        ("p", "Records kept include the Declaration, Bylaws and Rules, minutes of meetings for the last 7 years, the current budget, financial statements and insurance policies."),
    ],
]

hoa_rules = [
    [
        ("h", "Pool and clubhouse"),
        ("p", "The pool is open from 8:00 a.m. to 9:00 p.m. every day. There is no lifeguard; children under 14 must be accompanied by an adult. Each household may bring up to 4 guests at a time."),
        ("p", "The clubhouse may be rented by owners in good standing for private events. Rental is $150 per event plus a refundable $250 deposit, booked at least 14 days in advance through the management office. Events must end by 11:00 p.m."),
        ("h", "Trash and recycling"),
        ("p", "Trash is collected on Tuesdays and Fridays; recycling on Wednesdays. Containers may be placed at the curb after 6:00 p.m. the day before collection and must be put away by 9:00 p.m. on collection day."),
        ("h", "Holiday decorations"),
        ("p", "Holiday decorations may be put up 30 days before the holiday and must be removed within 15 days after it."),
        ("h", "Noise"),
        ("p", "Quiet hours are 10:00 p.m. to 7:00 a.m. Construction and lawn equipment may only be used from 8:00 a.m. to 6:00 p.m. Monday to Saturday."),
    ],
    [
        ("h", "Fee schedule (2026)"),
        ("t", [
            ["Item", "Fee"],
            ["Quarterly assessment", "$485 per lot"],
            ["Late fee (after 15 days)", "$25"],
            ["ARC application (fence, pool, shed, exterior colour)", "$50 per application"],
            ["ARC re-review after a denial", "$25"],
            ["Clubhouse rental", "$150 + $250 refundable deposit"],
            ["Gate remote (new or replacement)", "$35"],
            ["Resale or estoppel certificate", "$250"],
            ["Tenant registration", "$100 per lease"],
        ], [300, 160]),
        ("p", "Fees are payable to Palm Hollow Homeowners Association through the management office or the owner portal. The management company is Bayline Community Management, open Monday to Friday, 9:00 a.m. to 5:00 p.m."),
    ],
]

# ------------------------------------------------------------------ Dental
DENTAL = "Brightside Family Dental"

dental_manual = [
    [
        ("p", f"This manual is for every team member at {DENTAL}. It explains how we schedule, how we handle payment and insurance, and what we tell patients. Ask the office manager, Dana Ruiz, when something is not covered here."),
        ("h", "1. Office hours"),
        ("p", "Monday to Thursday 8:00 a.m. to 5:00 p.m.; Friday 8:00 a.m. to 1:00 p.m. Closed on weekends. The last new-patient appointment of the day starts at 3:30 p.m."),
        ("h", "2. Scheduling"),
        ("p", "New-patient visits are booked for 90 minutes and include a full exam, X-rays and a cleaning when time allows. Routine hygiene visits are 60 minutes. Emergency slots are held at 11:00 a.m. and 2:00 p.m. each weekday."),
        ("p", "Recall: adults are scheduled every 6 months; patients with periodontal disease every 3 months."),
        ("p", "Patients under 18 must be accompanied by a parent or legal guardian at their first visit, and a guardian must sign the consent form."),
    ],
    [
        ("h", "3. Cancellations and missed appointments"),
        ("p", "We ask for 48 hours' notice to cancel or move an appointment. The first late cancellation or missed appointment in a 12-month period is waived. After that, a $50 fee is charged for each late cancellation or missed appointment."),
        ("p", "After 3 missed appointments in 12 months, the patient may only book same-day appointments."),
        ("h", "4. Payment"),
        ("p", "Copays and the patient's estimated portion are due at the visit. We accept cash, debit and credit cards, and health savings account cards. We do not accept personal checks."),
        ("p", "For treatment plans over $600, patients may pay in equal monthly instalments over up to 6 months with no interest. The first instalment is due when treatment starts."),
        ("p", "Patients without insurance receive 10% off when they pay in full at the visit."),
    ],
    [
        ("h", "5. Insurance"),
        ("p", "We are in network with Coastal Shield Dental PPO and SunState Basic Dental HMO. Benefits for those plans are in the plan summaries in this pack. For any other plan we file the claim as a courtesy, and the patient pays our full fee at the visit."),
        ("p", "Always verify eligibility at least 2 business days before the appointment and note the remaining annual maximum in the chart."),
        ("h", "6. X-rays"),
        ("p", "Bitewing X-rays are taken once a year for adults. A full-mouth series is taken every 5 years, or sooner when the dentist orders it. Pregnant patients are asked to tell us before any X-ray."),
        ("h", "7. After-hours emergencies"),
        ("p", "Outside office hours, patients call the main number and press 2 to reach the dentist on call. Patients with facial swelling that affects breathing or swallowing are told to go to the emergency room."),
    ],
]

dental_ppo = [
    [
        ("p", "Plan summary for front-desk use. Coastal Shield Dental PPO is an invented plan used for this demonstration."),
        ("h", "Key figures"),
        ("t", [
            ["Benefit", "In network"],
            ["Annual maximum", "$1,500 per person per calendar year"],
            ["Deductible", "$50 per person, $150 per family; waived for preventive care"],
            ["Preventive (exams, cleanings, bitewings)", "100%"],
            ["Basic (fillings, simple extractions)", "80% after deductible"],
            ["Major (crowns, bridges, dentures)", "50% after deductible"],
            ["Orthodontics", "Not covered"],
        ], [230, 230]),
        ("h", "Frequency limits"),
        ("p", "Exams and cleanings: 2 per calendar year, at least 6 months apart. A third cleaning is covered only for members with a history of periodontal treatment."),
        ("p", "Fluoride: once a year for members under 16. Sealants: once per permanent molar for members under 14."),
    ],
    [
        ("h", "Waiting periods"),
        ("p", "There is no waiting period for preventive and basic care. Major services have a 12-month waiting period from the member's start date."),
        ("h", "Missing tooth clause"),
        ("p", "A bridge or implant to replace a tooth that was missing before the member joined the plan is not covered."),
        ("h", "Claims"),
        ("p", "Claims must be filed within 12 months of the date of service. Pre-treatment estimates are recommended for any treatment over $300."),
    ],
]

dental_hmo = [
    [
        ("p", "Plan summary for front-desk use. SunState Basic Dental HMO is an invented plan used for this demonstration."),
        ("p", "Members must choose Brightside Family Dental as their assigned office. There is no annual maximum and no deductible; members pay the fixed copay below."),
        ("t", [
            ["Service", "Member copay"],
            ["Exam", "$0"],
            ["Cleaning (2 per year)", "$0"],
            ["Bitewing X-rays", "$0"],
            ["Filling, one surface", "$25"],
            ["Simple extraction", "$40"],
            ["Root canal, front tooth", "$250"],
            ["Crown (porcelain on metal)", "$425"],
            ["Missed appointment (no 24 hours' notice)", "$20 charged by the plan"],
        ], [260, 200]),
        ("p", "Specialist referrals need approval from the plan before the visit. Cosmetic whitening is not covered."),
    ],
]

dental_sop = [
    [
        ("p", "Standard operating procedure for instrument processing. Sample text for demonstration only; follow the manufacturer's instructions and current CDC guidance in a real practice."),
        ("h", "Handpieces"),
        ("p", "After each patient: run the handpiece for 20 seconds to flush water lines, wipe it down, clean and lubricate it as the manufacturer directs, bag it, and sterilize it in the autoclave. Handpieces are never only wiped and reused."),
        ("h", "Autoclave"),
        ("p", "Standard cycle: 132 degrees Celsius (270 F) for 4 minutes, followed by the drying cycle. Every pouch carries a chemical indicator, and each load is logged with the date, cycle number and operator's initials."),
        ("h", "Spore testing"),
        ("p", "A biological spore test is run on the autoclave every week, on Monday's first load, and after any repair. A failed test means the autoclave is taken out of use and the office manager is told the same day."),
        ("h", "Sharps"),
        ("p", "Sharps go into the red sharps container in each operatory. Containers are closed and replaced when three-quarters full."),
    ],
]

# ------------------------------------------------------------------ Any business
BIZ = "Harbor Logistics"

biz_handbook = [
    [
        ("p", f"Welcome to {BIZ}. This handbook explains the policies that apply to every full-time employee. It replaces all earlier versions and takes effect on January 1, 2026."),
        ("h", "1. Working hours and probation"),
        ("p", "Standard hours are 8:30 a.m. to 5:00 p.m., Monday to Friday, with a one-hour lunch. New employees serve a 90-day probation period."),
        ("p", "Overtime must be approved in advance by your manager. Non-exempt employees are paid 1.5 times their hourly rate for hours over 40 in a week."),
        ("h", "2. Paid time off"),
        ("p", "Full-time employees earn 15 days of paid time off (PTO) per calendar year, accrued monthly. After three years of service, the allowance increases to 20 days."),
        ("p", "Up to 5 unused PTO days may be carried over into the next year. Carried-over days expire on March 31."),
        ("p", "PTO requests longer than three consecutive days must be submitted to your manager at least two weeks in advance. The company observes 9 paid holidays a year."),
    ],
    [
        ("h", "3. Remote and hybrid work"),
        ("p", "Office-based roles may work remotely up to two days per week with manager approval. Remote employees must be reachable on Slack between 10:00 and 15:00 Eastern time."),
        ("p", "Company laptops must stay encrypted and may not be used by family members."),
        ("h", "4. Expenses and reimbursement"),
        ("p", "Business expenses must be submitted in the expense portal within 30 days of purchase, with an itemized receipt for anything over $25."),
        ("p", "Meals while travelling are reimbursed up to $65 per day. Alcohol is not reimbursable. Mileage for personal vehicles is reimbursed at the current IRS standard rate."),
        ("p", "Expenses over $500 require written pre-approval from a department head."),
        ("h", "5. Benefits"),
        ("p", "Employees may enrol in health, dental and vision coverage within 30 days of their start date or during open enrolment in November. The company matches 401(k) contributions up to 4% of salary after 6 months of service."),
    ],
]

biz_sops = [
    [
        ("h", "SOP 1 - Customer returns"),
        ("p", "Standard items may be returned within 30 days of delivery for a full refund. Special-order items carry a 15% restocking fee. Items damaged in transit must be reported within 48 hours of delivery with photos."),
        ("p", "Refunds are issued to the original payment method within 5 business days of the item reaching the warehouse."),
        ("h", "SOP 2 - Purchase approvals"),
        ("t", [
            ["Purchase amount", "Approved by"],
            ["Up to $500", "Team lead"],
            ["$500.01 to $5,000", "Department head"],
            ["$5,000.01 to $25,000", "Operations director"],
            ["Over $25,000", "Chief financial officer, with two quotes"],
        ], [200, 260]),
    ],
    [
        ("h", "SOP 3 - Opening and closing the warehouse"),
        ("p", "The first person in disarms the alarm with their own code, turns on the dock lights and checks the overnight delivery log. The warehouse opens to drivers at 7:00 a.m."),
        ("p", "At closing, the shift lead checks that every dock door is down and locked, the forklifts are on their chargers, and the alarm is set. The last person out signs the closing sheet by the main door."),
        ("h", "SOP 4 - If the order system is down"),
        ("p", "Take orders on the paper order form kept at the front desk, give each a number from the paper log, and enter them into the system within 2 hours of it coming back. Tell customers their confirmation email may be delayed."),
    ],
]


PACKS = {
    "hoa": [
        ("Palm-Hollow-HOA-Declaration-CCRs.pdf", f"{HOA} - Declaration of Covenants (CC&Rs)", "Excerpts: assessments, architectural review, pets, leasing, vehicles, fines", hoa_ccrs),
        ("Palm-Hollow-HOA-Bylaws.pdf", f"{HOA} - Bylaws", "Board, officers, meetings, voting, budget and records", hoa_bylaws),
        ("Palm-Hollow-HOA-Rules-and-Fees-2026.pdf", f"{HOA} - Rules and Fee Schedule 2026", "Community rules adopted by the Board, and the 2026 fees", hoa_rules),
    ],
    "dental": [
        ("Brightside-Dental-Office-Manual.pdf", f"{DENTAL} - Office Policy Manual", "Front desk and team policies, 2026", dental_manual),
        ("Brightside-Dental-Coastal-Shield-PPO-Summary.pdf", "Coastal Shield Dental PPO - Plan Summary", "In-network benefits for Brightside Family Dental patients", dental_ppo),
        ("Brightside-Dental-SunState-HMO-Summary.pdf", "SunState Basic Dental HMO - Plan Summary", "Copay schedule for members assigned to Brightside Family Dental", dental_hmo),
        ("Brightside-Dental-Sterilization-SOP.pdf", f"{DENTAL} - Instrument Sterilization SOP", "Infection control procedure", dental_sop),
    ],
    "general": [
        ("Harbor-Logistics-Employee-Handbook-2026.pdf", f"{BIZ} - Employee Handbook 2026", "Policies for full-time employees", biz_handbook),
        ("Harbor-Logistics-Operations-SOPs.pdf", f"{BIZ} - Operations SOPs", "Returns, purchase approvals, opening and closing, system outages", biz_sops),
    ],
}


def main() -> None:
    for pack, files in PACKS.items():
        for name, title, sub, pages in files:
            build(OUT / pack / name, title, sub, pages)
            print(f"{pack}/{name}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
