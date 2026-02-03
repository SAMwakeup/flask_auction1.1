from app import app, db, User

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

with app.app_context():
    db.create_all()
    u = User(username='test')
    u.set_password('pass')
    db.session.add(u)
    db.session.commit()
    print('Hash:', u.password)
    print('Starts with:', u.password[:20])
