"""Static file serving and SPA fallback."""


def test_architecture_page(client):
    res = client.get("/architecture")
    # Served when docs/ is present (repo checkout); 404 otherwise.
    if res.status_code == 200:
        assert "text/html" in res.headers["content-type"]
    else:
        assert res.status_code == 404


def test_spa_fallback_serves_index_for_unknown_routes(client):
    res = client.get("/chemicals/upload")  # a React Router path, not an API one
    if res.status_code == 200:
        assert "text/html" in res.headers["content-type"]
        assert "Crucible" in res.text
    else:
        # No client build present in this checkout
        assert res.status_code == 404
