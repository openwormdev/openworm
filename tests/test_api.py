import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from wormbrain.api import app, jobs


class ApiTests(unittest.TestCase):
    def setUp(self):
        jobs.clear();self.client=TestClient(app)

    def test_health_cannot_enable_real_trading(self):
        data=self.client.get('/api/health').json()
        self.assertFalse(data['live_execution']);self.assertEqual(data['mode'],'paper')

    def test_token_and_origin_enforced(self):
        with patch.dict(os.environ,{'WORM_WORKER_TOKEN':'test-only-not-a-real-credential'}):
            self.assertEqual(self.client.post('/api/jobs',json={'scenario':'trend'}).status_code,401)
        self.assertEqual(self.client.post('/api/jobs',json={'scenario':'trend'},headers={'Origin':'https://untrusted.invalid'}).status_code,403)

    def test_no_trade_endpoint(self):
        self.assertEqual(self.client.post('/api/trade',json={}).status_code,405)

    def test_bounded_inputs_and_busy_worker(self):
        self.assertEqual(self.client.post('/api/jobs',json={'scenario':'missing'}).status_code,422)
        self.assertEqual(self.client.post('/api/jobs',json={'scenario':'trend','amount':100}).status_code,422)
        jobs['test']={'status':'running'}
        self.assertEqual(self.client.post('/api/jobs',json={'scenario':'trend'}).status_code,429)

    def test_job_contract(self):
        with patch('wormbrain.api.executor.submit') as submit:
            response=self.client.post('/api/jobs',json={'scenario':'reversal'})
        self.assertEqual(response.status_code,202);submit.assert_called_once()
        identifier=response.json()['id']
        self.assertEqual(self.client.get('/api/jobs/'+identifier).json()['status'],'running')
        self.assertEqual(self.client.get('/api/jobs/unknown').status_code,404)
