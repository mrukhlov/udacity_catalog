from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()

class User(Base):
	__tablename__ = 'user'
	name = Column(String(250), nullable=False)
	email = Column(String(250), nullable=False)
	picture = Column(String(250))
	id = Column(Integer, primary_key=True)

class DishType(Base):
	__tablename__ = 'type'
	name = Column(String(80), nullable=False)
	id = Column(Integer, primary_key=True)
	user_id = Column(Integer, ForeignKey('user.id'))
	user = relationship(User)

	@property
	def serialize(self):
		#Returns data in serializeable format
		return {
			'name': self.name,
			'id': self.id,
		}

class Dish(Base):
	__tablename__ = 'dish'
	name = Column(String(80), nullable=False)
	id = Column(Integer, primary_key=True)
	recipe = Column(String(250))
	photo = Column(String(250))
	price = Column(String(8))
	time = Column(String(20))
	type_id = Column(Integer, ForeignKey('type.id'))
	type = relationship(DishType)
	user_id = Column(Integer, ForeignKey('user.id'))
	user = relationship(User)

	@property
	def serialize(self):
		#Returns data in serializeable format
		return {
			'name': self.name,
			'recipe': self.recipe,
			'id': self.id,
			'price': self.price,
			'time': self.time,
			'photo': self.photo
		}

engine = create_engine('sqlite:///recipes.db')
Base.metadata.create_all(engine)