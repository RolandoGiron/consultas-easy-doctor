from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///clinica.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
db = SQLAlchemy(app)

# Asegurarse de que existe el directorio de uploads
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

class Paciente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(200), nullable=False)
    telefono = db.Column(db.String(20))
    fecha_nacimiento = db.Column(db.Date)
    direccion = db.Column(db.String(300))
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    visitas = db.relationship('Visita', backref='paciente', lazy=True)

    def __repr__(self):
        return f'<Paciente {self.nombre}>'

class Visita(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    diagnostico = db.Column(db.Text)
    receta = db.Column(db.Text)
    cobro = db.Column(db.Float)
    foto_path = db.Column(db.String(300))
    paciente_id = db.Column(db.Integer, db.ForeignKey('paciente.id'), nullable=False)

    def __repr__(self):
        return f'<Visita {self.fecha_hora}>'

@app.route('/pacientes', methods=['POST', 'GET'])
def lista_pacientes():
    if request.method == 'POST':
        nombre = request.form['nombre']
        telefono = request.form['telefono']
        fecha_nacimiento = datetime.strptime(request.form['fecha_nacimiento'], '%Y-%m-%d').date()
        direccion = request.form['direccion']
        
        nuevo_paciente = Paciente(
            nombre=nombre,
            telefono=telefono,
            fecha_nacimiento=fecha_nacimiento,
            direccion=direccion
        )

        try:
            db.session.add(nuevo_paciente)
            db.session.commit()
            return redirect('/pacientes')
        except:
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
                            request=request)  # Pasar request para acceder a args en la plantilla
    
@app.route('/pacientes/<int:id>/visitas', methods=['GET', 'POST'])
def visitas_paciente(id):
    paciente = Paciente.query.get_or_404(id)
    
    if request.method == 'POST':
        diagnostico = request.form['diagnostico']
        receta = request.form['receta']
        cobro = float(request.form['cobro'])
        foto = request.files.get('foto')
        
        # Guardar la foto si se proporcionó una
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
            paciente_id=id
        )

        try:
            db.session.add(nueva_visita)
            db.session.commit()
            return redirect(f'/pacientes/{id}/visitas')
        except:
            return 'Hubo un error al registrar la visita'

    visitas = Visita.query.filter_by(paciente_id=id).order_by(Visita.fecha_hora.desc()).all()
    return render_template('pacientes/visitas.html', paciente=paciente, visitas=visitas)

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
        paciente.telefono = request.form['telefono']
        paciente.fecha_nacimiento = datetime.strptime(request.form['fecha_nacimiento'], '%Y-%m-%d').date()
        paciente.direccion = request.form['direccion']
        
        try:
            db.session.commit()
            return redirect('/pacientes')
        except:
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

if __name__ == "__main__":
    with app.app_context():
        # Crear todas las tablas de la base de datos
        db.create_all()
    app.run(debug=True)