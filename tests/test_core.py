import os
import shutil
import unittest
from sbac.core import SBAC, SBAC_DIR, DB_FILE

class TestSBAC(unittest.TestCase):
    def setUp(self):
        if os.path.exists(SBAC_DIR):
            shutil.rmtree(SBAC_DIR, ignore_errors=True)
        self.app = SBAC()
        self.test_file = "test_code.py"
        with open(self.test_file, "w") as f:
            f.write("def suma(a, b):\n    return a + b\n")

    def tearDown(self):
        if self.app.conn:
            self.app.conn.close()
        if os.path.exists(SBAC_DIR):
            shutil.rmtree(SBAC_DIR, ignore_errors=True)
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    def test_01_init_db(self):
        res = self.app.init()
        self.assertTrue(os.path.exists(DB_FILE))
        self.assertIn("SQLite", res)

    def test_02_add_and_blob_creation(self):
        self.app.init()
        self.app.add(self.test_file)
        self.app.commit("init")
        
        # Validar que se creó el almacenamiento de blobs
        objects_dir = os.path.join(SBAC_DIR, "objects")
        self.assertTrue(len(os.listdir(objects_dir)) > 0)

    def test_03_full_transactional_flow(self):
        self.app.init()
        self.app.add(self.test_file)
        
        self.app.commit("v1")
        id_c1 = self.app.history()[0]['id']
        self.app.baseline("PROD_V1", id_c1)

        with open(self.test_file, "w") as f:
            f.write("def suma(a, b, c=0):\n    return a + b + c\n")
        
        self.app.commit("v2")
        id_c2 = self.app.history()[0]['id']

        diff_output = self.app.diff("PROD_V1", id_c2)
        self.assertTrue(len(diff_output) > 0)

        self.app.checkout("PROD_V1")
        with open(self.test_file, "r") as f:
            self.assertIn("return a + b", f.read())

    def test_04_ignore_file(self):
        self.app.init()
        with open(".sbacignore", "w") as f:
            f.write("*.tmp\n")
        
        tmp_file = "archivo.tmp"
        with open(tmp_file, "w") as f:
            f.write("basura")

        with self.assertRaises(Exception) as ctx:
            self.app.add(tmp_file)
        self.assertIn("ignorado por .sbacignore", str(ctx.exception))
        
        os.remove(tmp_file)
        os.remove(".sbacignore")

    def test_05_regression_checkout(self):
        """Prueba de regresión: Verificar que un checkout restaura exactamente el estado antiguo."""
        self.app.init()
        self.app.add(self.test_file)
        self.app.commit("version_limpia")
        
        # Introducir una modificación indeseada
        with open(self.test_file, "a") as f:
            f.write("\n# Linea introducida por error\n")
        self.app.commit("version_con_error")
        
        # Ejecutar la reversión (checkout)
        v1_id = self.app.history()[1]['id']
        self.app.checkout(v1_id)
        
        # Validar regresión: El archivo no debe contener el texto de la versión 2
        with open(self.test_file, "r") as f:
            content = f.read()
        self.assertNotIn("# Linea introducida por error", content)

if __name__ == '__main__':
    unittest.main(verbosity=2)