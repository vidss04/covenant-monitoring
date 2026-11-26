# Analyst timing protocol (manual vs system-assisted)

The prototype cannot measure human minutes by itself. Run this with two team members before the final presentation.

1. Pick 4 packages: AIH 2025-09-30, BHS 2025-06-30, CLC 2025-06-30, DSW 2026-03-31 (one hard case per borrower).
2. **Manual arm** (person A): from the PDFs and agreement text only, in Excel, compute Consolidated EBITDA, the leverage
   and coverage ratios, the governing threshold, status, and the reason for any gap with the certificate. Time each package.
3. **Assisted arm** (person B, different packages order): open the Streamlit screen, review the engine output, accept or
   reject each finding, accept re-extracted values, and choose a determination. Time each package, including the time
   spent checking citations.
4. Swap roles on a second set of 4 packages to control for person.
5. Record: minutes per package, errors against `data/gold/answer_key.json`, and number of times the assisted user
   overrode the system. Report net time saved = manual minus (review + correction) time.
