from smartscripts import create_app

app = create_app()
celery = app.celery

if __name__ == '__main__':
    # Start the Celery worker from this script
    celery.worker_main()
