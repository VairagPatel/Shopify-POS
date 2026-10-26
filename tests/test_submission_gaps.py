"""Final-scope cash movement and India business-day acceptance checks."""

from app.gateways.billing import BillingAdapter
from app.services.reporting import DayEndService
from test_production_matrix import production_env, identity_template, backend


# A reasoned cash addition and withdrawal must reconcile and survive reopening the connection.
def test_paid_in_expense_and_counted_close(production_env):
    clients, store, _, _ = production_env
    cashier = clients("cashier")
    assert (
        cashier.post(
            "/api/till/open", json={"store_code": "HSR", "amount_paise": 100000}
        ).status_code
        == 200
    )
    assert (
        cashier.post(
            "/api/till/paid-in",
            json={
                "store_code": "HSR",
                "amount_paise": 50000,
                "reason": "Manager cash top up",
            },
        ).status_code
        == 200
    )
    assert (
        cashier.post(
            "/api/till/expense",
            json={"store_code": "HSR", "amount_paise": 10000, "reason": "Courier"},
        ).status_code
        == 200
    )
    summary = cashier.get("/api/till", params={"store_code": "HSR"}).json()
    assert summary["paid_ins_paise"] == 50000
    assert summary["expected_paise"] == 140000
    assert summary["paid_ins"][0]["actor"] == "cashier"
    for invalid in (
        {"amount_paise": 0, "reason": "top up"},
        {"amount_paise": 1, "reason": " "},
    ):
        assert (
            cashier.post(
                "/api/till/paid-in", json={"store_code": "HSR", **invalid}
            ).status_code
            == 422
        )
    close = clients("manager").post(
        "/api/till/close", json={"store_code": "HSR", "amount_paise": 140000}
    )
    assert close.status_code == 200, close.text
    assert close.json()["variance_paise"] == 0
    assert (
        cashier.post(
            "/api/till/paid-in",
            json={"store_code": "HSR", "amount_paise": 100, "reason": "top up"},
        ).status_code
        == 409
    )


class MidnightOrders:
    # Supply a neutral test double with the current source report contract.
    def locations(self):
        return [{"id": 1, "eluno": {"store_code": "HSR", "kind": "store"}}]

    # An evening UTC sale belongs to the next India business day.
    def orders(self, limit=250):
        return [
            {
                "id": 10,
                "location_id": 1,
                "created_at": "2026-10-25T20:00:00+00:00",
                "total_price": "112.00",
                "line_items": [
                    {
                        "price": "112.00",
                        "quantity": 1,
                        "total_discount": "0.00",
                        "tax_lines": [{"price": "12.00"}],
                    }
                ],
                "transactions": [
                    {
                        "kind": "sale",
                        "status": "success",
                        "amount": "112.00",
                        "gateway": "cash",
                    }
                ],
            }
        ]


# Date selection must reflect store time, not the source server's offset.
def test_day_end_uses_india_date():
    reporting = DayEndService(BillingAdapter(MidnightOrders()))
    assert reporting.report("HSR", "2026-10-25")["bill_count"] == 0
    result = reporting.report("HSR", "2026-10-26")
    assert result["bill_count"] == 1
    assert result["gross_paise"] == 11200
    assert result["taxable_paise"] == 10000
    assert result["payment_methods"] == {"cash": 11200}
