from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_analyze_prompt():
    response = client.post('/api/analyze', json={'prompt': 'Ich brauche KI für Python coding und debugging', 'top_k': 3})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 3
    assert payload[0]['score'] >= payload[-1]['score']


def test_search_filters():
    response = client.get('/api/search', params={'category': 'coding', 'min_popularity': 4.0})
    assert response.status_code == 200
    payload = response.json()
    assert payload
    assert all(item['popularity'] >= 4.0 for item in payload)
