import os
import shutil
import unittest
import time
import sbac.core

# Aislamos las pruebas en una carpeta temporal para no tocar tu repositorio real
TEST_DIR = ".sbac_test"
sbac.core.SBAC_DIR = TEST_DIR
sbac.core.DB_FILE = os.path.join(TEST_DIR, "index.db")
sbac.core.OBJECTS_DIR = os.path.join(TEST_DIR, "objects")

from sbac.core import SBAC

class TestSBAC(unittest.TestCase):
    def setUp(self):
        self.cleanup()
        self.app = SBAC()
        self.test_file = "test_code.py"
        with open(self.test_file, "w") as f:
            f.write("def suma(a, b):\n    return a + b\n")

    def tearDown(self):
        self.cleanup()
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def cleanup(self):
        # Forzamos el cierre de la conexión de SQLite para que Windows libere el archivo
        if hasattr(self, 'app') and self.app and self.app.conn:
            try:
                self.app.conn.close()
            except Exception:
                pass
        
        if os.path.exists(TEST_DIR):
            try:
                shutil.rmtree(TEST_DIR)
            except Exception:
                time.sleep(0.5)
                shutil.rmtree(TEST_DIR, ignore_errors=True)

    def test_01_init_creates_structure(self):
        """Prueba Unitaria: Verifica que init cree la base de datos y carpetas"""
        res = self.app.init()
        self.assertTrue(os.path.exists(sbac.core.DB_FILE))
        self.assertTrue(os.path.exists(sbac.core.OBJECTS_DIR))
        self.assertIn("Staging y Objects", res)

    def test_02_add_moves_to_staging(self):
        """Prueba Unitaria: Verifica que add() marque el archivo como staged=1"""
        self.app.init()
        self.app.add(self.test_file)
        
        cursor = self.app.conn.cursor()
        cursor.execute("SELECT staged FROM tracked_files WHERE filepath=?", (self.test_file,))
        row = cursor.fetchone()
        self.assertIsNotNone(row, "El archivo no se guardó en la BD")
        self.assertEqual(row[0], 1, "El archivo no se marcó como staged (1)")

        st = self.app.status()
        self.assertIn(self.test_file, st["staged"])

    def test_03_integration_add_commit_diff(self):
        """Prueba de Integración: Flujo completo de Add -> Commit -> Modificar -> Diff"""
        self.app.init()
        self.app.add(self.test_file)
        self.app.commit("commit_inicial")
        
        hist = self.app.history()
        self.assertEqual(len(hist), 1)
        
        with open(self.test_file, "w") as f:
            f.write("def suma(a, b, c=0):\n    return a + b + c\n")
        
        self.app.add(self.test_file)
        self.app.commit("segundo_commit")
        
        id_v1 = hist[0]['id']
        id_v2 = self.app.history()[0]['id']
        diffs = self.app.diff(id_v1, id_v2)
        
        self.assertTrue(len(diffs) > 0, "No se detectaron diferencias entre los commits")

    def test_04_regression_checkout(self):
        """Prueba de Regresión: Verificar que checkout revierte daños indeseados"""
        self.app.init()
        self.app.add(self.test_file)
        self.app.commit("version_correcta")
        v1_id = self.app.history()[0]['id']
        
        with open(self.test_file, "a") as f:
            f.write("\n# Bug introducido por error\n")
        self.app.add(self.test_file)
        self.app.commit("version_con_error")
        
        self.app.checkout(v1_id)
        
        with open(self.test_file, "r") as f:
            content = f.read()
        self.assertNotIn("# Bug introducido por error", content)

if __name__ == '__main__':
    unittest.main(verbosity=2)