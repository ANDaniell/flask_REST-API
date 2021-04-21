import datetime

from flask import request, session, jsonify
from flask import make_response
from flask import Flask, render_template, redirect
from flask_wtf import FlaskForm
from werkzeug.exceptions import abort
from wtforms import PasswordField, BooleanField, SubmitField
from wtforms.fields.html5 import EmailField
from wtforms.validators import DataRequired
import os

from data import db_session, news_api
from data.news import News
from data.users import User
from forms.news import NewsForm
from forms.user import RegisterForm
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_restful import reqparse, abort, Api, Resource

app = Flask(__name__)

login_manager = LoginManager()
login_manager.init_app(app)
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=365)
app.config['SECRET_KEY'] = 'yandexlyceum_secret_key'


class LoginForm(FlaskForm):
    email = EmailField('Почта', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


@login_manager.user_loader
def load_user(user_id):
    db_sess = db_session.create_session()
    return db_sess.query(User).get(user_id)


@app.route("/")
def index():
    db_sess = db_session.create_session()
    if current_user.is_authenticated:
        news = db_sess.query(News).filter(
            (News.user == current_user) | (News.is_private != True))
    else:
        news = db_sess.query(News).filter(News.is_private != True)
    return render_template("index.html", news=news)


@app.route('/register', methods=['GET', 'POST'])
def reqister():
    form = RegisterForm()
    if form.validate_on_submit():
        if form.password.data != form.password_again.data:
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Пароли не совпадают")
        db_sess = db_session.create_session()
        if db_sess.query(User).filter(User.email == form.email.data).first():
            return render_template('register.html', title='Регистрация',
                                   form=form,
                                   message="Такой пользователь уже есть")
        user = User(
            name=form.name.data,
            email=form.email.data,
            about=form.about.data
        )
        user.set_password(form.password.data)
        db_sess.add(user)
        db_sess.commit()
        return redirect('/login')
    return render_template('register.html', title='Регистрация', form=form)


@app.route("/cookie_test")
def cookie_test():
    # request.cookies.pop('visits_count', None)
    visits_count = int(request.cookies.get("visits_count", 0))
    if visits_count:
        res = make_response(
            f"Вы пришли на эту страницу {visits_count + 1} раз")
        res.set_cookie("visits_count", str(visits_count + 1),
                       max_age=60 * 60 * 24 * 365 * 2)
    else:
        res = make_response(
            "Вы пришли на эту страницу в первый раз за последние 2 года")
        res.set_cookie("visits_count", '1',
                       max_age=60 * 60 * 24 * 365 * 2)
    # res.delete_cookie('visits_count')
    return res


@app.route("/session_test")
def session_test():
    # session.pop('visits_count', None)
    visits_count = session.get('visits_count', 0)
    session['visits_count'] = visits_count + 1
    return make_response(
        f"Вы пришли на эту страницу {visits_count + 1} раз")


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        user = db_sess.query(User).filter(User.email == form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            return redirect("/")
        return render_template('login.html',
                               message="Неправильный логин или пароль",
                               form=form)
    return render_template('login.html', title='Авторизация', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect("/")


@app.route('/news', methods=['GET', 'POST'])
@login_required
def add_news():
    form = NewsForm()
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        news = News()
        news.title = form.title.data
        news.content = form.content.data
        news.is_private = form.is_private.data
        current_user.news.append(news)
        # передаём бд данные б изменённом пользователе
        db_sess.merge(current_user)
        db_sess.commit()
        return redirect('/')
    return render_template('news.html', title='Добавление новости',
                           form=form)


@app.route('/news/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_news(id):
    form = NewsForm()
    if request.method == "GET":
        db_sess = db_session.create_session()
        news = db_sess.query(News).filter(News.id == id,
                                          News.user == current_user
                                          ).first()
        if news:
            form.title.data = news.title
            form.content.data = news.content
            form.is_private.data = news.is_private
        else:
            abort(404)
    if form.validate_on_submit():
        db_sess = db_session.create_session()
        news = db_sess.query(News).filter(News.id == id,
                                          News.user == current_user
                                          ).first()
        if news:
            news.title = form.title.data
            news.content = form.content.data
            news.is_private = form.is_private.data
            db_sess.commit()
            return redirect('/')
        else:
            abort(404)
    return render_template('news.html',
                           title='Редактирование новости',
                           form=form
                           )


@app.route('/news_delete/<int:id>', methods=['GET', 'POST'])
@login_required
def news_delete(id):
    db_sess = db_session.create_session()
    news = db_sess.query(News).filter(News.id == id,
                                      News.user == current_user
                                      ).first()
    if news:
        db_sess.delete(news)
        db_sess.commit()
    else:
        abort(404)
    return redirect('/')



@app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)




def add(name, about, email):
    user = User()
    db_sess = db_session.create_session()
    user.name = str(name)
    user.about = str(about)
    user.email = str(email)

    db_sess.add(user)
    db_sess.commit()


def del_by_filter(filter_, amount=True):
    db_sess = db_session.create_session()
    if amount:
        db_sess.query(User).filter(eval(filter_)).delete()
        db_sess.commit()
    else:
        user = db_sess.query(User).filter(eval(filter_)).first()
        db_sess.delete(user)
        db_sess.commit()
    pass


# пиздец не безопасно
def change(filter_, parametr_value):
    db_sess = db_session.create_session()
    user = db_sess.query(User).filter(eval(filter_)).first()
    # print(user)
    for key, par in parametr_value.items():
        # print(f'user.{key} = str({par})')
        try:
            exec(f'user.{key} = str({"par"})')
            # user.name = "Измененное имя пользователя"
        except Exception as e:
            print('change db data', e)
    user.created_date = datetime.datetime.now()
    db_sess.commit()


def main():
    db_session.global_init("db/blogs.db")
    app.register_blueprint(news_api.blueprint)
    """
    user.name = "Пользователь 3"
    user.about = "биография пользователя 3"
    user.email = "email3@email.ru"
    
    db_sess.add(user)
    db_sess.commit()
    """
    # change('User.id == 3', {'email': "почта"})
    # del_by_filter('User.id == 2')

    # важно
    '''
    user = db_sess.query(User).filter(User.id == 2).first()
    news = News(title="Личная запись", content="Эта запись личная",
                is_private=True)
    user.news.append(news)
    for news in user.news:
        print(news)
    db_sess.commit()

    for user in db_sess.query(User).all():
        print(user)
    '''
    # for user in db_sess.query(User).filter(User.id > 1, User.email.notilike("%1%")):
    #    print(user)

    app.run(debug=True)


def clear_data():
    os.remove("db/blogs.db")


if __name__ == '__main__':
    main()
