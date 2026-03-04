from app.main import app
from fastapi.testclient import TestClient

c = TestClient(app)
resp = c.post('/token', data={'username':'admin@example.com', 'password':'adminpassword'})
print('STATUS', resp.status_code)
print('HEADERS', resp.headers)
print('BODY', resp.text)
