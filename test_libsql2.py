import asyncio
import libsql_client

async def main():
    client = libsql_client.create_client("file:test.db")
    res = await client.execute("SELECT * FROM test")
    print(res.rows[0].asdict())
    
asyncio.run(main())
