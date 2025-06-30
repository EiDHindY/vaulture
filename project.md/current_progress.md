# initial setup ->
    1- created python venv with the name venv
    2- created a remote repo with the name Vaulture_1.0 with python .gitignore file
    3- cloned the repo using git clone
    4- made our first commit with an empty requirements.txt and .gitignore file
    5- wrote our first draft of the use_cases to implement in and saved them in a use_cases.md file
# 1st use case (create account)
    1- wrote the narrative approach for the first use_case (create_account)
    2- pushed to a new branch (create_account) with the commit"started working on the first use_case (create_account)"
    3- created the users table in src/infrastructure/database/migrations/001_users_table.sql
    4- created a def in the utils/paths.py file to return the .db file in both development and production phases
    5- created the migrate.py file in the database dir 
    6- created the logging.py file in src/utils/logging.py
    7- created the logs/ that will carry the .log file
    8- created the test/ in the src/ and made the first test file which is test_logging.py
