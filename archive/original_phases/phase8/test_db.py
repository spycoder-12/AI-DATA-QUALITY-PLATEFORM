from sqlalchemy import text

from app.database import engine


try:

    with engine.connect() as connection:

        result = connection.execute(
            text("SELECT current_database();")
        )

        database = result.fetchone()[0]

        print("\nPostgreSQL connection successful! ✅")
        print("Database:", database)


except Exception as error:

    print("\nPostgreSQL connection failed! ❌")
    print(error)
    