from database import engine


try:

    with engine.connect() as connection:

        print(
            "PostgreSQL connection successful! ✅"
        )

        print(
            "Database:",
            connection.engine.url.database
        )


except Exception as error:

    print(
        "PostgreSQL connection failed! ❌"
    )

    print(error)