from flask import Flask, render_template, redirect,request, url_for, flash, jsonify
import json
import jsonpickle
from json import JSONEncoder
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_socketio import SocketIO,send,join_room,leave_room
from flask_login import LoginManager,login_user,UserMixin,login_required, logout_user, current_user
from flask_script import Manager
from flask_migrate import Migrate, MigrateCommand
from datetime import datetime
from marshmallow import Schema, fields
from elasticsearch import Elasticsearch
from forms import *


app= Flask(__name__)
app.config['SECRET_KEY'] ='secretKey'
app.config['SQLALCHEMY_DATABASE_URI'] ='sqlite:///chat.db'

db= SQLAlchemy(app)
db=SQLAlchemy(session_options={"autoflush": False})
socketio= SocketIO(app)
login_manager= LoginManager(app)
login_manager.login_view='login'
migrate= Migrate(app,db)
manager= Manager(app)
ma=Marshmallow(app)
es=Elasticsearch()

manager.add_command('db', MigrateCommand)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

room_members=db.Table('room_members',
    #db.Column('id', db.Integer, primary_key=True),
    db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
    db.Column('room_id', db.Integer(), db.ForeignKey('room.id')),
    db.UniqueConstraint('user_id','room_id', name='UC_user_id_room_id')
)

#q=db.session.query(room_members.c.user_id,room_members.c.room_id,sa.func.count().label('# connections'),).group_by(room_members.c.user_id,room_members.c.room_id,).having(sa.func.count()>1)
class User(db.Model, UserMixin):
    id= db.Column(db.Integer, primary_key=True)
    username= db.Column(db.String(20),unique=True,nullable=False)
    rooms=db.relationship('Room', secondary=room_members, backref=db.backref('members', lazy='dynamic'))
    usermsgs=db.relationship('Message', backref='msgsuser', lazy=True)
    def __repr__(self):
        return f"User('{self.username}')"

class Room(db.Model):
    __searchable_=['roomname']
    id= db.Column(db.Integer, primary_key=True)
    roomname= db.Column(db.String(20),nullable=False)
    roomcode=db.Column(db.String(100),unique=True,nullable=False)
    created_by=db.Column(db.String(20),nullable=False)
    created_at=db.Column(db.DateTime, nullable=False, default= datetime.utcnow)
    roommsgs=db.relationship('Message', backref='msgsroom', lazy=True)
    
    #members=db.relationship('User', secondary=relation, primaryjoin=('User.id==relation.c.friends_id'), secondaryjoin=('User.id==relation.c.mutual_friend_id'),backref=db.backref('mutual_friends', lazy='dynamic'), lazy='dynamic')

    def __repr__(self):
        return f"User('{self.roomname}','{self.created_by}')"
class Message(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    msg=db.Column(db.String(100),nullable=False)
    sent_at=db.Column(db.DateTime, nullable=False, default= datetime.utcnow)
    userID=db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    roomID=db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    def __repr__(self):
        return f"User('{self.msg}','{self.sent_at}')"
class UserSchema(ma.ModelSchema):
    class Meta:
        model=User
class RoomSchema(ma.ModelSchema):
    class Meta:
        model=Room

class MessageSchema(ma.ModelSchema):
    #sent_at=fields.String()
    # id=fields.Integer()
    # msg=fields.String()
    # sent_at = fields.String()
    #msgsroom= fields.Nested(RoomSchema)
    class Meta:
    #    fields=('id', 'msg', 'sent_at','msgsuser','msgsroom')
    #     dateformat='%d %b, %H:%M'
        model=Message
    #     sent_at = fields.String()
    sent_at=fields.String()
    msgsuser= ma.Nested(UserSchema)        
        
# @app.route('/search', methods=['GET'])
# def index():
#     results= es.get(index='contents', doc_type='title', id='my-new-slug')
#     return jsonify(results['_source'])


@app.route('/')
def home():
    if current_user.is_authenticated:
        #rooms= User.query.order_by(User.date_posted.desc()).paginate(page=page, per_page=5)
        user_rooms=User.query.filter_by(username=current_user.username).first().rooms
        user_rooms.reverse()
        len_rooms=len(user_rooms)
    else:
        user_rooms=len_rooms=0
    return render_template('index.html', user_rooms=user_rooms, len_rooms=len_rooms, title='Home')
   
@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        flash(f'you are already logged in')
        return redirect(url_for('home'))

    form=LoginForm()
    if form.validate_on_submit():
        user= User.query.filter_by(username=form.username.data).first()
        if user:
            login_user(user)
            next_page=request.args.get('next') 
            return redirect(next_page) if next_page else  redirect(url_for('home'))
        else:
            flash(f'it seems like you do not know your username and password', 'failure')
    return render_template('login.html', form=form, title='Login')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if current_user.is_authenticated:
        flash(f'you are already logged in')
        return redirect(url_for('home'))
    form=RegistrationForm()
    if form.validate_on_submit():
        user=User(username=form.username.data)
        db.session.add(user)
        db.session.commit()
        flash(f'you can pick your class now, {form.username.data}', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html', form=form, title='Register')
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/join_room', methods=['GET','POST'])
@login_required
def join():
    form=JoinRoomForm()
    if form.validate_on_submit():
        room= Room.query.filter_by(roomcode=form.roomcode.data).first()
        if room:
            if current_user in room.members:
                flash(f'you are already in group') 
            else:
                room.members.append(current_user)
                db.session.commit()
                return redirect(url_for('chatroom', room_id=room.id))
        else:
            flash(f'code invalid')
    return render_template('join.html', form=form, title='Join-Room')
@app.route('/create_room', methods=['GET','POST'])
@login_required
def create():
    form=CreateRoomForm()
    if form.validate_on_submit():
        room=Room.query.filter_by(roomcode=form.roomcode.data).first()
        if room:
            flash('roomcode already taken')
        else:    
            room=Room(roomname=form.roomname.data, roomcode=form.roomcode.data, created_by=current_user.username)
            db.session.add(room)
            db.session.commit()
            user=User.query.filter_by(username=current_user.username).first()
            room.members.append(user)
            db.session.commit()
            flash(f'group created', 'success')
            return redirect(url_for('home'))
    return render_template('create.html', form=form, title='Create-Room')
    
@app.route('/chat_room/<int:room_id>', methods=['GET', 'POST'])
@login_required
def chatroom(room_id):
    roomObj= Room.query.get_or_404(room_id)
    if current_user not in roomObj.members:
        return 'Room not found', 404
    else:
        page= request.args.get('page', 1, type=int) 
        room= roomObj.roomcode
        username=current_user.username
        #messages= Message.query.order_by(Message.sent_at.desc()).paginate(page=page, per_page=2)
        limit_msgs=3

        page= request.args.get('page', 0, type=int)
        off=page*limit_msgs
        messages= Message.query.filter_by(msgsroom=roomObj).order_by(Message.id.desc()).limit(limit_msgs).offset(off).all()
        for message in messages:
            message.sent_at=message.sent_at.strftime('%d %b, %H:%M')
            # print(current_user)
            # print(message.msgsuser)
        return render_template('chatroom.html',title=roomObj.roomname,roomObj=roomObj, room=room, username=username, messages=messages[::-1])

@socketio.on('send_message')
def handle_message(data):
    app.logger.info(f"{data['username']} has sent message to the room {data['room']}: {data['message']}")
    data['sent_at']=datetime.now().strftime('%d %b, %H:%M')
    msg=Message(msg=data['message'], msgsuser=current_user, msgsroom=Room.query.filter_by(roomcode=data['room']).first())
    db.session.add(msg)
    db.session.commit()
    socketio.emit('recieve_message',data, room=data['room'])

@socketio.on('join_room')
def handle_join(data):
    print(f"{data['username']} has joined the room {data['room']}")
    join_room(data['room'])
    socketio.emit('join_room_announ',data, room=data['room'])


@app.route('/chat_room/<int:room_id>/messages/')
@login_required
def chatroom_messages(room_id): 
    roomObj= Room.query.get_or_404(room_id)
    if current_user not in roomObj.members:
        return 'Room not found', 404
    else:
        limit_msgs=3

        page= request.args.get('page', 0, type=int)
        off=page*limit_msgs
        messages= Message.query.filter_by(msgsroom=roomObj).order_by(Message.id.desc()).limit(limit_msgs).offset(off).all()
        for message in messages:
            message.sent_at=message.sent_at.strftime('%d %b, %H:%M')
        user_schema=MessageSchema(many=True)        
        output=user_schema.dump(messages[::-1])
        return jsonify(output)
            
@app.route('/chat_room/<int:room_id>/info', methods=['GET', 'POST'])
@login_required
def chatroom_info(room_id): 
    roomObj= Room.query.get_or_404(room_id)
    if current_user not in roomObj.members:
        return 'Room not found', 404
    else: 
        return render_template('chatroom_info.html',title=roomObj.roomname,roomObj=roomObj)

@app.route('/chat_room/<int:room_id>/info/update_room', methods=['GET', 'POST'])
@login_required
def chatroom_info_update(room_id):
    roomObj= Room.query.get_or_404(room_id)
    if current_user not in roomObj.members:
        return 'Room not found', 404
    else: 
        old_room_members=[user.username for user in roomObj.members]
        if current_user not in roomObj.members:
            abort(403)
        form=UpdateRoomForm()
        if form.validate_on_submit():
            roomObj.roomname= form.roomname.data
            roommembers=form.roommembers.data
            room_members=roommembers.replace(' ','').split(',')
            changes={user for user in max(old_room_members,room_members) if user not in min(old_room_members,room_members) and user if User.query.filter_by(username=user).first()}
            if changes:
                for user in changes:
                    user=User.query.filter_by(username=user).first()
                    if user in roomObj.members:
                        roomObj.members.remove(user)
                    else:
                        roomObj.members.append(user)
            db.session.commit()
            flash(f'{roomObj.roomname}, room has been updated', 'success')  
            return redirect(url_for('chatroom_info', room_id=roomObj.id))
        elif request.method =='GET':
            form.roomname.data= roomObj.roomname
            form.roommembers.data= ','.join(old_room_members)    
        return render_template('chatroom_info_update.html',title=roomObj.roomname,roomObj=roomObj, form=form)
 

if __name__== '__main__':
    socketio.run(app,debug=True)
