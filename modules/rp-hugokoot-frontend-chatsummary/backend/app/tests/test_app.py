from unittest.mock import patch
from app.tests.conftest import AnyStringWith

def test_hello(client):
    response = client.get('/')
    assert b'Hello' in response.data


def test_response(client, message_data):
    with patch('flask_sse.sse') as sse:
        res = client.post(f"/process", json=message_data)
        sse.publish.assert_called_once_with(message_data, type='response')
        assert res.status_code == 200 and len(res.text) > 0


def test_submit(client, sentence_data, triple_address):
    with patch('app.routes.requests') as r:
        res = client.post(f"/submit", json=sentence_data)

        r.post.assert_called_with(AnyStringWith(triple_address), json=sentence_data)
        assert res.status_code == 200 and sentence_data['sentence'] in res.text


