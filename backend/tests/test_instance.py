"""Phase SH-13: which instance is answering.

The label is derived from CRUCIBLE_INSTANCE, the same name the scripts use
for the container, so the page and the terminal can never disagree.
"""

from app import instance as inst
from app.routers import instance as instance_router


def test_label_default_is_prod_and_named_is_capitalised():
    assert inst.instance_label("", "") == "Prod"
    assert inst.instance_label("beta", "") == "Beta"
    assert inst.instance_label("uat-2", "") == "Uat-2"


def test_label_override_wins():
    assert inst.instance_label("", "Production") == "Production"
    assert inst.instance_label("beta", "Staging") == "Staging"


def test_endpoint_shape_and_consistency(client):
    res = client.get("/api/instance")
    assert res.status_code == 200
    body = res.json()
    assert set(body.keys()) == {"name", "label", "port", "https"}
    assert isinstance(body["port"], int)
    assert isinstance(body["https"], bool)
    # whatever the environment says, the label follows the name by the one rule
    assert body["label"] == inst.instance_label(body["name"], instance_router.CRUCIBLE_INSTANCE_LABEL)


def test_endpoint_as_the_beta_container_sees_it(client, monkeypatch):
    monkeypatch.setattr(instance_router, "CRUCIBLE_INSTANCE", "beta")
    monkeypatch.setattr(instance_router, "CRUCIBLE_INSTANCE_LABEL", "")
    monkeypatch.setattr(instance_router, "PORT", 49161)
    body = client.get("/api/instance").json()
    assert body == {"name": "beta", "label": "Beta", "port": 49161, "https": body["https"]}


def test_endpoint_with_an_override(client, monkeypatch):
    monkeypatch.setattr(instance_router, "CRUCIBLE_INSTANCE", "")
    monkeypatch.setattr(instance_router, "CRUCIBLE_INSTANCE_LABEL", "Production")
    assert client.get("/api/instance").json()["label"] == "Production"
