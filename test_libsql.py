import asyncio
import libsql_client

async def main():
    client = libsql_client.create_client("file:test.db")
    await client.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER, name TEXT)")
    await client.execute("INSERT INTO test VALUES (1, 'Alice')")
    res = await client.execute("SELECT * FROM test")
    print(res.rows[0])
    try:
        print(dict(res.rows[0]))
    except Exception as e:
        print("dict error:", e)
        print("keys?", dir(res.rows[0]))

asyncio.run(main())
