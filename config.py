import os
from typing import ClassVar


BASE_DIR: str = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY: ClassVar[str] = os.environ.get('SECRET_KEY', 'canteen-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI: ClassVar[str] = 'sqlite:///' + os.path.join(BASE_DIR, 'canteen.db')
    SQLALCHEMY_TRACK_MODIFICATIONS: ClassVar[bool] = False
    UPLOAD_FOLDER: ClassVar[str] = os.path.join(BASE_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH: ClassVar[int] = 5 * 1024 * 1024
    ALLOWED_EXTENSIONS: ClassVar[set[str]] = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    SESSION_COOKIE_HTTPONLY: ClassVar[bool] = True
    SESSION_COOKIE_SAMESITE: ClassVar[str] = 'Lax'
    SESSION_COOKIE_SECURE: ClassVar[bool] = False

    WTF_CSRF_TIME_LIMIT: ClassVar[int] = 3600

    ITEMS_PER_PAGE: ClassVar[int] = 20
    MAX_CART_QTY: ClassVar[int] = 99

    HOST: ClassVar[str] = os.environ.get('HOST', '0.0.0.0')
    PORT: ClassVar[int] = int(os.environ.get('PORT', '5000'))
    CANTEEN_NAME: ClassVar[str] = 'School Canteen'
    CANTEEN_ADDRESS: ClassVar[str] = '123 School Street<br>City, State 12345'
