from flask import Flask, jsonify, request
from flask_pydantic_spec import FlaskPydanticSpec, Response, Request
from tinydb import TinyDB, Query
from pydantic import BaseModel, Field
from datetime import datetime
from itertools import count

from typing import Optional

app = Flask(__name__)
spec = FlaskPydanticSpec('FlAsK', title='Estudo API')
spec.register(app)

c = count()
database = TinyDB('database.json')

class QueryPessoa(BaseModel):
    id: Optional[int]
    name: Optional[str]
    age: Optional[int]

class Pessoa(BaseModel):
    id: Optional[int] = Field(default_factory=lambda: next(c))
    name: str
    age: int

class Pessoas(BaseModel):
    pessoas: list[Pessoa]
    count: int


@app.get('/')
def index():
    return {'homepage':'/', 'API version': 'v1'}


@app.get('/pessoas')
@spec.validate(query=QueryPessoa, resp=Response(HTTP_200=Pessoas))
def busca_pessoas():
    '''Retorna lista de pessoas'''
    query = request.context.query
    list_pessoas = database.search(Query().fragment(query.dict(exclude_none=True)))
    return jsonify(
            Pessoas(
                pessoas=list_pessoas, 
                count=len(list_pessoas)
            ).dict()
    )

@app.get('/pessoas/<int:id>')
@spec.validate(resp=Response(HTTP_200=Pessoa))
def busca_pessoa(id):
    '''Retorna pessoa dado o id'''
    try:
        pessoa = database.search(Query().id == id)[0]
    except IndexError:
        return {'message': 'Pessoa not found'}, 404
    return jsonify(pessoa)


@app.post('/pessoas')
@spec.validate(body=Request(Pessoa), resp=Response(HTTP_201=Pessoa))
def insere_pessoa():
    '''Insere uma pessoa no banco de dados'''
    person = request.context.body.dict()
    database.insert(person)
    return person


@app.put('/pessoas/<int:id>')
@spec.validate(body=Request(Pessoa), resp=Response(HTTP_200=Pessoa))
def altera_pessoa(id):
    '''Altera a pessoa pelo numero do id.'''
    body = request.context.body.dict()
    database.update(body, Query().id == id)
    return jsonify(body)


@app.delete('/pessoas/<int:id>')
@spec.validate(resp=Response('HTTP_204'))
def deleta_pessoa(id):
    '''Deleta a pessoa pelo numero do id.'''
    database.remove(Query().id == id)
    return jsonify({})

