from flask import Flask, render_template, request, url_for, send_file, redirect, flash
from flask_mail import Mail, Message
import qrcode
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'clave_secreta_segura'
app.config['UPLOAD_FOLDER'] = 'static/qr_codes'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Configuración de correo
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'rosariobus.unrc@gmail.com'
app.config['MAIL_PASSWORD'] = 'anqd meuh jylg amix'
mail = Mail(app)

# Inicializar base de datos
def init_db():
    with sqlite3.connect('registro.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alumnos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL,
                carrera TEXT NOT NULL,
                matricula TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS docentes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                correo TEXT NOT NULL,
                carrera TEXT NOT NULL,
                num_trabajador TEXT NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accesos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                persona_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
init_db()

@app.route('/')
def inicio():
    return render_template('tipo_form.html')

@app.route('/datos', methods=['POST'])
def datos():
    tipo = request.form['tipo']
    identificador = request.form.get('matricula') if tipo == 'alumno' else request.form.get('num_trabajador')
    return render_template('registro_form.html', tipo=tipo, identificador=identificador)

@app.route('/registrar', methods=['POST'])
def registrar():
    tipo = request.form['tipo']
    nombre = request.form['nombre'].strip()
    correo = request.form['correo'].strip()
    carrera = request.form['carrera']
    identificador = request.form['identificador'].strip()

    # Validación básica
    if not nombre or not correo or not carrera or not identificador:
        flash("Todos los campos son obligatorios.", "error")
        return redirect('/')

    with sqlite3.connect('registro.db') as conn:
        cursor = conn.cursor()
        if tipo == 'alumno':
            cursor.execute('INSERT INTO alumnos (nombre, correo, carrera, matricula) VALUES (?, ?, ?, ?)', 
                           (nombre, correo, carrera, identificador))
        else:
            cursor.execute('INSERT INTO docentes (nombre, correo, carrera, num_trabajador) VALUES (?, ?, ?, ?)', 
                           (nombre, correo, carrera, identificador))
        persona_id = cursor.lastrowid

    # Generar QR
    qr_filename = f'{tipo}_{persona_id}.png'
    qr_path = os.path.join(app.config['UPLOAD_FOLDER'], qr_filename)
    qr_url = url_for('ver_info', tipo=tipo, persona_id=persona_id, _external=True)
    qrcode.make(qr_url).save(qr_path)

    # Enviar correo con QR
    msg = Message('Boleto electrónico - RosarioBus', sender=app.config['MAIL_USERNAME'], recipients=[correo])

    # Texto con formato HTML
    msg.html = f"""
    <p>Hola {nombre}.</p>
    <p>Adjunto encontrarás el código QR que es tu pase de abordar al <strong>RosarioBus</strong>. No lo compartas con nadie, recuerda que es único e intransferible.</p>
    <p><em><strong>¡Libres, dignos y humanos, somos Rosario Castellanos!</strong></em></p>
    """
    # Adjuntar QR
    with open(qr_path, 'rb') as qr_file:
        msg.attach(qr_filename, 'image/png', qr_file.read())

    try:
        mail.send(msg)
    except Exception as e:
        print("Error al enviar correo:", e)

    return render_template('boleto.html', nombre=nombre, qr_file=qr_filename, tipo=tipo, persona_id=persona_id)

@app.route('/ver_info/<tipo>/<int:persona_id>')
def ver_info(tipo, persona_id):
    with sqlite3.connect('registro.db') as conn:
        cursor = conn.cursor()
        if tipo == 'alumno':
            cursor.execute('SELECT * FROM alumnos WHERE id = ?', (persona_id,))
        else:
            cursor.execute('SELECT * FROM docentes WHERE id = ?', (persona_id,))
        persona = cursor.fetchone()

        if persona:
            cursor.execute('INSERT INTO accesos (tipo, persona_id, timestamp) VALUES (?, ?, ?)',
                           (tipo, persona_id, datetime.now().isoformat()))
            cursor.execute('SELECT timestamp FROM accesos WHERE tipo = ? AND persona_id = ? ORDER BY timestamp DESC',
                           (tipo, persona_id))
            historial = [datetime.fromisoformat(row[0]).strftime('%d/%m/%Y %H:%M:%S') for row in cursor.fetchall()]
            return render_template('info.html', tipo=tipo, persona=persona, historial=historial)
        else:
            return 'No encontrado', 404

@app.route('/descargar_qr/<tipo>/<int:persona_id>')
def descargar_qr(tipo, persona_id):
    qr_filename = f'{tipo}_{persona_id}.png'
    qr_path = os.path.join(app.config['UPLOAD_FOLDER'], qr_filename)
    if os.path.exists(qr_path):
        return send_file(qr_path, as_attachment=True)
    return 'QR no encontrado', 404

if __name__ == '__main__':
    app.run(debug=True)