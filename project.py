import json
import random
import string

import httplib2
import requests
from flask import Flask, render_template, url_for, request, redirect, flash, jsonify, session as login_session, \
	make_response
from oauth2client.client import FlowExchangeError
from oauth2client.client import flow_from_clientsecrets
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
import bleach

from database_setup import Base, DishType, Dish, User

CLIENT_ID = json.loads(open('client_secrets.json', 'r').read())['web']['client_id']

engine = create_engine('sqlite:///recipes.db')
Base.metadata.bind = engine
DBSession = sessionmaker(bind=engine)
session = DBSession()

app = Flask(__name__)


@app.route('/login')
def showLogin():
	state = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in xrange(32))
	login_session['state'] = state
	print login_session
	return render_template('login.html', STATE=state)


@app.route('/gconnect', methods=['POST'])
def gconnect():
	# Validate state token
	if request.args.get('state') != login_session['state']:
		response = make_response(json.dumps('Invalid state parameter.'), 401)
		response.headers['Content-Type'] = 'application/json'
		return response
	# Obtain authorization code
	code = request.data

	try:
		# Upgrade the authorization code into a credentials object
		oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
		oauth_flow.redirect_uri = 'postmessage'
		credentials = oauth_flow.step2_exchange(code)
	except FlowExchangeError:
		response = make_response(json.dumps('Failed to upgrade the authorization code.'), 401)
		response.headers['Content-Type'] = 'application/json'
		return response

	# Check that the access token is valid.
	access_token = credentials.access_token
	url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s' % access_token)
	h = httplib2.Http()
	result = json.loads(h.request(url, 'GET')[1])
	# If there was an error in the access token info, abort.
	if result.get('error') is not None:
		response = make_response(json.dumps(result.get('error')), 500)
		response.headers['Content-Type'] = 'application/json'
		return response

	# Verify that the access token is used for the intended user.
	gplus_id = credentials.id_token['sub']
	if result['user_id'] != gplus_id:
		response = make_response(json.dumps("Token's user ID doesn't match given user ID."), 401)
		response.headers['Content-Type'] = 'application/json'
		return response

	# Verify that the access token is valid for this app.
	if result['issued_to'] != CLIENT_ID:
		response = make_response(json.dumps("Token's client ID does not match app's."), 401)
		print "Token's client ID does not match app's."
		response.headers['Content-Type'] = 'application/json'
		return response

	stored_credentials = login_session.get('credentials')
	stored_gplus_id = login_session.get('gplus_id')
	if stored_credentials is not None and gplus_id == stored_gplus_id:
		response = make_response(json.dumps('Current user is already connected.'), 200)
		response.headers['Content-Type'] = 'application/json'
		return response

	# Store the access token in the session for later use.
	login_session['credentials'] = credentials
	login_session['gplus_id'] = gplus_id
	login_session['provider'] = 'google'

	# Get user info
	userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
	params = {'access_token': credentials.access_token, 'alt': 'json'}
	answer = requests.get(userinfo_url, params=params)

	data = answer.json()


	login_session['username'] = data['name']
	login_session['picture'] = data['picture']
	login_session['email'] = data['email']

	user_id = getUserID(data['email'])
	if not user_id:
		user_id = createUser(login_session)

	login_session['user_id'] = user_id

	output = ''
	output += '<h1>Welcome, '
	output += login_session['username']
	output += '!</h1>'
	output += '<img src="'
	output += login_session['picture']
	output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
	# flash("you are now logged in as %s" % login_session['username'])
	print "done!"

	return output


@app.route('/gdisconnect')
def gdisconnect():
	credentials = login_session.get('credentials')
	print credentials
	if credentials is None:
		response = make_response(json.dumps('Current user not connected.'), 401)
		response.headers['Content-Type'] = 'application/json'
		return response
	access_token = credentials.access_token
	url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
	h = httplib2.Http()
	result = h.request(url, 'GET')[0]
	if result['status'] == '200':
		# del login_session['access_token']
		del login_session['credentials']
		del login_session['gplus_id']
		del login_session['username']
		del login_session['email']
		del login_session['picture']
		response = make_response(json.dumps('Successfully disconnected.'), 200)
		response.headers['Content-Type'] = 'application/json'
		return response
	else:
		del login_session['credentials']
		del login_session['gplus_id']
		del login_session['username']
		del login_session['email']
		del login_session['picture']
		response = make_response(json.dumps('Failed to revoke token for given user.', 400))
		response.headers['Content-Type'] = 'application/json'
		return response

@app.route('/fbconnect', methods=['POST'])
def fbconnect():
	# Validate state token
	if request.args.get('state') != login_session['state']:
		response = make_response(json.dumps('Invalid state parameter.'), 401)
		response.headers['Content-Type'] = 'application/json'
		return response
	# Obtain authorization code
	access_token = request.data

	app_id = json.loads(open('fb_client_secrets.json', 'r').read())['web']['app_id']
	app_secret = json.loads(open('fb_client_secrets.json', 'r').read())['web']['app_secret']
	url = 'https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s' % (
        app_id, app_secret, access_token)
	h = httplib2.Http()
	result = h.request(url, 'GET')[1]

	userinfo_url = 'https://graph.facebook.com/v2.2/me'
	token = result.split('&')[0]

	url = 'https://graph.facebook.com/v2.4/me?%s&fields=name,id,email' % token
	h = httplib2.Http()
	result = h.request(url, 'GET')[1]
	data = json.loads(result)

	login_session['provider'] = 'facebook'
	login_session['username'] = data['name']
	login_session['email'] = data['email']
	login_session['facebook_id'] = data['id']

	url = 'https://graph.facebook.com/v2.4/me/picture?%s&redirect=0&height=200&width=200' % token
	h = httplib2.Http()
	result = h.request(url, 'GET')[1]
	data = json.loads(result)
	login_session['picture'] = data['data']['url']

	user_id = getUserID(login_session['email'])
	if not user_id:
		user_id = createUser(login_session)
	login_session['user_id'] = user_id

	output = ''
	output += '<h1>Welcome, '
	output += login_session['username']
	output += '!</h1>'
	output += '<img src="'
	output += login_session['picture']
	output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: 150px;-moz-border-radius: 150px;"> '
	return output

@app.route('/fbdisconnect')
def fbdisconnect():
	facebook_id = login_session['facebook_id']
	url = 'https://graph.facebook.com/%s/permissions' % facebook_id
	h = httplib2.Http()
	try:
		result = h.request(url, 'DELETE')[1]
	except:
		pass

	del login_session['username']
	del login_session['email']
	del login_session['picture']
	del login_session['user_id']
	del login_session['facebook_id']

	return 'you have logged out'

@app.route('/disconnect')
def disconnect():
	if 'provider' in login_session:
		if login_session['provider'] == 'google':
			gdisconnect()
		if login_session['provider'] == 'facebook':
			fbdisconnect()

		del login_session['provider']

		flash('u have been logged out successfully')
		return redirect(url_for('showGroups'))
	else:
		flash('you must be logged in first')
		return redirect(url_for('showGroups'))


# Making an API endpoint
@app.route('/group/JSON')
def dishTypesJSON():
	items = session.query(DishType).all()
	return jsonify(MenuItems=[i.serialize for i in items])

@app.route('/group/<int:group_id>/JSON')
def typeDishJSON(group_id):
	items = session.query(Dish).filter_by(type_id=group_id).all()
	return jsonify(MenuItems=[i.serialize for i in items])

@app.route('/dish/<int:group_id>/<int:dish_id>/JSON')
def menuItemJSON(group_id, dish_id):
	items = session.query(Dish).filter_by(id=dish_id, type_id=group_id).one()
	return jsonify(MenuItem=items.serialize)

@app.route('/')
def showGroups():
	print login_session
	types = session.query(DishType).order_by(asc(DishType.name))
	return render_template('index.html', types = types, session=login_session)

#Groups

@app.route('/<int:group_id>')
def showGroup(group_id):
	group = session.query(DishType).filter_by(id=group_id).one()
	dishes = session.query(Dish).filter_by(type_id=group_id)
	types = session.query(DishType).order_by(asc(DishType.name))
	return render_template('showGroup.html', dishes = dishes, group=group, types = types)

@app.route('/add_group', methods=['POST', 'GET'])
def addGroup():
	if 'username' not in login_session:
		return redirect('login')
	if request.method == 'POST':
		name = bleach.clean(request.form['name'])
		group = session.query(DishType).filter_by(name=name).all()
		if group:
			message = 'Sorry, this group is already present'
			print message
		else:
			session_user_email = login_session['email']
			user = session.query(User).filter_by(email=session_user_email).one()

			new_group = DishType(name=name, user_id=user.id)
			session.add(new_group)
			session.commit()
		return redirect('/')
	else:
		return render_template('addGroup.html')

@app.route('/edit_group/<int:group_id>', methods=['POST', 'GET'])
def editGroup(group_id):
	if 'username' not in login_session:
		return redirect('login')

	group = session.query(DishType).filter_by(id=group_id).one()

	if login_session['user_id'] == group.user_id:
		if request.method == 'POST':
			name = bleach.clean(request.form['name'])
			# group = session.query(DishType).filter_by(id=group_id).one()
			group.name = name
			print group
			session.add(group)
			session.commit()
			return redirect('/')
		else:
			group = session.query(DishType).filter_by(id=group_id).one()
			return render_template('editGroup.html', group=group)
	else:
		return redirect('/')

@app.route('/delet_group/<int:group_id>', methods=['POST', 'GET'])
def deleteGroup(group_id):
	if 'username' not in login_session:
		return redirect('login')
	group = session.query(DishType).filter_by(id=group_id).one()
	if login_session['user_id'] == group.user_id:
		session.delete(group)
		session.commit()
	return redirect('/')

#Dishes

@app.route('/<int:group_id>/<int:dish_id>')
def showDish(group_id, dish_id):
	dish = session.query(Dish).filter_by(type_id=group_id, id=dish_id).one()
	return render_template('showDish.html', dish = dish, group_id=group_id)

@app.route('/add_dish/<int:group_id>', methods=['POST', 'GET'])
def addDish(group_id):
	if 'username' not in login_session:
		return redirect('login')

	group = session.query(DishType).filter_by(id=group_id).one()
	if login_session['user_id'] == group.user_id:

		if request.method == 'POST':

			name = bleach.clean(request.form['name'])
			recipe = bleach.clean(request.form['recipe'])
			photo = bleach.clean(request.form['photo'])
			price = bleach.clean(request.form['price'])
			time = bleach.clean(request.form['time'])

			dish = session.query(Dish).filter_by(name=name).all()
			print dish
			if dish:
				message = 'Sorry, this recipe is already present'
				print message
			else:
				new_recipe = Dish(name=name, user_id=group.user_id, type_id=group_id, recipe=recipe, photo=photo, price=price, time=time)
				session.add(new_recipe)
				session.commit()

			return redirect(url_for('showGroup', group_id=group_id))
		else:
			return render_template('addDish.html', group_id=group_id)
	else:
		return redirect(url_for('showGroup', group_id = group.id))

@app.route('/edit_dish/<int:dish_id>', methods=['POST', 'GET'])
def editDish(dish_id):
	if 'username' not in login_session:
		return redirect('login')

	dish = session.query(Dish).filter_by(id=dish_id).one()
	group = session.query(DishType).filter_by(id=dish.type_id).one()

	if login_session['user_id'] == group.user_id:

		if request.method == 'POST':

			name = bleach.clean(request.form['name'])
			recipe = bleach.clean(request.form['recipe'])
			photo = bleach.clean(request.form['photo'])
			price = bleach.clean(request.form['price'])
			time = bleach.clean(request.form['time'])

			dish.name = name
			dish.recipe = recipe
			dish.photo = photo
			dish.price = price
			dish.time = time

			print dish
			session.add(dish)
			session.commit()

			# return render_template('showDish.html', dish=dish, group_id=dish.type_id)
			return redirect(url_for('showGroup', group_id=dish.type_id))
		else:
			dish = session.query(Dish).filter_by(id=dish_id).one()
			group = session.query(DishType).filter_by(id=dish.type_id).one()
			return render_template('editDish.html', dish=dish, group = group)
	else:
		return redirect(url_for('showGroup', group_id=group.id))

@app.route('/delete_dish/<int:dish_id>', methods=['POST', 'GET'])
def deleteDish(dish_id):
	if 'username' not in login_session:
		return redirect('login')
	dish = session.query(Dish).filter_by(id=dish_id).one()
	group_id = dish.type_id
	group = session.query(DishType).filter_by(id=group_id).one()
	if login_session['user_id'] == group.user_id:
		session.delete(dish)
		session.commit()
	return redirect(url_for('showGroup', group_id = group_id))


def getUserID(email):
	try:
		user = session.query(User).filter_by(email=email).one()
		return user.id
	except:
		return None

def getUserInfo(user_id):
	user = session.query(User).filter_by(id=user_id).one()
	return user

def createUser(login_session):
	newUser = User(name = login_session['username'], email = login_session['email'], picture = login_session['picture'])
	session.add(newUser)
	session.commit()
	user = session.query(User).filter_by(email = login_session['email']).one()
	return user.id


if __name__ == '__main__':
	app.secret_key = 'super_secret_key'
	app.debug = True
	app.run(host='0.0.0.0', port=5000)