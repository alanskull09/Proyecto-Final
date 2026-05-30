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
            self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row

    def _init_db(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS tracked_files (
                filepath TEXT PRIMARY KEY,
                blob_hash TEXT,
                staged INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS commits (
                id TEXT PRIMARY KEY,
                message TEXT,
                timestamp TEXT,
                parent_id TEXT
            );
            CREATE TABLE IF NOT EXISTS commit_files (
                commit_id TEXT,
                filepath TEXT,
                blob_hash TEXT,
                FOREIGN KEY(commit_id) REFERENCES commits(id)
            );
            CREATE TABLE IF NOT EXISTS baselines (
                name TEXT PRIMARY KEY,
                commit_id TEXT,
                FOREIGN KEY(commit_id) REFERENCES commits(id)
            );
        """)
        self.conn.commit()

    def _get_ignored_patterns(self):
        if not os.path.exists(IGNORE_FILE):
            return [SBAC_DIR + "/*"]
        with open(IGNORE_FILE, "r") as f:
            patterns = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        patterns.append(SBAC_DIR + "/*")
        patterns.append("__pycache__/*")
        return patterns

    def _is_ignored(self, filepath):
        patterns = self._get_ignored_patterns()
        for p in patterns:
            if fnmatch.fnmatch(filepath, p) or fnmatch.fnmatch(filepath.split('/')[0], p):
                return True
        return False

    def _calculate_hash(self, filepath):
        hasher = hashlib.sha1()
        with open(filepath, 'rb') as f:
            content = f.read()
            hasher.update(content)
        return hasher.hexdigest(), content

    def _write_blob(self, filepath):
        blob_hash, content = self._calculate_hash(filepath)
        folder = os.path.join(OBJECTS_DIR, blob_hash[:2])
        os.makedirs(folder, exist_ok=True)
        blob_path = os.path.join(folder, blob_hash[2:])
        
        if not os.path.exists(blob_path):
            compressed_data = zlib.compress(content)
            with open(blob_path, 'wb') as f:
                f.write(compressed_data)
        return blob_hash

    def _read_blob(self, blob_hash):
        folder = os.path.join(OBJECTS_DIR, blob_hash[:2])
        blob_path = os.path.join(folder, blob_hash[2:])
        if not os.path.exists(blob_path):
            old_path = os.path.join(OBJECTS_DIR, blob_hash)
            if os.path.exists(old_path):
                blob_path = old_path
            else:
                return []
                
        with open(blob_path, 'rb') as f:
            decompressed_data = zlib.decompress(f.read())
        return decompressed_data.decode('utf-8', errors='replace').splitlines(keepends=True)

    def init(self):
        if os.path.exists(SBAC_DIR):
            return "El repositorio ya está inicializado."
        os.makedirs(OBJECTS_DIR)
        self._init_db()
        return "Repositorio SBAC inicializado con estructura de Staging y Objects."

    def add(self, filepath):
        if self._is_ignored(filepath):
            raise Exception(f"El archivo '{filepath}' está ignorado.")
        
        cursor = self.conn.cursor()
        
        # 1. Soporte para archivos eliminados físicamente
        if not os.path.exists(filepath):
            cursor.execute("SELECT filepath FROM tracked_files WHERE filepath = ?", (filepath,))
            if cursor.fetchone():
                cursor.execute("UPDATE tracked_files SET staged = 1, blob_hash = '' WHERE filepath = ?", (filepath,))
                self.conn.commit()
                return f"Eliminación de '{filepath}' preparada para el commit."
            else:
                raise FileNotFoundError(f"El archivo '{filepath}' no existe.")
        
        # 2. Soporte para archivos normales
        blob_hash = self._write_blob(filepath)
        cursor.execute("""
            INSERT INTO tracked_files (filepath, blob_hash, staged) 
            VALUES (?, ?, 1)
            ON CONFLICT(filepath) DO UPDATE SET blob_hash=excluded.blob_hash, staged=1
        """, (filepath, blob_hash))
        self.conn.commit()
        return f"Archivo '{filepath}' añadido al staging area."

    def status(self):
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT filepath FROM tracked_files WHERE staged = 1")
        staged = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT filepath, blob_hash FROM tracked_files")
        tracked = {row[0]: row[1] for row in cursor.fetchall()}
        
        modified = []
        for filepath, db_hash in tracked.items():
            if filepath not in staged:
                if os.path.exists(filepath):
                    current_hash, _ = self._calculate_hash(filepath)
                    if current_hash != db_hash:
                        modified.append(filepath)
                else:
                    modified.append(f"{filepath} (eliminado)")
                    
        untracked = []
        for root, dirs, files in os.walk("."):
            if ".sbac" in dirs: dirs.remove(".sbac")
            if "__pycache__" in dirs: dirs.remove("__pycache__")
            for file in files:
                full_path = os.path.relpath(os.path.join(root, file), ".")
                if not self._is_ignored(full_path) and full_path not in tracked:
                    untracked.append(full_path)
                    
        return {"staged": staged, "modified": modified, "untracked": untracked}

    def commit(self, message):
        cursor = self.conn.cursor()
        cursor.execute("SELECT filepath, blob_hash FROM tracked_files WHERE staged = 1")
        staged_files = cursor.fetchall()
        
        if not staged_files:
            raise Exception("No hay archivos en staging (add) para hacer commit.")
        
        cursor.execute("SELECT id FROM commits ORDER BY timestamp DESC LIMIT 1")
        parent_row = cursor.fetchone()
        parent_id = parent_row[0] if parent_row else None
        
        commit_id = hashlib.sha1(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
        timestamp = str(datetime.now())
        
        cursor.execute("INSERT INTO commits (id, message, timestamp, parent_id) VALUES (?, ?, ?, ?)", 
                       (commit_id, message, timestamp, parent_id))
        
        for filepath, blob_hash in staged_files:
            if blob_hash == '':
                # Si es una eliminación oficial, lo borramos del rastreo continuo
                cursor.execute("DELETE FROM tracked_files WHERE filepath = ?", (filepath,))
            else:
                cursor.execute("INSERT INTO commit_files (commit_id, filepath, blob_hash) VALUES (?, ?, ?)", 
                               (commit_id, filepath, blob_hash))
                cursor.execute("UPDATE tracked_files SET staged = 0 WHERE filepath = ?", (filepath,))
        
        self.conn.commit()
        return f"Commit {commit_id} ejecutado correctamente."

    def delete_commit(self, commit_id):
        cursor = self.conn.cursor()
        
        # Obtener el padre del commit que vamos a borrar
        cursor.execute("SELECT parent_id FROM commits WHERE id = ?", (commit_id,))
        row = cursor.fetchone()
        if not row:
            raise Exception(f"El commit '{commit_id}' no existe.")
        parent_id = row[0]
        
        # Obtener cómo estaban los archivos en el commit padre
        parent_files = {}
        if parent_id:
            cursor.execute("SELECT filepath, blob_hash FROM commit_files WHERE commit_id = ?", (parent_id,))
            parent_files = {r[0]: r[1] for r in cursor.fetchall()}
        
        # Identificar qué archivos fueron afectados en este commit que se va a borrar
        cursor.execute("SELECT filepath FROM commit_files WHERE commit_id = ?", (commit_id,))
        files_in_commit = [r[0] for r in cursor.fetchall()]
        
        # Borrar permanentemente el commit de la base de datos
        cursor.execute("DELETE FROM baselines WHERE commit_id = ?", (commit_id,))
        cursor.execute("DELETE FROM commit_files WHERE commit_id = ?", (commit_id,))
        cursor.execute("DELETE FROM commits WHERE id = ?", (commit_id,))
        
        # MAGIA DE RESTAURACIÓN: Revertir la memoria de seguimiento (tracked_files) al pasado
        for filepath in files_in_commit:
            if filepath in parent_files:
                # Si el archivo ya existía antes, le regresamos su hash antiguo
                cursor.execute("UPDATE tracked_files SET blob_hash = ?, staged = 0 WHERE filepath = ?", 
                               (parent_files[filepath], filepath))
            else:
                # Si el archivo fue un invento nuevo de este commit, lo sacamos de la memoria (volverá a ser "No rastreado")
                cursor.execute("DELETE FROM tracked_files WHERE filepath = ?", (filepath,))
        
        # Restaurar archivos que hayan sido eliminados en el commit que estamos borrando
        for filepath, p_hash in parent_files.items():
            cursor.execute("SELECT filepath FROM tracked_files WHERE filepath = ?", (filepath,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO tracked_files (filepath, blob_hash, staged) VALUES (?, ?, 0)", 
                               (filepath, p_hash))
        
        self.conn.commit()
        return f"Commit {commit_id[:8]} eliminado. Los archivos volvieron a su estado anterior para un nuevo commit."

    def history(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, timestamp, message, parent_id FROM commits ORDER BY timestamp DESC")
        return [{"id": r[0], "timestamp": r[1], "message": r[2], "parent_id": r[3]} for r in cursor.fetchall()]

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
            raise Exception(f"Commit '{commit_id}' no encontrado.")

        cursor.execute("INSERT OR REPLACE INTO baselines (name, commit_id) VALUES (?, ?)", (name, commit_id))
        self.conn.commit()
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

    def diff(self, v1, v2=None):
        id1 = self._resolve_version(v1)
        cursor = self.conn.cursor()
        cursor.execute("SELECT filepath, blob_hash FROM commit_files WHERE commit_id = ?", (id1,))
        files1 = {row[0]: row[1] for row in cursor.fetchall()}
        
        diff_results = []

        if v2:
            id2 = self._resolve_version(v2)
            cursor.execute("SELECT filepath, blob_hash FROM commit_files WHERE commit_id = ?", (id2,))
            files2 = {row[0]: row[1] for row in cursor.fetchall()}
            
            all_files = set(files1.keys()).union(set(files2.keys()))
            for f in all_files:
                lines1 = self._read_blob(files1[f]) if f in files1 else []
                lines2 = self._read_blob(files2[f]) if f in files2 else []
                diff_output = list(difflib.unified_diff(lines1, lines2, fromfile=f"{f} ({v1})", tofile=f"{f} ({v2})"))
                if diff_output:
                    diff_results.append((f, diff_output))
        else:
            for f in files1.keys():
                lines1 = self._read_blob(files1[f])
                lines_actual = []
                if os.path.exists(f):
                    with open(f, 'r', encoding='utf-8', errors='replace') as file:
                        lines_actual = file.readlines()
                
                diff_output = list(difflib.unified_diff(lines1, lines_actual, fromfile=f"{f} ({v1})", tofile=f"{f} (Actual)"))
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
        
        return f"Árbol de trabajo restaurado al estado de {version} (Commit {commit_id})."