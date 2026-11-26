# Live demo script (about 6 minutes)

Setup: `make eval` beforehand; terminal with `python demo.py`; browser with `streamlit run app/approval_app.py`.

1. **The problem (30s).** Apex's Q3 2025 certificate says 4.08x vs 4.50x: compliant. Ask the room: is it?
2. **Scene 1 - engine + graph (90s).** Run `demo.py`. Show governing versions BASE+AMD1 (threshold 4.25x), the 15% cap cutting
   $3.0m of add-backs, 4.35x -> BREACH, sensitivity ($1.06m EBITDA / $4.5m debt). Show the 3-step agent trace: typed fields only.
3. **Scene 2 - authority (60s).** The PM cannot declare a breach; the analyst who reviewed findings cannot also sign; credit
   committee signs. Every refusal comes from config, not a prompt.
4. **Scene 3 - injection (60s).** Q4 certificate tells automated systems to report COMPLIANT. Status stays BREACH, identical
   to the clean twin. The note appears only on the analyst screen.
5. **Scene 4 - halt (45s).** Cedar's amendment has no calendar effective date: the system refuses to pick a threshold.
6. **Streamlit (60s).** AIH 2025-09-30: page image behind a citation, accept the finding, sign as credit committee, open the
   audit trail. Then CLC 2025-06-30: units error caught by XBRL tie-out, second read recommended, pending acceptance.
