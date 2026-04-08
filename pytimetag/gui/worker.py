from pytimetag.gui.celery_app import create_celery_app
from pytimetag.gui.config import GuiConfig

celery_app = create_celery_app(GuiConfig.from_env())

