"""Priority scoring and deterministic request ranking (BR-18–23)."""
from datetime import datetime
from math import floor

from src.models.request import Urgency


class PriorityEngine:
    URGENCY_POINTS = {Urgency.CRITICAL: 25, Urgency.HIGH: 15, Urgency.NORMAL: 5}

    def __init__(self, camps, zones, last_deliveries=None):
        self.camps = camps
        self.zones = zones
        self.last_deliveries = last_deliveries if last_deliveries is not None else {}

    def score(self, managed, at: datetime) -> float:
        request = managed.request
        camp = self.camps[request.camp_id]
        zone = self.zones[camp.zone_id]
        delivered = self.last_deliveries.get((camp.camp_id, request.item_id))
        since = delivered or camp.opened_ts
        if since is None:
            since = request.requested_at
        if at.tzinfo is None or since.tzinfo is None:
            raise ValueError("Priority timestamps must be timezone-aware.")
        hours = max(0.0, (at - since).total_seconds() / 3600)
        waiting = min(10, floor(hours / 6))
        vulnerable = min(15.0, 15 * camp.vulnerable_count / camp.occupancy) if camp.occupancy else 0.0
        return zone.severity_level * 10 + self.URGENCY_POINTS[request.urgency] + vulnerable + waiting

    @staticmethod
    def band(score: float) -> int:
        return floor(score / 10)

    def rank(self, requests, at: datetime):
        scored = [(self.score(request, at), request) for request in requests]
        scored.sort(key=lambda pair: (-pair[0], -self.camps[pair[1].request.camp_id].occupancy,
                                      pair[1].request.camp_id))
        return scored
