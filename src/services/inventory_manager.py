
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.models.item import Item
from src.models.stock_batch import StockBatch, StockSource


IST = ZoneInfo("Asia/Kolkata")


class InventoryError(Exception):
    """Raised when an inventory operation cannot be completed."""


class InventoryManager:
    """
    Manages opening inventory, stock receipts, verification,
    stock availability, deductions and expiry write-offs.
    """

    def __init__(self):
        self.batches: dict[str, StockBatch] = {}
        self.items: dict[str, Item] = {}
        self.processed_receipts: set[str] = set()
        self.rejected_receipts: list[dict] = []
        self.verification_times: dict[str, datetime] = {}
        self.write_offs: list[dict] = []

    @staticmethod
    def _parse_timestamp(value: str | datetime) -> datetime:
        """Convert a timestamp into an IST-aware datetime."""
        if isinstance(value, datetime):
            result = value
        else:
            try:
                result = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                result = result.replace(tzinfo=IST)
            except (TypeError, ValueError) as exc:
                raise InventoryError(
                    f"Invalid timestamp: {value}"
                ) from exc

        if result.tzinfo is None or result.utcoffset() is None:
            raise InventoryError("Timestamp must include timezone information.")

        return result

    @staticmethod
    def _parse_bool(value: str | bool) -> bool:
        if isinstance(value, bool):
            return value

        normalized = str(value).strip().lower()

        if normalized == "true":
            return True
        if normalized == "false":
            return False

        raise InventoryError(f"Invalid boolean value: {value}")

    def register_item(self, item: Item) -> None:
        """Register an item and its metadata."""
        if not isinstance(item, Item):
            raise InventoryError("Invalid item.")

        if item.item_id in self.items:
            raise InventoryError(
                f"Item '{item.item_id}' already exists."
            )

        self.items[item.item_id] = item

    def add_batch(self, batch: StockBatch) -> None:
        """Register an existing stock batch."""
        if not isinstance(batch, StockBatch):
            raise InventoryError("Invalid stock batch.")

        if batch.batch_id in self.batches:
            raise InventoryError(
                f"Batch '{batch.batch_id}' already exists."
            )

        self.batches[batch.batch_id] = batch

    def load_opening_batches(self, rows: list[dict]) -> None:
        """Load the initial inventory from stock_batches.csv."""
        for row in rows:
            item_id = row["item_id"]

            if item_id not in self.items:
                raise InventoryError(
                    f"Unknown item '{item_id}' in opening inventory."
                )

            source = StockSource(row["source"])
            is_donation = source == StockSource.DONATION
            verified = self._parse_bool(row["verified"])

            requires_verification = (
                is_donation
                and self.items[item_id].is_medicine
                and not verified
            )

            batch = StockBatch(
                batch_id=row["batch_id"],
                depot_id=row["depot_id"],
                item_id=item_id,
                quantity=int(row["qty"]),
                received_at=None,
                expiry_date=self._parse_timestamp(row["expiry_ts"]),
                source=source,
                is_donation=is_donation,
                verified=verified,
                requires_verification=requires_verification,
            )

            self.add_batch(batch)

    def process_receipt(self, receipt: dict) -> StockBatch | None:
        """
        Process one RECEIVE command's receipt record.

        Donations with less than seven days of remaining shelf
        life are rejected. Donated medicine is quarantined.
        """
        receipt_id = receipt["receipt_id"]

        if receipt_id in self.processed_receipts:
            raise InventoryError(
                f"Receipt '{receipt_id}' has already been processed."
            )

        item_id = receipt["item_id"]

        if item_id not in self.items:
            raise InventoryError(
                f"Unknown item '{item_id}' in receipt."
            )

        source = StockSource(receipt["source"])
        received_at = self._parse_timestamp(receipt["received_ts"])
        expiry_date = self._parse_timestamp(receipt["expiry_ts"])

        if expiry_date <= received_at:
            raise InventoryError(
                "Receipt expiry must be after its received timestamp."
            )

        is_donation = source == StockSource.DONATION

        if is_donation and expiry_date - received_at < timedelta(days=7):
            self.processed_receipts.add(receipt_id)
            self.rejected_receipts.append({
                "receipt_id": receipt_id,
                "batch_id": receipt["batch_id"],
                "reason": "DONATION_SHELF_LIFE_BELOW_7_DAYS",
            })
            return None

        if receipt["batch_id"] in self.batches:
            raise InventoryError(
                f"Batch '{receipt['batch_id']}' already exists."
            )

        requires_verification = (
            is_donation and self.items[item_id].is_medicine
        )

        batch = StockBatch(
            batch_id=receipt["batch_id"],
            depot_id=receipt["depot_id"],
            item_id=item_id,
            quantity=int(receipt["qty"]),
            received_at=received_at,
            expiry_date=expiry_date,
            source=source,
            is_donation=is_donation,
            requires_verification=requires_verification,
            verified=not requires_verification,
        )

        self.add_batch(batch)
        self.processed_receipts.add(receipt_id)
        return batch

    def verify_batch(
        self,
        batch_id: str,
        verified_at: datetime | str | None = None
    ) -> None:
        """Release a quarantined donated medicine batch."""
        batch = self._get_batch(batch_id)

        if not batch.is_donation or not batch.requires_verification:
            raise InventoryError(
                "Batch is not awaiting donation verification."
            )

        if verified_at is None:
            raise InventoryError(
                "Verification timestamp is required."
            )

        timestamp = self._parse_timestamp(verified_at)

        if batch.received_at is not None and timestamp < batch.received_at:
            raise InventoryError(
                "Verification cannot occur before receipt."
            )

        if timestamp >= batch.expiry_date:
            raise InventoryError(
                "An expired batch cannot be verified."
            )

        batch.verified = True
        batch.requires_verification = False
        self.verification_times[batch_id] = timestamp

    def get_allocatable_batches(
        self,
        depot_id: str,
        item_id: str,
        current_time: datetime
    ) -> list[StockBatch]:
        """Return usable batches in FEFO order."""
        eligible = [
            batch
            for batch in self.batches.values()
            if batch.depot_id == depot_id
            and batch.item_id == item_id
            and batch.can_allocate(current_time)
        ]

        return sorted(
            eligible,
            key=lambda batch: (batch.expiry_date, batch.batch_id)
        )

    def get_available_stock(
        self,
        depot_id: str,
        item_id: str,
        current_time: datetime
    ) -> int:
        """Calculate total allocatable stock."""
        batches = self.get_allocatable_batches(
            depot_id, item_id, current_time
        )

        return sum(batch.quantity for batch in batches)

    def deduct_stock(
        self,
        depot_id: str,
        item_id: str,
        quantity: int,
        current_time: datetime
    ) -> list[tuple[str, int]]:
        """Deduct stock using FEFO order."""
        if (
            not isinstance(quantity, int)
            or isinstance(quantity, bool)
            or quantity <= 0
        ):
            raise InventoryError(
                "Deduction quantity must be a positive integer."
            )

        batches = self.get_allocatable_batches(
            depot_id, item_id, current_time
        )

        available = sum(batch.quantity for batch in batches)

        if quantity > available:
            raise InventoryError(
                f"Insufficient stock. Available: {available}, "
                f"requested: {quantity}."
            )

        remaining = quantity
        deductions = []

        for batch in batches:
            if remaining == 0:
                break

            deducted = min(batch.quantity, remaining)
            batch.quantity -= deducted
            remaining -= deducted

            deductions.append((batch.batch_id, deducted))

        return deductions

    def write_off_expired(self, current_time: datetime) -> list[dict]:
        """Write off expired stock at the start of a cycle."""
        current_time = self._parse_timestamp(current_time)
        new_write_offs = []

        for batch in self.batches.values():
            if batch.quantity > 0 and batch.is_expired(current_time):
                record = {
                    "batch_id": batch.batch_id,
                    "depot_id": batch.depot_id,
                    "item_id": batch.item_id,
                    "quantity": batch.quantity,
                    "write_off_ts": current_time,
                }

                new_write_offs.append(record)
                batch.quantity = 0

        self.write_offs.extend(new_write_offs)
        return new_write_offs

    def _get_batch(self, batch_id: str) -> StockBatch:
        """Retrieve a batch or raise an error."""
        if batch_id not in self.batches:
            raise InventoryError(
                f"Batch '{batch_id}' does not exist."
            )

        return self.batches[batch_id]
