from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, PasswordField, SelectField, FloatField,
                     IntegerField, TextAreaField, BooleanField, SubmitField)
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Login')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(3, 64)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(6, 128)])
    role = SelectField('Role', choices=[('student', 'Student'), ('staff', 'Staff')],
                       default='student')
    student_id = StringField('Student / Staff ID', validators=[Optional(), Length(1, 20)])
    submit = SubmitField('Register')


class MenuItemForm(FlaskForm):
    name = StringField('Item Name', validators=[DataRequired(), Length(1, 128)])
    description = TextAreaField('Description', validators=[Optional()])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    category_id = SelectField('Category', coerce=int, validators=[Optional()])
    new_category = StringField('Or add new category', validators=[Optional(), Length(1, 64)])
    image = FileField('Image', validators=[Optional(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Images only (jpg, png, gif, webp)')])
    image_url = StringField('Or image URL', validators=[Optional(), Length(0, 256)])
    available = BooleanField('Available', default=True)
    featured = BooleanField('Featured (daily special)')
    stock = IntegerField('Stock', default=0, validators=[NumberRange(min=0)])
    submit = SubmitField('Save')


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(1, 64)])
    description = StringField('Description', validators=[Optional(), Length(0, 256)])
    submit = SubmitField('Save')
