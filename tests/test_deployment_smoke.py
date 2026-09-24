def test_health_endpoint(
    client,
):
    response = client.get(
        "/health"
    )

    assert (
        response.status_code
        == 200
    )

    payload = (
        response.get_json()
    )

    assert payload == {
        "status": "ok",
        "application": (
            "Pokerturneringsapp"
        ),
    }


def test_dashboard_smoke(
    client,
):
    response = client.get(
        "/"
    )

    assert (
        response.status_code
        == 200
    )

    page = response.get_data(
        as_text=True
    )

    assert "POKERSPOT" in page


def test_static_css_exists(
    client,
):
    response = client.get(
        "/static/css/app.css"
    )

    assert (
        response.status_code
        == 200
    )


def test_static_javascript_exists(
    client,
):
    response = client.get(
        "/static/js/app.js"
    )

    assert (
        response.status_code
        == 200
    )