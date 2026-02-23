import unittest
from pathlib import Path
from db_utils import DatabaseManager
from models import JobStatus
import sqlite3
import tempfile
import os

class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.db = DatabaseManager(Path(self.temp_db.name))
        
    def tearDown(self):
        os.unlink(self.temp_db.name)
        
    def test_add_and_dequeue_job(self):
        self.assertTrue(self.db.add_job("/test/path.mkv"))
        self.assertFalse(self.db.add_job("/test/path.mkv")) # duplicate
        
        job = self.db.dequeue_pending_job()
        self.assertIsNotNone(job)
        job_id, path = job
        self.assertEqual(path, "/test/path.mkv")
        
        # Should be processing now
        job2 = self.db.dequeue_pending_job()
        self.assertIsNone(job2)
        
    def test_update_job_status(self):
        self.db.add_job("/test/path2.mkv")
        job = self.db.dequeue_pending_job()
        self.assertIsNotNone(job)
        job_id, path = job
        
        self.db.update_job_status(job_id, JobStatus.COMPLETED.value)
        
        with sqlite3.connect(self.temp_db.name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM jobs WHERE id=?", (job_id,))
            status = cursor.fetchone()[0]
            self.assertEqual(status, JobStatus.COMPLETED.value)
            
    def test_heuristics_profiles(self):
        self.db.save_successful_profile(1920, 1080, "h264", "yuv420p", 4, 30, 4)
        
        profile = self.db.get_best_profile(1920, 1080, "h264", "yuv420p")
        self.assertIsNotNone(profile)
        self.assertEqual(profile, (4, 30, 4)) # bf, lad, async_depth
        
        profile2 = self.db.get_best_profile(1280, 720, "h264", "yuv420p")
        self.assertIsNone(profile2)

if __name__ == '__main__':
    unittest.main()
