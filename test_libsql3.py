import asyncio
import libsql_client

async def main():
    client = libsql_client.create_client("file:test.db")
    res = await client.execute("DELETE FROM test")
    print(dir(res))
    print("rows_affected:", res.rows_affected)
    
asyncio.run(main())
