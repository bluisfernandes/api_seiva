# API with SQLAlchemy and Pydantic

'from app import db
db.create_all()'

'from app import User, db'
user = User(username='foo', email='foo@bar.com', password='asd123')
db.session.add(user)
deb.session.commit()

flask run
localhost:5000/apidoc/swagger

