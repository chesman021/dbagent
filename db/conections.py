from infrastructure import DatabaseManager, DBEnvironment 
dev_db = DatabaseManager(DBEnvironment.DEV)
qa_db = DatabaseManager(DBEnvironment.QA)