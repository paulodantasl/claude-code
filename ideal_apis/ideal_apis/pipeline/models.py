from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Priority = Literal["high", "medium", "low"]
Brand = Literal["ideal_dental", "ideal_cgc", "ideal_remodeling"]
Source = Literal["nppes", "yelp", "openfema", "usaspending", "federal_contracts", "weather", "manual"]


@dataclass
class LeadRecord:
    id: str
    source: Source
    brand: Brand
    name: str
    phone: str | None = None
    email: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    taxonomy: str | None = None
    npi: str | None = None
    priority: Priority = "medium"
    notes: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    phone_valid: bool | None = None
    email_disposable: bool | None = None
    address_validated: bool | None = None
    discovered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def contact_name(self) -> str:
        """JobTread contact name with embedded phone per org convention."""
        short = self.name[:40]
        if self.phone:
            return f"{short} | {self._format_phone(self.phone)}"
        return short

    @staticmethod
    def _format_phone(phone: str) -> str:
        digits = "".join(c for c in phone if c.isdigit())
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) == 10:
            return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
        return phone

    def full_address(self) -> str | None:
        parts = [self.street, self.city, self.state, self.zip_code]
        cleaned = [p for p in parts if p]
        return ", ".join(cleaned) if cleaned else None

    def has_contact_channel(self) -> bool:
        return bool(self.phone or self.email)

    def dedupe_key(self) -> str:
        if self.npi:
            return f"npi:{self.npi}"
        if self.phone:
            digits = "".join(c for c in self.phone if c.isdigit())[-10:]
            if digits:
                return f"phone:{digits}"
        if self.email:
            return f"email:{self.email.lower()}"
        return f"name:{self.name.lower()}|{self.city or ''}|{self.state or ''}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
