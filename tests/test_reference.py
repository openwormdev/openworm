"""Opt-in integration test: real exporter/compiler/NEURON through HTTP routes."""
import os
import time
import unittest
from fastapi.testclient import TestClient
from wormstreet.api import app, jobs
from wormstreet.core import digest


@unittest.skipUnless(os.getenv('WORM_RUN_INTEGRATION') == '1', 'Set WORM_RUN_INTEGRATION=1 for the real model gate')
class RealWorkerTests(unittest.TestCase):
    def test_real_job_and_static_dashboard(self):
        jobs.clear()
        with TestClient(app) as client:
            self.assertIn('Follow the signal.', client.get('/').text)
            self.assertEqual(client.get('/report.js').status_code,200)
            response=client.post('/api/jobs',json={'scenario':'reversal'})
            self.assertEqual(response.status_code,202)
            identifier=response.json()['id']
            deadline=time.monotonic()+300
            while time.monotonic()<deadline:
                result=client.get('/api/jobs/'+identifier).json()
                if result['status']!='running':break
                time.sleep(.5)
            self.assertEqual(result['status'],'complete',result.get('error','timeout'))
            report=result['report']
            self.assertEqual(report['model']['neurons'],302)
            self.assertEqual(report['model']['backend'],'neuron')
            self.assertEqual(report['simulation_mode'],'real-c302')
            saved_hash=report.pop('report_hash')
            self.assertEqual(saved_hash,digest(report))
            previous='genesis'
            for row in report['rows']:
                self.assertEqual(row['previous_hash'],previous)
                body={k:v for k,v in row.items() if k!='event_hash'}
                self.assertEqual(row['event_hash'],digest(body))
                previous=row['event_hash']
            self.assertEqual(previous,report['audit_root'])
            # The scene is synthetic; samples still have measured neural dynamics.
            trace=report['traces']['voltage_mv']['ASEL']
            self.assertGreater(max(trace)-min(trace),1.0)
