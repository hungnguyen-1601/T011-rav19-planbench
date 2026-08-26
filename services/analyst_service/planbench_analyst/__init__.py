"""The analyst: the half of the explanation layer that proposes.

``packages/explanation`` owns the evidence, the sixteen tool cards, the
four mechanism checkers, the promotion matrix and the gate. It can say
what a claim is allowed to be, and it can refuse one. What it cannot do
is read a case packet and say *what the mechanism might be* — that is
the one job in this layer that needs a model, and it is this package.

Four rules every module under here inherits, from the E0–E6 contract
and from plan bản 8 §1. They are restated here rather than left in the
plan because a module that forgets one of them looks, from the outside,
exactly like a module that is working:

1. **It proposes; it never stamps.** The analyst returns
   :class:`~planbench_explanation.ledger.HypothesisProposal` objects,
   which carry no status, no confidence and no number — ``extra="forbid"``
   turns that policy into a parse error rather than a review comment.
2. **The model is never the source of a number.** Numbers shown to a
   reader are read out of the packet's fact index by the renderer. A
   statement that carries a quantity is a statement the guard drops.
3. **The tool menu is closed.** Sixteen cards, catalog version pinned in
   the bundle. There is no free-form check.
4. **It does not read raw traces.** The case packet and the tool results
   are the whole world; a Parquet file opened here would be evidence
   nobody could re-derive from the artifact the gate holds.

Nothing is exported yet: the modules arrive with their phases (A1 packet
view, A2 engine, A3 guard, A4 runner and lane, A5 knowledge, A6 harness,
A7 bundle builder), and a name published before the thing behind it
exists is the sort of promise the rest of this layer is built to refuse.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
