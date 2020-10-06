from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField,PasswordField,SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from flask_login import current_user
from chat import User, Room,room_members 

class RegistrationForm(FlaskForm):
    username=StringField('Username',validators=[DataRequired(), Length(min=2, max=50)])
    submit=SubmitField('SignUp')

    def validate_username(self,username):
        user= User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('This username is already taken, Go and think of another one')

class LoginForm(FlaskForm):
    username=StringField('Username',validators=[DataRequired(), Length(min=2, max=50)])   
    submit=SubmitField('Log in')


class JoinRoomForm(FlaskForm):
    roomcode=StringField('Room code',validators=[DataRequired(), Length(min=2, max=50)])   
    submit=SubmitField('Enter Room')
class CreateRoomForm(FlaskForm):
    roomname=StringField('Room name',validators=[DataRequired(), Length(min=2, max=50)])   
    roomcode=StringField('Room code',validators=[DataRequired(), Length(min=2, max=50)])   
    submit=SubmitField('Create Room')

class UpdateRoomForm(FlaskForm):
    roomname=StringField('Room name',validators=[DataRequired(), Length(min=2, max=50)])   
    roommembers=StringField('Room members',validators=[DataRequired(), Length(min=2, max=100)])   
    submit=SubmitField('Update Room')


        
    