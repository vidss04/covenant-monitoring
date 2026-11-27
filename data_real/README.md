# Real-filing pilot (SEC EDGAR)

`fetch_edgar.py` was run on 10 filers chosen from `search_results.csv` (159 filers matching
"Total Net Leverage Ratio" + "Compliance Certificate"). It saved ~170 Exhibit-10 credit documents
and XBRL company facts. The raw filings (~114 MB) are in the team Drive folder (`edgar_raw.zip`),
not in git.

`draft_covenant_labels.csv` holds **DRAFT** labels for the maintenance covenants in the most recent
agreement for 9 filers (Limoneira dropped: short agricultural loan documents only). They were read
from the filings by Claude and **must be verified by a team member against the filing** before
being called gold labels.

Findings so far (pre-verification):
- 7 of 9 agreements have a locatable maintenance covenant; Quantum and Cadre need a closer look.
- 4 of 7 have thresholds that change on an event or a borrower election rather than a calendar date
  (Enviri: Rail Disposition / Clean Earth Effective Date; DSG: Alternate Funding / Covenant Ratchet
  Date; ModivCare: Covenant Relief Period; Digi: acquisition holiday). The effective-date rule must
  halt on these unless a person supplies the event date, the same behaviour as synthetic borrower CLC.
- 2 of 7 conformed copies contain redline artifacts that put two numbers next to each other
  ("2.75 2.00 to 1.00", "5:25 5.25 to 1:00 1.00"); a naive pattern reads the struck number.
- A fixed clause pattern of the kind that parses the synthetic agreements located the covenant
  clause in only 3 of 9 real agreements, which is why real text goes to the LLM graph builder
  (`cov/kg_llm.py`) plus human review.
