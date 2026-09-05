import pytest

from dispatch.models import SignupRequest, ValidationError, WorkOrder
from dispatch.work_orders import DispatchError, WorkOrderBoard


@pytest.fixture()
def board() -> WorkOrderBoard:
    b = WorkOrderBoard()
    b.add(WorkOrder(order_id="WO-9001", site="Modesto plant", problem="thermostat drift"))
    return b


def test_visit_without_a_photo_becomes_follow_up(board):
    board.dispatch("WO-9001", "rosa@fieldsvc.test")
    board._move(board.get("WO-9001"), "on_site")

    order = board.close("WO-9001")

    assert order.status == "needs_follow_up"
    assert order.follow_up_note == "no site photo on file"


def test_documented_visit_closes(board):
    board.dispatch("WO-9001", "rosa@fieldsvc.test")
    board._move(board.get("WO-9001"), "on_site")
    board.attach_photo("WO-9001", "wo-9001/thermostat.jpg", "new unit installed")

    order = board.close("WO-9001", "recheck in 30 days")

    assert order.status == "closed"
    assert order.follow_up_note == "recheck in 30 days"
    assert "on_site -> closed" in order.history


def test_closed_order_refuses_more_photos(board):
    board.dispatch("WO-9001", "rosa@fieldsvc.test")
    board._move(board.get("WO-9001"), "on_site")
    board.attach_photo("WO-9001", "a.jpg", "before")
    board.close("WO-9001")

    with pytest.raises(DispatchError):
        board.attach_photo("WO-9001", "b.jpg", "after")


def test_signup_request_rejects_short_password():
    with pytest.raises(ValidationError):
        SignupRequest.parse({"email": "rosa@fieldsvc.test", "password": "short", "captcha_token": "t"})
