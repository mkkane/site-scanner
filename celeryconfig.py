BROKER_URL = 'amqp://guest:guest@localhost:5672//'

CELERY_IMPORTS = ('scan')

CELERY_ROUTES = {
    'scan.process_page': {'queue': 'pull'},
    'scan.process_link': {'queue': 'push'}
    }

