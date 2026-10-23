"""Apply the reviewed expected answers and promote the verified ones.

Every answer below uses only facts visible in the source chunks listed in eval/expected_review.md
(or, for F02/C04, chunks retrieved for C03/X02). Usage:  python eval/apply_review.py
N04 is left out until the Institutional Group figure is looked up in the filing.
"""
import json
from pathlib import Path

P = Path(__file__).parent / "questions_draft.json"

REVISED = {
    "F02": ("Schwab says clients' allocation of cash held on its balance sheet is sensitive to interest rate levels: "
            "when yields are higher, clients increase use of investment cash solutions such as purchased money market "
            "funds and certain fixed income products. A significant reduction in clients' allocation to cash, a change in "
            "that allocation, or a transfer of cash away from Schwab would likely reduce its income. After rapid "
            "short-term rate increases in 2022 and 2023, clients' allocation to sweep cash fell significantly, and Schwab "
            "relied extensively on higher-cost funding sources, which negatively impacted net income."),
    "F03": ("LPL says it depends on attracting and retaining experienced, productive advisors: a large portion of its "
            "revenue comes from advisor commissions and fees, and its strategy assumes continued growth in advisors. If it "
            "fails to attract new advisors, retain and motivate current advisors, replace advisors who retire, or help "
            "retiring advisors transition their practices to other advisors on its platform, or if advisor migration from "
            "wirehouses to independent channels slows, its business may suffer. Advisors or institutions that join through "
            "acquisitions or strategic relationships may later leave, taking their assets off the platform."),
    "F04": ("Stifel highlights: increased cybersecurity risk after acquisitions while it transitions acquired systems and "
            "networks; risks from mobile and cloud technologies and reliance on external service providers, including data "
            "breaches, unauthorized access and compromised APIs; cloud risks from misconfiguration, weak identity and access "
            "controls, vulnerable cloud workloads, and provider failures or outages; data leakage, malicious applications, "
            "phishing and network-level threats from mobile and web-facing technologies; and third-party risks including "
            "operational disruptions, security weaknesses and delayed incident notification."),
    "F05": ("Private Client Group net revenues rose 8% to $10,182 million in fiscal 2025 (from $9,459 million), driven "
            "mainly by asset management and related administrative fees, up 14% to $5,980 million, and brokerage revenues, "
            "up 6% to $1,737 million, partly offset by lower RJBDP fees (Bank segment down 8% to $754 million; third-party "
            "banks down 20% to $486 million). Pre-tax income fell 4% to $1,720 million as total compensation, commissions "
            "and benefits rose 10% to $7,384 million. Domestic PCG net new assets were $52,431 million (3.8% growth) versus "
            "$60,709 million (5.5%) in fiscal 2024."),
    "N02": ("Schwab's 2025 net interest revenue was $11,750 million, up 28% from $9,144 million in 2024. Asset management "
            "and administration fees were $6,506 million, up 14% from $5,716 million."),
    "N05": ("Capital Markets pre-tax income was $146 million in fiscal 2025, versus $67 million in fiscal 2024 and a "
            "pre-tax loss of $91 million in fiscal 2023, on net revenues of $1,770 million. A segment pre-tax margin is not "
            "reported; the firmwide pre-tax margin was 19.3%."),
    "C01": ("Both describe intense competition for advisor talent. Raymond James says the labor market remains "
            "competitive, with competition for talent across all aspects of its business and from non-traditional firms "
            "such as technology companies, as firms increase compensation and enhance benefits to attract talent. Stifel "
            "says its Global Wealth Management segment depends on attracting, retaining and motivating financial advisors "
            "and faces competition for qualified associates from major financial services companies, including other "
            "brokerage firms, insurance companies, banking institutions and discount brokerage firms; it also cites "
            "competition from fintechs and other non-traditional competitors."),
    "C04": ("Common to all four: extensive regulation and supervision by federal and state authorities and SROs such as "
            "the SEC and FINRA; exposure to regulatory actions that can bring fines, penalties, sanctions and restrictions; "
            "and the resulting financial and reputational harm. Raymond James and Stifel use nearly identical language: an "
            "evolving regulatory environment, scrutiny from the SEC, Fed, FDIC, OCC, DOL, CFPB, FINRA and state attorneys "
            "general, legal challenges to rules that create compliance uncertainty and cost, substantial and growing "
            "penalties, and overlapping state regulation. LPL emphasizes litigation, arbitration claims and regulatory "
            "proceedings by the SEC, FINRA, DOL and state regulators. Schwab describes compliance risk: legal or regulatory "
            "sanctions, fines, penalties, financial loss or reputational damage from failing to comply with laws and rules, "
            "under extensive federal, state, foreign and SRO regulation."),
    "X02": ("Schwab completed the Ameritrade integration as of December 31, 2024. Across five client transition groups in "
            "2023 and 2024 it converted about $1.9 trillion in client assets in more than 17 million accounts, including "
            "7,000 RIAs; attrition was below initial estimates. Total acquisition and integration-related costs and capital "
            "expenditures were about $2.5 billion, with acquisition and integration-related costs of $117 million in 2024 "
            "and $401 million in 2023. It realized annualized run-rate cost synergies of about $2.0 billion, plus about "
            "$500 million of incremental run-rate savings from streamlining actions."),
}
PROMOTE_AS_DRAFTED = ["F06", "N01", "N03", "N06", "C02", "C03", "X01"]

qs = json.loads(P.read_text())
done = []
for q in qs:
    if q["id"] in REVISED:
        q["candidate_answer"] = q["expected_answer"] = REVISED[q["id"]]
        done.append(q["id"] + " (revised)")
    elif q["id"] in PROMOTE_AS_DRAFTED and q.get("candidate_answer"):
        q["expected_answer"] = q["candidate_answer"]
        done.append(q["id"])
P.write_text(json.dumps(qs, indent=2, ensure_ascii=False))
missing = [q["id"] for q in qs if q["category"] != "unanswerable" and not q.get("expected_answer")]
print("Promoted:", ", ".join(done))
print("Still without an expected answer:", ", ".join(missing) or "none")
