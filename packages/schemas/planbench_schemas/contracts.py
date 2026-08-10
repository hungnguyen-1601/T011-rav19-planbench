"""The contract version the code implements.

Every Decision Card (HĐ-12) and every manifest (HĐ-13) carries
``contracts_version``, so the string has to live in exactly one place. It
lives here, and :mod:`tests.test_contract_version` asserts it matches the
header of ``contracts/CONTRACTS.md``.

That test exists because of a specific, very ordinary failure: somebody
amends the contract and bumps the document, and the code keeps stamping
the old version onto cards — or the reverse. Either way a stored card
claims to have been produced under rules it was not produced under, and
HĐ-13's acceptance criterion (hand the manifest to someone else, they
rebuild the same Decision Card) quietly stops holding.
"""

from __future__ import annotations

#: Must equal the `contracts_version` in the header of contracts/CONTRACTS.md.
CONTRACTS_VERSION = "2.1.0"
