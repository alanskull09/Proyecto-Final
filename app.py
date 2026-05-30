from flask import Flask, render_template, request, redirect, url_for, flash
from sbac.core import SBAC
import os

app = Flask(__name__)
app.secret_key = 'sbac_secreto_super_seguro'
sbac_app = SBAC()

@app.route('/')
def index():
    is_init = os.path.exists(".sbac")
    tracked_files = sbac_app.status() if is_init else {'staged': [], 'modified': [], 'untracked': []}
    history = sbac_app.history() if is_init else []
    baselines = sbac_app.list_baselines() if is_init else {}
    
    # Combinamos los archivos modificados y no rastreados para el autocompletado
    all_suggested_files = tracked_files['modified'] + tracked_files['untracked']
    
    return render_template('index.html', is_init=is_init, files=tracked_files, history=history, baselines=baselines, all_files=all_suggested_files)

@app.route('/init', methods=['POST'])
def init_repo():
    flash(sbac_app.init(), "success")
    return redirect(url_for('index'))

@app.route('/add', methods=['POST'])
def add_file():
    filename = request.form.get('filename')
    try:
        flash(sbac_app.add(filename), "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('index'))

@app.route('/commit', methods=['POST'])
def make_commit():
    msg = request.form.get('message')
    try:
        flash(sbac_app.commit(msg), "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('index'))

# NUEVA RUTA: Para eliminar commits
@app.route('/delete_commit/<commit_id>', methods=['POST'])
def delete_commit(commit_id):
    try:
        flash(sbac_app.delete_commit(commit_id), "success")
    except Exception as e:
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)