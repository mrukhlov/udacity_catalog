from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Base, DishType, Dish, User

engine = create_engine('sqlite:///recipes.db')
# Bind the engine to the metadata of the Base class so that the
# declaratives can be accessed through a DBSession instance
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
# A DBSession() instance establishes all conversations with the database
# and represents a "staging zone" for all the objects loaded into the
# database session object. Any change made against the objects in the
# session won't be persisted into the database until you call
# session.commit(). If you're not happy about the changes, you can
# revert all of them back to the last commit by calling
# session.rollback()
session = DBSession()

# Create dummy user
User1 = User(name="Robo Barista", email="tinnyTim@udacity.com",
             picture='https://pbs.twimg.com/profile_images/2671170543/18debd694829ed78203a5a36dd364160_400x400.png')
session.add(User1)
session.commit()

type1 = DishType(user_id=1, name="Lasagna")

session.add(type1)
session.commit()

menuItem2 = Dish(user_id=1, name="Meat Lasagna",
                     recipe="Meat Lasagna with tomato mayo and lettuce",
                     price="$7.50", type=type1)

session.add(menuItem2)
session.commit()

menuItem1 = Dish(user_id=1, name="Veggie Lasagna", recipe="Veggie Lasagna with garlic and parmesan",
                     price="$2.99", type=type1)

session.add(menuItem1)
session.commit()

#asd

type2 = DishType(user_id=1, name="Soup")

session.add(type2)
session.commit()

menuItem2 = Dish(user_id=1, name="Cream Soup",
                 recipe="Cream Soup with tomato mayo and lettuce",
                 price="$7.50", type=type2)

session.add(menuItem2)
session.commit()

menuItem1 = Dish(user_id=1, name="Beans Soup",
                 recipe="Beans Soup with garlic and parmesan",
                 price="$2.99", type=type2)

session.add(menuItem1)
session.commit()