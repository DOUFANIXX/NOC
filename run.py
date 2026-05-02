from app import create_app


app = create_app()


if __name__ == "__main__":
    try:
        from waitress import serve

        serve(app, host=app.config["HOST"], port=app.config["PORT"])
    except ImportError:
        app.run(host=app.config["HOST"], port=app.config["PORT"], debug=False)
