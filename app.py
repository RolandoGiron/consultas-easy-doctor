from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from sqlalchemy.orm import validates
import re
import config

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clinica.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config.from_object(config)
db = SQLAlchemy(app)

# Asegurarse de que existe el directorio de uploads
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

class Paciente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    dui = db.Column(db.String(10), unique=True, nullable=False)
    telefono = db.Column(db.String(20))
    fecha_nacimiento = db.Column(db.Date)
    direccion = db.Column(db.String(300))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    visitas = db.relationship('Visita', backref='paciente', lazy=True)

    @validates('dui')
    def validate_dui(self, key, dui):
        if not re.match(r'^\d{8}-\d$', dui):
            raise ValueError('Formato de DUI inválido. Debe ser NNNNNNNN-N')
        return dui

    def __repr__(self):
        return f'<Paciente {self.nombre}>'

class Visita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    diagnostico = db.Column(db.Text)
    receta = db.Column(db.Text)
    cobro = db.Column(db.Float)
    foto_path = db.Column(db.String(300))
    fecha_proxima = db.Column(db.Date, nullable=True)
    categoria = db.Column(db.String(100))
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)

    def __repr__(self):
        return f'<Visita {self.fecha_hora}>'

@app.route('/pacientes', methods=['POST', 'GET'])
def lista_pacientes():
    if request.method == 'POST':
        nombre = request.form['nombre']
        dui = request.form['dui']
        telefono = request.form['telefono']
        fecha_nacimiento = datetime.strptime(request.form['fecha_nacimiento'], '%Y-%m-%d').date()
        direccion = request.form['direccion']
        
        nuevo_paciente = Paciente(
            nombre=nombre,
            dui=dui,
            telefono=telefono,
            fecha_nacimiento=fecha_nacimiento,
            direccion=direccion
        )

        try:
            db.session.add(nuevo_paciente)
            db.session.commit()
            return redirect('/pacientes')
        except Exception as e:
            db.session.rollback()
            if 'unique' in str(e).lower():
                return 'El DUI ingresado ya existe en la base de datos'
            return 'Hubo un error al agregar el paciente'

    else:
        # Obtener parámetros de búsqueda
        nombre_busqueda = request.args.get('nombre', '').strip()
        telefono_busqueda = request.args.get('telefono', '').strip()
        
        # Construir la consulta base
        query = Paciente.query
        
        # Aplicar filtros si se proporcionaron términos de búsqueda
        if nombre_busqueda:
            query = query.filter(Paciente.nombre.ilike(f'%{nombre_busqueda}%'))
        if telefono_busqueda:
            query = query.filter(Paciente.telefono.ilike(f'%{telefono_busqueda}%'))
        
        # Ordenar y ejecutar la consulta
        pacientes = query.order_by(Paciente.fecha_registro.desc()).all()
        
        return render_template('pacientes/index.html', 
                             pacientes=pacientes,
                             request=request)
    
@app.route('/pacientes/<int:id>/visitas', methods=['GET', 'POST'])
def visitas_paciente(id):
    paciente = Paciente.query.get_or_404(id)
    
    if request.method == 'POST':
        diagnostico = request.form['diagnostico']
        receta = request.form['receta']
        cobro = float(request.form['cobro'])
        categoria = request.form['categoria']
        fecha_proxima = None
        if request.form.get('fecha_proxima'):
            fecha_proxima = datetime.strptime(request.form['fecha_proxima'], '%Y-%m-%d').date()
        
        foto = request.files.get('foto')
        foto_path = None
        if foto:
            filename = f"visita_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{foto.filename}"
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            foto_path = filename

        nueva_visita = Visita(
            diagnostico=diagnostico,
            receta=receta,
            cobro=cobro,
            foto_path=foto_path,
            fecha_proxima=fecha_proxima,
            categoria=categoria,
            paciente_id=id
        )

        try:
            db.session.add(nueva_visita)
            db.session.commit()
            
            # Verificar qué botón se presionó
            if request.form.get('action') == 'print':
                return redirect(url_for('imprimir_receta', 
                                      paciente_id=id, 
                                      visita_id=nueva_visita.id))
            return redirect(url_for('visitas_paciente', id=id))
        except Exception as e:
            db.session.rollback()
            return f'Hubo un error al registrar la visita: {str(e)}'

    visitas = Visita.query.filter_by(paciente_id=id).order_by(Visita.fecha_hora.desc()).all()
    return render_template('pacientes/visitas.html', 
                         paciente=paciente, 
                         visitas=visitas,
                         config=app.config)

@app.route('/pacientes/delete/<int:id>')
def eliminar_paciente(id):
    paciente = Paciente.query.get_or_404(id)
    try:
        db.session.delete(paciente)
        db.session.commit()
        return redirect('/pacientes')
    except:
        return 'Hubo un problema al eliminar el paciente'

@app.route('/pacientes/<int:paciente_id>/visitas/delete/<int:visita_id>')
def eliminar_visita(paciente_id, visita_id):
    visita = Visita.query.get_or_404(visita_id)
    try:
        db.session.delete(visita)
        db.session.commit()
        return redirect(f'/pacientes/{paciente_id}/visitas')
    except:
        return 'Hubo un problema al eliminar la visita'

@app.route('/pacientes/edit/<int:id>', methods=['GET', 'POST'])
def editar_paciente(id):
    paciente = Paciente.query.get_or_404(id)
    
    if request.method == 'POST':
        paciente.nombre = request.form['nombre']
        paciente.dui = request.form['dui']
        paciente.telefono = request.form['telefono']
        paciente.fecha_nacimiento = datetime.strptime(request.form['fecha_nacimiento'], '%Y-%m-%d').date()
        paciente.direccion = request.form['direccion']
        
        try:
            db.session.commit()
            return redirect('/pacientes')
        except Exception as e:
            if 'unique' in str(e).lower():
                return 'El DUI ingresado ya existe en la base de datos'
            return 'Hubo un error al actualizar el paciente'
    
    return render_template('pacientes/edit.html', paciente=paciente)

@app.route('/pacientes/<int:paciente_id>/visitas/edit/<int:visita_id>', methods=['GET', 'POST'])
def editar_visita(paciente_id, visita_id):
    visita = Visita.query.get_or_404(visita_id)
    paciente = Paciente.query.get_or_404(paciente_id)
    
    if request.method == 'POST':
        visita.diagnostico = request.form['diagnostico']
        visita.receta = request.form['receta']
        visita.cobro = float(request.form['cobro'])
        visita.categoria = request.form['categoria']
        visita.fecha_proxima = None
        if request.form.get('fecha_proxima'):
            visita.fecha_proxima = datetime.strptime(request.form['fecha_proxima'], '%Y-%m-%d').date()
        
        foto = request.files.get('foto')
        if foto and foto.filename:
            # Eliminar foto anterior si existe
            if visita.foto_path:
                try:
                    os.remove(os.path.join(app.config['UPLOAD_FOLDER'], visita.foto_path))
                except:
                    pass
            
            filename = f"visita_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{foto.filename}"
            foto.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            visita.foto_path = filename
        
        try:
            db.session.commit()
            return redirect(f'/pacientes/{paciente_id}/visitas')
        except:
            return 'Hubo un error al actualizar la visita'
    
    return render_template('pacientes/edit_visita.html', paciente=paciente, visita=visita)

@app.route('/pacientes/<int:paciente_id>/visitas/<int:visita_id>/receta')
def imprimir_receta(paciente_id, visita_id):
    try:
        visita = Visita.query.get_or_404(visita_id)
        paciente = Paciente.query.get_or_404(paciente_id)
        return render_template('pacientes/receta.html', 
                             visita=visita, 
                             paciente=paciente,
                             config=app.config)
    except Exception as e:
        return f'Error al generar la receta: {str(e)}'

if __name__ == "__main__":
    with app.app_context():
        # Crear todas las tablas de la base de datos
        db.create_all()
    app.run(host='0.0.0.0', port=5000)