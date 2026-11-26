"""Human authority gate. The system computes and proposes; only these functions record decisions,
and each checks the caller's role against the delegation-of-authority matrix in config/settings.json.
Nothing in cov.pipeline or cov.agent calls these functions.
"""
from cov.common import load_settings


class AuthorityError(Exception):
    pass


class ApprovalGate:
    def __init__(self, audit, settings=None):
        self.audit = audit
        self.settings = settings or load_settings()

    def _check(self, action, role):
        allowed = self.settings["authority"][action]
        if role not in allowed:
            raise AuthorityError(f"role '{role}' may not '{action}' (allowed: {allowed})")

    def _decisions(self, run_id):
        return [e["payload"] for e in self.audit.entries() if e["kind"] == "decision" and e["payload"]["run_id"] == run_id]

    def decide_finding(self, run, idx, decision, user, role, note=""):
        assert decision in ("accept", "reject")
        self._check("accept_finding", role)
        return self.audit.append("decision", {"run_id": run["run_id"], "action": "finding", "finding_index": idx,
                                              "finding": run["findings"][idx], "decision": decision,
                                              "user": user, "role": role, "note": note})

    def accept_value(self, run, field, value_source, user, role, note=""):
        self._check("accept_reextracted_value", role)
        return self.audit.append("decision", {"run_id": run["run_id"], "action": "accept_value", "field": field,
                                              "source": value_source, "user": user, "role": role, "note": note})

    def release_halt(self, run, user, role, reason):
        self._check("release_halt", role)
        return self.audit.append("decision", {"run_id": run["run_id"], "action": "release_halt", "user": user,
                                              "role": role, "reason": reason})

    def sign(self, run, user, role, determination, note=""):
        """Record the determination. Breach declarations require the credit committee."""
        if run["provisional_status"] == "HALT":
            raise AuthorityError("run is halted; it must be released and re-run before a determination")
        open_items = {i for i in range(len(run["findings"]))}
        decided = {d["finding_index"] for d in self._decisions(run["run_id"]) if d["action"] == "finding"}
        if open_items - decided:
            raise AuthorityError(f"open findings not yet decided: {sorted(open_items - decided)}")
        needed_values = set(run.get("pending_value_acceptance", []))
        accepted = {d["field"] for d in self._decisions(run["run_id"]) if d["action"] == "accept_value"}
        if needed_values - accepted:
            raise AuthorityError(f"values awaiting acceptance: {sorted(needed_values - accepted)}")
        action = {"BREACH": "declare_breach", "TIGHT": "sign_memo_tight", "COMPLIANT": "sign_memo_compliant"}[determination]
        self._check(action, role)
        if self.settings["separation_of_duties"]["memo_signer_must_differ_from_finding_reviewer"]:
            reviewers = {d["user"] for d in self._decisions(run["run_id"]) if d["action"] in ("finding", "accept_value")}
            if user in reviewers:
                raise AuthorityError("separation of duties: signer reviewed findings for this run")
        if determination != run["provisional_status"] and not note:
            raise AuthorityError("override of the engine status requires a written rationale")
        return self.audit.append("determination", {"run_id": run["run_id"], "borrower": run["borrower"],
                                                   "period": run["period"], "determination": determination,
                                                   "engine_status": run["provisional_status"], "override": determination != run["provisional_status"],
                                                   "user": user, "role": role, "note": note})
