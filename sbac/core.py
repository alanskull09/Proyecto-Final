import os
import sqlite3
import hashlib
import zlib
import difflib
import fnmatch
from datetime import datetime

SBAC_DIR = ".sbac"
DB_FILE = os.path.join(SBAC_DIR, "index.db")
OBJECTS_DIR = os.path.join(SBAC_DIR, "objects")
IGNORE_FILE = ".sbacignore"

class SBAC:
    def __init__(self):
        self.conn = None
        if os.path.exists(DB_FILE):
            # Aquí está la primera corrección
            self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

    def _init_db(self):
        # Y aquí está la segunda corrección
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS tracked_files (filepath TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS commits (id TEXT PRIMARY KEY, message TEXT, timestamp TEXT);
            CREATE TABLE IF NOT EXISTS commit_files (commit_id TEXT, filepath TEXT, blob_hash TEXT, FOREIGN KEY(commit_id) REFERENCES commits(id));
            CREATE TABLE IF NOT EXISTS baselines (name TEXT PRIMARY KEY, commit_id TEXT, FOREIGN KEY(commit_id) REFERENCES commits(id));
        """)
        self.conn.commit()

    def _get_ignored_patterns(self):
        if not os.path.exists(IGNORE_FILE):
            return [SBAC_DIR + "/*"]
        with open(IGNORE_FILE, "r") as f:
            patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        patterns.append(SBAC_DIR + "/*")
        return patterns

    def _is_ignored(self, filepath):
        patterns = self._get_ignored_patterns()
        for p in patterns:
            if fnmatch.fnmatch(filepath, p):
                return True
        return False

    def _write_blob(self, filepath):
        """Comprime y guarda el archivo referenciado por su hash (simulando Git objects)"""
        with open(filepath, 'rb') as f:
            content = f.read()
        blob_hash = hashlib.sha1(content).hexdigest()
        blob_path = os.path.join(OBJECTS_DIR, blob_hash)
        
        if not os.path.exists(blob_path):
            compressed_data = zlib.compress(content)
            with open(blob_path, 'wb') as f:
                f.write(compressed_data)
        return blob_hash

    def _read_blob(self, blob_hash):
        """Descomprime y lee un blob desde el almacenamiento"""
        blob_path = os.path.join(OBJECTS_DIR, blob_hash)
        if not os.path.exists(blob_path):
            return []
        with open(blob_path, 'rb') as f:
            decompressed_data = zlib.decompress(f.read())
        return decompressed_data.decode('utf-8', errors='replace').splitlines(keepends=True)

    def init(self):
        if os.path.exists(SBAC_DIR):
            return "El repositorio ya está inicializado."
        os.makedirs(OBJECTS_DIR)
        self._init_db()
        return "Repositorio SBAC inicializado con motor SQLite y Blob Storage."

    def add(self, filepath):
        if self._is_ignored(filepath):
            raise Exception(f"El archivo '{filepath}' está ignorado por .sbacignore.")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"El archivo '{filepath}' no existe.")
        
        cursor = self.conn.cursor()
        try:
            cursor.execute("INSERT INTO tracked_files (filepath) VALUES (?)", (filepath,))
            self.conn.commit()
            return f"Archivo '{filepath}' añadido al index de SQLite."
        except sqlite3.IntegrityError:
            return f"El archivo '{filepath}' ya está en seguimiento."

    def status(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT filepath FROM tracked_files")
        return [row[0] for row in cursor.fetchall()]

    def commit(self, message):
        tracked = self.status()
        if not tracked:
            raise Exception("No hay archivos en seguimiento para hacer commit.")
        
        commit_id = hashlib.sha1(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
        timestamp = str(datetime.now())
        
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO commits (id, message, timestamp) VALUES (?, ?, ?)", (commit_id, message, timestamp))
        
        for filepath in tracked:
            if os.path.exists(filepath):
                blob_hash = self._write_blob(filepath)
                cursor.execute("INSERT INTO commit_files (commit_id, filepath, blob_hash) VALUES (?, ?, ?)", (commit_id, filepath, blob_hash))
        
        self.conn.commit()
        return f"Commit {commit_id} ejecutado de forma transaccional."

    def history(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, timestamp, message FROM commits ORDER BY timestamp DESC")
        return [{"id": r[0], "timestamp": r[1], "message": r[2]} for r in cursor.fetchall()]

    def baseline(self, name, commit_id=None):
        cursor = self.conn.cursor()
        if not commit_id:
            cursor.execute("SELECT id FROM commits ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                raise Exception("No hay commits para marcar.")
            commit_id = row[0]
        
        cursor.execute("SELECT id FROM commits WHERE id = ?", (commit_id,))
        if not cursor.fetchone():
            raise Exception(f"Commit '{commit_id}' no encontrado en la base de datos.")

        try:
            cursor.execute("INSERT OR REPLACE INTO baselines (name, commit_id) VALUES (?, ?)", (name, commit_id))
            self.conn.commit()
        except sqlite3.Error as e:
            raise Exception(f"Error de base de datos: {e}")
        
        return f"Línea base '{name}' enlazada al commit {commit_id}."

    def list_baselines(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name, commit_id FROM baselines")
        return {row[0]: row[1] for row in cursor.fetchall()}

    def _resolve_version(self, version):
        cursor = self.conn.cursor()
        cursor.execute("SELECT commit_id FROM baselines WHERE name = ?", (version,))
        row = cursor.fetchone()
        if row: return row[0]
        
        cursor.execute("SELECT id FROM commits WHERE id = ?", (version,))
        if cursor.fetchone(): return version
        raise Exception(f"Referencia '{version}' no encontrada.")

    def diff(self, v1, v2):
        id1 = self._resolve_version(v1)
        id2 = self._resolve_version(v2)

        cursor = self.conn.cursor()
        cursor.execute("SELECT filepath, blob_hash FROM commit_files WHERE commit_id = ?", (id1,))
        files1 = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute("SELECT filepath, blob_hash FROM commit_files WHERE commit_id = ?", (id2,))
        files2 = {row[0]: row[1] for row in cursor.fetchall()}

        all_files = set(files1.keys()).union(set(files2.keys()))
        diff_results = []

        for f in all_files:
            lines1 = self._read_blob(files1[f]) if f in files1 else []
            lines2 = self._read_blob(files2[f]) if f in files2 else []
            
            diff_output = list(difflib.unified_diff(lines1, lines2, fromfile=f"{f} ({v1})", tofile=f"{f} ({v2})"))
            if diff_output:
                diff_results.append((f, diff_output))
        return diff_results

    def checkout(self, version):
        commit_id = self._resolve_version(version)
        cursor = self.conn.cursor()
        cursor.execute("SELECT filepath, blob_hash FROM commit_files WHERE commit_id = ?", (commit_id,))
        
        for row in cursor.fetchall():
            filepath, blob_hash = row[0], row[1]
            content = b"".join([line.encode('utf-8') for line in self._read_blob(blob_hash)])
            
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
            with open(filepath, 'wb') as f:
                f.write(content)
        
        return f"Árbol de trabajo restaurado al estado del commit {commit_id}."