def test_dashboard_returns_200(client):
    response = client.get("/")

    assert response.status_code == 200
    assert b"PokerSpot" in response.data


def test_leo_returns_200_with_image_and_animation_button(client):
    response = client.get("/leo")

    assert response.status_code == 200
    assert b"/static/leo.png" in response.data
    assert b"ALL-IN" in response.data


def test_health_returns_ok(client):
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.get_json()

    assert payload == {
        "status": "ok",
        "application": "Pokerturneringsapp",
    }
