import os

class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-default-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    TESTING = False

    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///smartscripts.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Upload paths
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'uploads/')
    RUBRIC_FOLDER = os.path.join(UPLOAD_FOLDER, 'rubrics')
    GUIDE_FOLDER = os.path.join(UPLOAD_FOLDER, 'guides')
    ANSWER_FOLDER = os.path.join(UPLOAD_FOLDER, 'answers')

    # AI/ML keys or service endpoints (e.g., OpenAI)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your-openai-api-key')

    # Other third-party services
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Limit file uploads to 16MB


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # in-memory DB for testing

# Optional config map for app factory use
config_by_name = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig
}

