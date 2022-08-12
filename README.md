# API with SQLAlchemy and Pydantic

To create database
`export DATABASE_USER_URI=sqlite:///database.db`

```python
from app import db
db.create_all()
```

To insert in in database
```python
from app import User, db
user = User(username='foo', email='foo@bar.com', password='asd123')
db.session.add(user)
deb.session.commit()
```

To run the API
```
flask run
localhost:5000/apidoc/swagger
```

