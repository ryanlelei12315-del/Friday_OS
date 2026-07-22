from mem0 import Memory

memory = Memory.from_config(
    {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "host": "localhost",
                "port": 5432,
                "db_name": "friday_memory",
                "user": "friday",
                "password": "password",
            },
        }
    }
)

memory.initialize()
