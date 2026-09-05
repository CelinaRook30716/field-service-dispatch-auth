"""The dispatch state machine plus photo attachment rules."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from .models import PhotoRef, WorkOrder

ALLOWED_TRANSITIONS: Dict[str, set] = {
    "unassigned": {"dispatched"},
    "dispatched": {"on_site", "unassigned"},
    "on_site": {"needs_follow_up", "closed"},
    "needs_follow_up": {"dispatched", "closed"},
    "closed": set(),
}


class DispatchError(Exception):
    pass


class WorkOrderBoard:
    def __init__(self) -> None:
        self._orders: Dict[str, WorkOrder] = {}

    def add(self, order: WorkOrder) -> WorkOrder:
        self._orders[order.order_id] = order
        return order

    def get(self, order_id: str) -> WorkOrder:
        order = self._orders.get(order_id)
        if not order:
            raise DispatchError(f"no work order {order_id}")
        return order

    def for_technician(self, email: str) -> List[WorkOrder]:
        return [o for o in self._orders.values() if o.technician_email == email]

    def dispatch(self, order_id: str, technician_email: str) -> WorkOrder:
        order = self.get(order_id)
        self._move(order, "dispatched")
        order.technician_email = technician_email
        return order

    def attach_photo(self, order_id: str, key: str, caption: str) -> WorkOrder:
        order = self.get(order_id)
        if order.status == "closed":
            raise DispatchError("a closed work order no longer accepts photos")
        order.photos.append(PhotoRef(key=key, caption=caption))
        order.history.append(f"photo {key} attached")
        return order

    def close(self, order_id: str, follow_up_note: Optional[str] = None) -> WorkOrder:
        """Close only when the visit is documented; otherwise ask for follow-up.

        A photo is the evidence a field visit happened, so an on-site order with
        zero photos moves to needs_follow_up instead of closing.
        """
        order = self.get(order_id)
        if not order.photos:
            self._move(order, "needs_follow_up")
            order.follow_up_note = follow_up_note or "no site photo on file"
            return order
        self._move(order, "closed")
        order.follow_up_note = follow_up_note
        return order

    def _move(self, order: WorkOrder, target: str) -> None:
        if target not in ALLOWED_TRANSITIONS[order.status]:
            raise DispatchError(f"cannot move {order.order_id} from {order.status} to {target}")
        order.history.append(f"{order.status} -> {target}")
        order.status = target  # type: ignore[assignment]


def seed_board(rows: Iterable[WorkOrder]) -> WorkOrderBoard:
    board = WorkOrderBoard()
    for row in rows:
        board.add(row)
    return board
